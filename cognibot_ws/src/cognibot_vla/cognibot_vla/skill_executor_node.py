"""ExecuteSkill action server: runs LeRobot's async `robot_client` as a subprocess.

One goal at a time. The client itself requests VLA on connect and IDLE on disconnect
(`lerobot_robot_cognibot`), so this node only starts and stops it, reports the command rate it
observes on `/cognibot/joint_command`, and stops the run when the arm leaves VLA (STOP, mode key)
or when `max_duration_s` elapses. Policy, checkpoint and cameras come from the environment the
container was started with (`run_robot_client.sh`); a non-empty goal `checkpoint` overrides
`VLA_CHECKPOINT` and `instruction` overrides `TASK`.
"""

from __future__ import annotations

import os
import signal
import subprocess
import threading
import time
import urllib.error
import urllib.request
from collections import deque

import rclpy
from cognibot_interfaces.action import ExecuteSkill
from cognibot_interfaces.msg import ControlMode
from rcl_interfaces.msg import ParameterDescriptor
from rclpy.action import ActionServer, CancelResponse, GoalResponse
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy
from sensor_msgs.msg import JointState

RATE_WINDOW_S = 2.0
STOP_GRACE_S = 10.0
NO_ACTION_TIMEOUT_S = 30.0


def unload_vlm(base_url: str, timeout_s: float = 10.0) -> str:
    """Ask llama-swap to unload every model so the policy gets the GPU; best effort."""
    url = base_url.rstrip("/").removesuffix("/v1") + "/api/models/unload"
    try:
        with urllib.request.urlopen(urllib.request.Request(url, method="POST"), timeout=timeout_s):
            return f"VLM unloaded ({url})"
    except (urllib.error.URLError, OSError) as exc:
        return f"VLM unload skipped ({exc})"


def stop_reason(
    cancel_requested: bool,
    elapsed_s: float,
    max_duration_s: float,
    in_vla: bool,
    entered_vla: bool,
    silent_s: float = 0.0,
) -> str | None:
    """Why a running client must be stopped now, or None to keep going.

    The arm leaving VLA only counts once the client has actually been granted VLA: before that the
    mode is whatever the operator left (typically IDLE) and the client is still connecting.
    `silent_s` is how long the client has held VLA without a single command reaching the arm.
    """
    if cancel_requested:
        return "canceled"
    if max_duration_s > 0 and elapsed_s >= max_duration_s:
        return f"max_duration_s {max_duration_s:g} reached"
    if entered_vla and not in_vla:
        return "arm left VLA mode"
    if silent_s >= NO_ACTION_TIMEOUT_S:
        return (
            f"no actions from the policy for {NO_ACTION_TIMEOUT_S:g} s "
            "(camera keys or units mismatch? see the policy-server log)"
        )
    return None


class SkillExecutor(Node):
    def __init__(self) -> None:
        super().__init__("skill_executor")
        self.declare_parameter(
            "client_script",
            "/ws/src/cognibot_vla/scripts/run_robot_client.sh",
            ParameterDescriptor(description="robot_client wrapper started per goal"),
        )
        self.declare_parameter(
            "command_topic",
            "/cognibot/joint_command",
            ParameterDescriptor(description="stream whose rate is reported as feedback"),
        )
        self._script = str(self.get_parameter("client_script").value)
        self._lock = threading.Lock()
        self._busy = False
        self._mode = ControlMode.IDLE
        self._stamps: deque[float] = deque()
        self._commands = 0
        group = ReentrantCallbackGroup()
        self.create_subscription(
            JointState,
            str(self.get_parameter("command_topic").value),
            self._on_command,
            10,
            callback_group=group,
        )
        self.create_subscription(
            ControlMode,
            "/cognibot/mode",
            self._on_mode,
            QoSProfile(
                depth=1,
                reliability=ReliabilityPolicy.RELIABLE,
                durability=DurabilityPolicy.TRANSIENT_LOCAL,
            ),
            callback_group=group,
        )
        ActionServer(
            self,
            ExecuteSkill,
            "/cognibot/vla/execute_skill",
            execute_callback=self._execute,
            goal_callback=lambda _g: GoalResponse.REJECT if self._busy else GoalResponse.ACCEPT,
            cancel_callback=lambda _g: CancelResponse.ACCEPT,
            callback_group=group,
        )
        self.get_logger().info(f"skill_executor ready ({self._script})")

    def _on_command(self, _msg: JointState) -> None:
        with self._lock:
            self._stamps.append(time.monotonic())
            self._commands += 1

    def _on_mode(self, msg: ControlMode) -> None:
        self._mode = msg.mode

    def _rate(self) -> float:
        now = time.monotonic()
        with self._lock:
            while self._stamps and now - self._stamps[0] > RATE_WINDOW_S:
                self._stamps.popleft()
            return len(self._stamps) / RATE_WINDOW_S

    def _execute(self, handle):
        goal: ExecuteSkill.Goal = handle.request
        result = ExecuteSkill.Result()
        self._busy = True
        env = dict(os.environ)
        if goal.instruction:
            env["TASK"] = goal.instruction
        if goal.checkpoint:
            env["VLA_CHECKPOINT"] = goal.checkpoint
        self.get_logger().info(
            f"starting robot_client: task={env.get('TASK')!r} "
            f"checkpoint={env.get('VLA_CHECKPOINT')}"
        )
        with self._lock:
            self._stamps.clear()
            self._commands = 0
        if env.get("LLM_BASE_URL"):
            self.get_logger().info(unload_vlm(env["LLM_BASE_URL"]))
        started = time.monotonic()
        proc = subprocess.Popen([self._script], env=env)
        entered_vla = False
        vla_since: float | None = None
        reason = "finished"
        try:
            feedback = ExecuteSkill.Feedback()
            while proc.poll() is None:
                elapsed = time.monotonic() - started
                in_vla = self._mode == ControlMode.VLA
                entered_vla = entered_vla or in_vla
                if in_vla and vla_since is None:
                    vla_since = time.monotonic()
                silent = (
                    time.monotonic() - vla_since
                    if vla_since is not None and self._commands == 0
                    else 0.0
                )
                stop = stop_reason(
                    handle.is_cancel_requested,
                    elapsed,
                    goal.max_duration_s,
                    in_vla,
                    entered_vla,
                    silent,
                )
                if stop:
                    reason = stop
                    break
                feedback.elapsed_s = float(elapsed)
                feedback.rate_hz = float(self._rate())
                handle.publish_feedback(feedback)
                time.sleep(0.5)
            else:
                reason = "client exited" if proc.returncode else "finished"
        finally:
            self._stop(proc)
            self._busy = False
        elapsed = time.monotonic() - started
        result.actions_executed = self._commands
        result.mean_rate_hz = float(self._commands / elapsed) if elapsed > 0 else 0.0
        result.success = reason != "client exited" and not reason.startswith("no actions")
        result.message = f"{reason} after {elapsed:.0f} s ({self._commands} commands)"
        if reason == "canceled":
            handle.canceled()
        elif result.success:
            handle.succeed()
        else:
            handle.abort()
        self.get_logger().info(result.message)
        return result

    def _stop(self, proc: subprocess.Popen) -> None:
        """SIGINT lets the client disconnect cleanly (which requests IDLE); SIGKILL as backstop."""
        if proc.poll() is not None:
            return
        proc.send_signal(signal.SIGINT)
        try:
            proc.wait(STOP_GRACE_S)
        except subprocess.TimeoutExpired:
            self.get_logger().warn("robot_client ignored SIGINT; killing it")
            proc.kill()
            proc.wait()


def main() -> None:
    rclpy.init()
    node = SkillExecutor()
    executor = MultiThreadedExecutor(num_threads=4)
    executor.add_node(node)
    try:
        executor.spin()
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
