"""safety_filter: the only publisher of /arm_position_controller/commands.

Subscribes /cognibot/joint_command (JointState, any joint order) and /cognibot/mode, enforces
joint ranges and max_joint_velocity from the robot registry and scene, and forwards the result
only in TELEOP, VLA or TWIN. Everything else is dropped and counted in diagnostics.
The collision-sphere distance check joins this node with P2-T03/T05.
"""

from __future__ import annotations

import mujoco
import numpy as np
import rclpy
from cognibot_common.qos import RELIABLE_COMMAND, SENSOR_DATA, TRANSIENT_LOCAL
from cognibot_common.robot_registry import load_robot
from cognibot_interfaces.msg import ControlMode
from diagnostic_msgs.msg import DiagnosticArray, DiagnosticStatus, KeyValue
from rcl_interfaces.msg import ParameterDescriptor
from rclpy.node import Node
from sensor_msgs.msg import JointState
from std_msgs.msg import Float64MultiArray

from cognibot_motion.joint_limiter import JointLimiter

STREAMING_MODES = {ControlMode.TELEOP, ControlMode.VLA, ControlMode.TWIN}


class SafetyFilter(Node):
    def __init__(self) -> None:
        super().__init__("safety_filter")
        self.declare_parameter("robot", "so101", ParameterDescriptor(description="registry name"))
        self.declare_parameter(
            "rate_hz", 100.0, ParameterDescriptor(description="forwarding rate to the controller")
        )
        self.declare_parameter(
            "command_timeout_s",
            0.3,
            ParameterDescriptor(description="hold the last safe target after this silence"),
        )
        self.cfg = load_robot(self.get_parameter("robot").value)
        model = mujoco.MjModel.from_xml_path(str(self.cfg.mjcf.scene))
        # arm_position_controller drives arm + gripper (controllers.yaml); same order here.
        self.joints = list(self.cfg.arm_joints) + [self.cfg.gripper.joint]
        ranges = np.array([model.jnt_range[model.joint(j).id] for j in self.joints])
        self.limiter = JointLimiter(
            self.joints, ranges[:, 0], ranges[:, 1], self.cfg.safety.max_joint_velocity
        )
        self.rate = float(self.get_parameter("rate_hz").value)
        self.timeout = float(self.get_parameter("command_timeout_s").value)

        self._mode = ControlMode.IDLE
        self._current: np.ndarray | None = None
        self._target: np.ndarray | None = None
        self._last_command = 0.0
        self._forwarded = 0
        self._dropped = 0
        self._clamped = 0
        self._rate_limited = 0
        self._last_reason = ""

        self.create_subscription(JointState, "/joint_states", self._on_joints, SENSOR_DATA)
        self.create_subscription(ControlMode, "/cognibot/mode", self._on_mode, TRANSIENT_LOCAL)
        self.create_subscription(
            JointState, "/cognibot/joint_command", self._on_command, RELIABLE_COMMAND
        )
        self._pub = self.create_publisher(
            Float64MultiArray, "/arm_position_controller/commands", RELIABLE_COMMAND
        )
        self._diag = self.create_publisher(DiagnosticArray, "/cognibot/safety/status", 10)
        self.create_timer(1.0 / self.rate, self._tick)
        self.create_timer(1.0, self._publish_diagnostics)
        self.get_logger().info(
            f"safety_filter ready: {len(self.joints)} joints, "
            f"v_max {self.cfg.safety.max_joint_velocity} rad/s, {self.rate:.0f} Hz"
        )

    def _on_joints(self, msg: JointState) -> None:
        current = self.limiter.reorder(list(msg.name), list(msg.position))
        if current is not None:
            self._current = current

    def _on_mode(self, msg: ControlMode) -> None:
        if msg.mode != self._mode:
            self._target = None  # never carry a target across modes
        self._mode = msg.mode

    def _on_command(self, msg: JointState) -> None:
        if self._mode not in STREAMING_MODES:
            self._drop("mode is not TELEOP/VLA/TWIN")
            return
        target = self.limiter.reorder(list(msg.name), list(msg.position))
        if target is None:
            self._drop("command lacks a controlled joint")
            return
        if not np.all(np.isfinite(target)):
            self._drop("command contains NaN/inf")
            return
        self._target = target
        self._last_command = self.get_clock().now().nanoseconds / 1e9

    def _tick(self) -> None:
        if self._mode not in STREAMING_MODES or self._current is None or self._target is None:
            return
        now = self.get_clock().now().nanoseconds / 1e9
        if now - self._last_command > self.timeout:
            self._target = self._current.copy()  # dead-man: hold where we are
        result = self.limiter.apply(self._target, self._current, 1.0 / self.rate)
        if result.clamped_joints:
            self._clamped += 1
            self._last_reason = f"clamped {', '.join(result.clamped_joints)} to joint range"
        if result.rate_limited:
            self._rate_limited += 1
        self._pub.publish(Float64MultiArray(data=result.positions.tolist()))
        self._forwarded += 1

    def _drop(self, reason: str) -> None:
        self._dropped += 1
        self._last_reason = reason

    def _publish_diagnostics(self) -> None:
        status = DiagnosticStatus()
        status.name = "safety_filter"
        status.hardware_id = self.cfg.name
        status.level = DiagnosticStatus.OK if not self._last_reason else DiagnosticStatus.WARN
        status.message = self._last_reason or "ok"
        status.values = [
            KeyValue(key="mode", value=str(self._mode)),
            KeyValue(key="forwarded", value=str(self._forwarded)),
            KeyValue(key="dropped", value=str(self._dropped)),
            KeyValue(key="clamped", value=str(self._clamped)),
            KeyValue(key="rate_limited", value=str(self._rate_limited)),
            KeyValue(key="collision_check", value="not yet (P2-T03)"),
        ]
        msg = DiagnosticArray()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.status = [status]
        self._diag.publish(msg)
        self._last_reason = ""


def main() -> None:
    rclpy.init()
    node = SafetyFilter()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
