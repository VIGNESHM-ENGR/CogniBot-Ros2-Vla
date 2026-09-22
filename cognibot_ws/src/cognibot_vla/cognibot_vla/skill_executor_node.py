"""ExecuteSkill action server: runs LeRobot's async `robot_client` as a subprocess.

One goal at a time. The client itself requests VLA on connect and IDLE on disconnect
(`lerobot_robot_cognibot`), so this node only starts and stops it, reports the command rate it
observes on `/cognibot/joint_command`, and stops the run when the arm leaves VLA (STOP, mode key)
or when `max_duration_s` of acting (counted from the first action, not from the goal: loading a
policy onto the GPU took 17 s of a 60 s budget) elapses. Policy, checkpoint and cameras come from
the environment the container was started with (`run_robot_client.sh`); a non-empty goal
`checkpoint` overrides `VLA_CHECKPOINT` and `instruction` overrides `TASK`. `VLA_START_POSE`
(degrees, arm joints) and `VLA_START_GRIPPER_DEG` park the arm where the checkpoint's episodes
began before the client starts.
"""

from __future__ import annotations

import math
import os
import signal
import subprocess
import threading
import time
import urllib.error
import urllib.request
from collections import deque

import rclpy
from builtin_interfaces.msg import Duration
from cognibot_interfaces.action import ExecuteSkill
from cognibot_interfaces.msg import ControlMode, ModelStatus
from cognibot_interfaces.srv import SetControlMode
from control_msgs.action import FollowJointTrajectory, ParallelGripperCommand
from rcl_interfaces.msg import ParameterDescriptor
from rclpy.action import ActionClient, ActionServer, CancelResponse, GoalResponse
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy
from sensor_msgs.msg import JointState
from std_srvs.srv import Trigger
from trajectory_msgs.msg import JointTrajectoryPoint

ARM_JOINTS = ["shoulder_pan", "shoulder_lift", "elbow_flex", "wrist_flex", "wrist_roll"]
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


def parse_start_pose(text: str) -> list[float]:
    """`VLA_START_POSE` ("0,-103,36,102,0", degrees) -> radians; empty -> no start pose."""
    values = [float(v) for v in text.replace(" ", "").split(",") if v]
    if values and len(values) != len(ARM_JOINTS):
        raise ValueError(f"VLA_START_POSE needs {len(ARM_JOINTS)} values, got {len(values)}")
    return [math.radians(v) for v in values]


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
    `elapsed_s` is acting time — from the first action — so policy loading does not eat the budget.
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
        self._set_mode = self.create_client(
            SetControlMode, "/cognibot/set_mode", callback_group=group
        )
        self._trajectory = ActionClient(
            self,
            FollowJointTrajectory,
            "/joint_trajectory_controller/follow_joint_trajectory",
            callback_group=group,
        )
        self._gripper = ActionClient(
            self, ParallelGripperCommand, "/gripper_controller/gripper_cmd", callback_group=group
        )
        self._unload_rlcd = self.create_client(
            Trigger, "/cognibot/rlcd/unload", callback_group=group
        )
        self.models_pub = self.create_publisher(
            ModelStatus,
            "/cognibot/models",
            QoSProfile(
                depth=1,
                reliability=ReliabilityPolicy.RELIABLE,
                durability=DurabilityPolicy.TRANSIENT_LOCAL,
            ),
        )
        self._policy_resident = False
        self._publish_model(ModelStatus.UNLOADED, "no policy loaded yet")
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

    def _publish_model(self, state: int, detail: str, model: str = "") -> None:
        msg = ModelStatus()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.name = "vla"
        msg.model = model or os.environ.get("VLA_CHECKPOINT", "").rstrip("/").split("/")[-1]
        msg.state, msg.detail = state, detail
        self.models_pub.publish(msg)

    def _free_rlcd(self) -> None:
        """Ask the RLCD node to drop Laya (~1.8 GB) so the policy has the GPU; best effort."""
        if not self._unload_rlcd.wait_for_service(timeout_sec=1.0):
            return
        future = self._unload_rlcd.call_async(Trigger.Request())
        if self._call(future, 10.0) and future.result() is not None:
            self.get_logger().info(f"RLCD model: {future.result().message}")

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
        model = env.get("VLA_CHECKPOINT", "").rstrip("/").split("/")[-1]
        self._publish_model(
            ModelStatus.LOADING,
            "freeing the VLM and Laya, loading the policy"
            if not self._policy_resident
            else "policy resident; starting the client",
            model,
        )
        if env.get("LLM_BASE_URL"):
            self.get_logger().info(unload_vlm(env["LLM_BASE_URL"]))
        self._free_rlcd()
        self._go_start_pose(env)
        started = time.monotonic()
        acting_since: float | None = None
        proc = subprocess.Popen([self._script], env=env)
        entered_vla = False
        vla_since: float | None = None
        reason = "finished"
        try:
            feedback = ExecuteSkill.Feedback()
            while proc.poll() is None:
                if acting_since is None and self._commands > 0:
                    acting_since = time.monotonic()
                    self._policy_resident = True
                    self._publish_model(ModelStatus.LOADED, "acting", model)
                elapsed = time.monotonic() - acting_since if acting_since is not None else 0.0
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
            # the LeRobot policy server has no unload call: a loaded policy stays on the GPU
            self._publish_model(
                ModelStatus.LOADED if self._policy_resident else ModelStatus.UNLOADED,
                "kept by the policy server"
                if self._policy_resident
                else "run ended before loading",
                model,
            )
        total = time.monotonic() - started
        acting = time.monotonic() - acting_since if acting_since is not None else 0.0
        result.actions_executed = self._commands
        # the rate over the acting window only: loading time would otherwise halve it
        result.mean_rate_hz = float(self._commands / acting) if acting > 0 else 0.0
        result.success = reason != "client exited" and not reason.startswith("no actions")
        result.message = (
            f"{reason} after {acting:.0f} s of acting, {total:.0f} s in all "
            f"({self._commands} commands)"
        )
        if reason == "canceled":
            handle.canceled()
        elif result.success:
            handle.succeed()
        else:
            handle.abort()
        self.get_logger().info(result.message)
        return result

    def _go_start_pose(self, env: dict[str, str]) -> None:
        """Park the arm where the checkpoint's training episodes started (MOTION, through IDLE)."""
        try:
            pose = parse_start_pose(env.get("VLA_START_POSE", ""))
        except ValueError as exc:
            self.get_logger().warn(f"start pose ignored: {exc}")
            return
        if not pose or not self._set_mode.wait_for_service(timeout_sec=3.0):
            return
        for mode in (ControlMode.IDLE, ControlMode.MOTION):
            request = SetControlMode.Request()
            request.mode, request.requester, request.reason = mode, "skill_executor", "start pose"
            self._call(self._set_mode.call_async(request), 5.0)
        goal = FollowJointTrajectory.Goal()
        goal.trajectory.joint_names = list(ARM_JOINTS)
        point = JointTrajectoryPoint(positions=pose)
        point.time_from_start = Duration(sec=3)
        goal.trajectory.points = [point]
        if self._trajectory.wait_for_server(timeout_sec=3.0):
            sent = self._trajectory.send_goal_async(goal)
            if self._call(sent, 5.0) and sent.result().accepted:
                self._call(sent.result().get_result_async(), 15.0)
        gripper = env.get("VLA_START_GRIPPER_DEG", "")
        if gripper and self._gripper.wait_for_server(timeout_sec=3.0):
            g = ParallelGripperCommand.Goal()
            g.command.name, g.command.position, g.command.effort = (
                ["gripper"],
                [math.radians(float(gripper))],
                [5.0],
            )
            sent = self._gripper.send_goal_async(g)
            if self._call(sent, 5.0) and sent.result().accepted:
                self._call(sent.result().get_result_async(), 5.0)
        self.get_logger().info(f"start pose reached: {env.get('VLA_START_POSE')} deg")

    @staticmethod
    def _call(future, timeout: float) -> bool:
        done = threading.Event()
        future.add_done_callback(lambda _f: done.set())
        return done.wait(timeout)

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
