"""mode_manager: owns /cognibot/set_mode and publishes the latched /cognibot/mode.

Every accepted transition is one STRICT switch_controller call, so exactly one arm commander's
controller set is active. Publishes IDLE on startup after aligning the controllers.
"""

from __future__ import annotations

import threading
from pathlib import Path

import rclpy
from ament_index_python.packages import get_package_share_directory
from cognibot_common.qos import TRANSIENT_LOCAL
from cognibot_interfaces.msg import ControlMode
from cognibot_interfaces.srv import SetControlMode
from controller_manager_msgs.srv import ListControllers, SwitchController
from rcl_interfaces.msg import ParameterDescriptor
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node

from cognibot_motion.mode_logic import MODE_NAMES, ModeError, load_mode_table


class ModeManager(Node):
    def __init__(self) -> None:
        super().__init__("mode_manager")
        default_table = str(
            Path(get_package_share_directory("cognibot_motion")) / "config" / "modes.yaml"
        )
        self.declare_parameter(
            "modes_file", default_table, ParameterDescriptor(description="mode → controllers YAML")
        )
        self.declare_parameter(
            "switch_timeout_s",
            3.0,
            ParameterDescriptor(description="controller_manager switch timeout"),
        )
        self.table = load_mode_table(self.get_parameter("modes_file").value)
        self._lock = threading.Lock()
        self._mode = ControlMode.IDLE
        group = ReentrantCallbackGroup()
        self._switch = self.create_client(
            SwitchController, "/controller_manager/switch_controller", callback_group=group
        )
        self._list = self.create_client(
            ListControllers, "/controller_manager/list_controllers", callback_group=group
        )
        self._startup_deadline = self.get_clock().now().nanoseconds + int(60e9)
        self._last_states: dict[str, str] = {}
        self._pub = self.create_publisher(ControlMode, "/cognibot/mode", TRANSIENT_LOCAL)
        self.create_service(
            SetControlMode, "/cognibot/set_mode", self._on_set_mode, callback_group=group
        )
        # Align controllers with IDLE once controller_manager is up, then publish.
        self._startup = self.create_timer(0.5, self._startup_align, callback_group=group)

    def _startup_align(self) -> None:
        # Spawners load controllers one by one; act only once every managed controller exists
        # (or after the deadline, with whatever is loaded).
        if not self._switch.service_is_ready() or not self._list.service_is_ready():
            return
        states = self._controller_states()
        missing = [c for c in self.table.managed if c not in states]
        # Spawners also activate: wait until the set is complete and unchanged between polls.
        settled = not missing and states == self._last_states
        self._last_states = states
        if not settled and self.get_clock().now().nanoseconds < self._startup_deadline:
            return
        self._startup.cancel()
        if missing:
            self.get_logger().warn(f"controllers never loaded: {missing}")
        activate = list(self.table.active[ControlMode.IDLE])
        deactivate = [c for c in self.table.managed if c not in activate]
        ok, message = self._call_switch(activate, deactivate)
        if not ok:
            self.get_logger().warn(f"startup controller alignment failed: {message}")
        self._publish(ControlMode.IDLE, "mode_manager", "startup")

    def _on_set_mode(self, request, response):
        with self._lock:
            try:
                activate, deactivate = self.table.switch(self._mode, request.mode)
            except ModeError as exc:
                return self._reply(response, False, str(exc))
            if request.mode == self._mode:
                return self._reply(response, True, f"already {MODE_NAMES[self._mode]}")
            ok, message = self._call_switch(activate, deactivate)
            if not ok:
                return self._reply(response, False, f"switch_controller failed: {message}")
            self._publish(request.mode, request.requester, request.reason)
            return self._reply(response, True, f"now {MODE_NAMES[self._mode]}")

    def _reply(self, response, success: bool, message: str):
        response.success = success
        response.message = message
        response.active_mode = self._mode
        if not success:
            self.get_logger().warn(message)
        return response

    def _controller_states(self) -> dict[str, str]:
        done = threading.Event()
        future = self._list.call_async(ListControllers.Request())
        future.add_done_callback(lambda _f: done.set())
        if not done.wait(2.0) or future.result() is None:
            return {}
        return {c.name: c.state for c in future.result().controller}

    def _call_switch(self, activate: list[str], deactivate: list[str]) -> tuple[bool, str]:
        timeout = float(self.get_parameter("switch_timeout_s").value)
        if not self._switch.wait_for_service(timeout_sec=timeout):
            return False, "controller_manager not available"
        # STRICT rejects no-op requests, so only switch controllers whose state must change.
        states = self._controller_states()
        activate = [c for c in activate if states.get(c) == "inactive"]
        deactivate = [c for c in deactivate if states.get(c) == "active"]
        if not activate and not deactivate:
            return True, "no change"
        request = SwitchController.Request()
        request.activate_controllers = activate
        request.deactivate_controllers = deactivate
        request.strictness = SwitchController.Request.STRICT
        request.activate_asap = True
        request.timeout.sec = int(timeout)
        done = threading.Event()
        future = self._switch.call_async(request)
        future.add_done_callback(lambda _f: done.set())
        if not done.wait(timeout + 1.0) or future.result() is None:
            return False, "switch_controller timed out"
        return future.result().ok, future.result().message

    def _publish(self, mode: int, requester: str, reason: str) -> None:
        self._mode = mode
        msg = ControlMode()
        msg.stamp = self.get_clock().now().to_msg()
        msg.mode = mode
        msg.requester = requester
        msg.reason = reason
        self._pub.publish(msg)
        self.get_logger().info(f"mode {MODE_NAMES[mode]} ({requester}: {reason})")


def main() -> None:
    rclpy.init()
    node = ModeManager()
    executor = MultiThreadedExecutor(num_threads=2)
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
