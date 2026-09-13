"""mink_teleop: Cartesian jogging of the end effector from TeleopCommand messages.

Integrates an end-effector target from normalized velocity commands (dead-man 300 ms), clamps
it to the registry workspace shell and the table, solves differential IK with mink on the
robot MJCF (FrameTask + PostureTask, ConfigurationLimit + VelocityLimit) and streams joint
targets to /cognibot/joint_command, which only the safety filter forwards. Requests TELEOP on
the first command. Collision avoidance joins once the sphere IK model exists (P2-T03).
"""

from __future__ import annotations

import mink
import mujoco
import numpy as np
import rclpy
from cognibot_common.qos import RELIABLE_COMMAND, SENSOR_DATA, TRANSIENT_LOCAL
from cognibot_common.robot_registry import load_robot
from cognibot_interfaces.msg import ControlMode, TeleopCommand
from cognibot_interfaces.srv import SetControlMode
from geometry_msgs.msg import PoseStamped
from rcl_interfaces.msg import ParameterDescriptor
from rclpy.node import Node
from sensor_msgs.msg import JointState

from cognibot_teleop.teleop_math import Workspace, integrate_target


def _desc(text: str) -> ParameterDescriptor:
    return ParameterDescriptor(description=text)


class MinkTeleop(Node):
    def __init__(self) -> None:
        super().__init__("mink_teleop")
        self.declare_parameter("robot", "so101", _desc("registry name"))
        self.declare_parameter("rate_hz", 100.0, _desc("IK and command rate"))
        self.declare_parameter("max_linear_speed", 0.10, _desc("m/s at full deflection"))
        self.declare_parameter("max_angular_speed", 1.0, _desc("rad/s wrist roll"))
        self.declare_parameter("deadman_s", 0.3, _desc("zero velocity after this silence"))
        self.declare_parameter("orientation_cost", 0.1, _desc("soft orientation weight"))
        self.declare_parameter("posture_cost", 0.001, _desc("posture regularization"))
        self.declare_parameter("table_z_min", 0.01, _desc("lowest allowed EE height, m"))
        p = lambda n: self.get_parameter(n).value  # noqa: E731

        self.cfg = load_robot(p("robot"))
        ik_model = self.cfg.mjcf.ik_model
        if not ik_model.is_file():  # sphere model arrives with P2-T03
            ik_model = self.cfg.urdf.parent.parent / "mjcf" / f"{self.cfg.name}.xml"
        self.model = mujoco.MjModel.from_xml_path(str(ik_model))
        self.arm_joints = list(self.cfg.arm_joints)
        self.qadr = [self.model.jnt_qposadr[self.model.joint(j).id] for j in self.arm_joints]
        self.gripper_qadr = self.model.jnt_qposadr[self.model.joint(self.cfg.gripper.joint).id]
        self.dt = 1.0 / float(p("rate_hz"))
        self.max_linear = float(p("max_linear_speed"))
        self.max_angular = float(p("max_angular_speed"))
        self.deadman = float(p("deadman_s"))
        ws = self.cfg.reach.workspace_sphere
        self.workspace = Workspace(np.array(ws.center), ws.r_min, ws.r_max, float(p("table_z_min")))

        self.configuration = mink.Configuration(self.model)
        self.ee_task = mink.FrameTask(
            self.cfg.ee_site,
            "site",
            position_cost=1.0,
            orientation_cost=float(p("orientation_cost")),
            lm_damping=1e-3,
        )
        self.posture = mink.PostureTask(self.model, cost=float(p("posture_cost")))
        vmax = self.cfg.safety.max_joint_velocity
        self.limits = [
            mink.ConfigurationLimit(self.model),
            mink.VelocityLimit(self.model, {j: vmax for j in self.arm_joints}),
        ]

        self._mode = ControlMode.IDLE
        self._joints: dict[str, float] = {}
        self._linear = np.zeros(3)
        self._roll = 0.0
        self._last_cmd = -np.inf
        self._engaged = False
        self._target: mink.SE3 | None = None
        self._gripper = self.cfg.gripper.open
        self._mode_requested = False

        self.create_subscription(JointState, "/joint_states", self._on_joints, SENSOR_DATA)
        self.create_subscription(ControlMode, "/cognibot/mode", self._on_mode, TRANSIENT_LOCAL)
        self.create_subscription(
            TeleopCommand, "/cognibot/teleop/cmd", self._on_command, RELIABLE_COMMAND
        )
        self._cmd_pub = self.create_publisher(
            JointState, "/cognibot/joint_command", RELIABLE_COMMAND
        )
        self._target_pub = self.create_publisher(PoseStamped, "/cognibot/teleop/ee_target", 10)
        self._set_mode = self.create_client(SetControlMode, "/cognibot/set_mode")
        self.create_timer(self.dt, self._tick)
        self.get_logger().info(f"mink_teleop ready on {ik_model.name} ({self.cfg.ee_site})")

    # ───────────── inputs ─────────────

    def _on_joints(self, msg: JointState) -> None:
        self._joints.update(zip(msg.name, msg.position, strict=False))

    def _on_mode(self, msg: ControlMode) -> None:
        self._mode = msg.mode
        if msg.mode != ControlMode.TELEOP:
            self._engaged = False
            self._mode_requested = False

    def _on_command(self, msg: TeleopCommand) -> None:
        self._linear = np.array([msg.linear.x, msg.linear.y, msg.linear.z])
        self._roll = float(np.clip(msg.wrist_roll, -1.0, 1.0))
        self._last_cmd = self._now()
        if msg.gripper == TeleopCommand.GRIPPER_TOGGLE:
            closed = abs(self._gripper - self.cfg.gripper.closed) < 1e-3
            self._gripper = self.cfg.gripper.open if closed else self.cfg.gripper.closed
        elif msg.gripper == TeleopCommand.GRIPPER_OPEN:
            self._gripper = self.cfg.gripper.open
        elif msg.gripper == TeleopCommand.GRIPPER_CLOSE:
            self._gripper = self.cfg.gripper.closed
        if self._mode != ControlMode.TELEOP and not self._mode_requested:
            self._request_teleop()

    def _request_teleop(self) -> None:
        if not self._set_mode.service_is_ready():
            self.get_logger().warn("mode_manager not available; cannot enter TELEOP")
            return
        self._mode_requested = True
        req = SetControlMode.Request()
        req.mode, req.requester, req.reason = ControlMode.TELEOP, "mink_teleop", "jog command"
        self._set_mode.call_async(req).add_done_callback(self._on_mode_reply)

    def _on_mode_reply(self, future) -> None:
        res = future.result()
        if res is None or not res.success:
            self.get_logger().warn(f"TELEOP refused: {res.message if res else 'no reply'}")
            self._mode_requested = False

    # ───────────── loop ─────────────

    def _now(self) -> float:
        return self.get_clock().now().nanoseconds / 1e9

    def _engage(self) -> bool:
        """Seed the IK configuration and target from the measured state."""
        if any(j not in self._joints for j in self.arm_joints):
            return False
        q = self.configuration.q.copy()
        for adr, j in zip(self.qadr, self.arm_joints, strict=True):
            q[adr] = self._joints[j]
        gripper = self._joints.get(self.cfg.gripper.joint, self.cfg.gripper.open)
        q[self.gripper_qadr] = gripper
        self._gripper = (
            self.cfg.gripper.closed
            if abs(gripper - self.cfg.gripper.closed) < abs(gripper - self.cfg.gripper.open)
            else self.cfg.gripper.open
        )
        self.configuration.update(q)
        self.posture.set_target(q)
        self._target = self.configuration.get_transform_frame_to_world(self.cfg.ee_site, "site")
        self._engaged = True
        return True

    def _tick(self) -> None:
        if self._mode != ControlMode.TELEOP:
            return
        if not self._engaged and not self._engage():
            return
        assert self._target is not None
        active = self._now() - self._last_cmd <= self.deadman
        linear = self._linear if active else np.zeros(3)
        roll = self._roll if active else 0.0

        position = integrate_target(
            self._target.translation(), linear, self.max_linear, self.dt, self.workspace
        )
        rotation = self._target.rotation()
        if roll:
            rotation = rotation @ mink.SO3.exp(
                np.array([0.0, 0.0, roll * self.max_angular * self.dt])
            )
        self._target = mink.SE3.from_rotation_and_translation(rotation, position)
        self.ee_task.set_target(self._target)

        velocity = mink.solve_ik(
            self.configuration,
            [self.ee_task, self.posture],
            self.dt,
            "daqp",
            damping=1e-3,
            limits=self.limits,
        )
        self.configuration.integrate_inplace(velocity, self.dt)
        q = self.configuration.q

        cmd = JointState()
        cmd.header.stamp = self.get_clock().now().to_msg()
        cmd.name = self.arm_joints + [self.cfg.gripper.joint]
        cmd.position = [float(q[a]) for a in self.qadr] + [self._gripper]
        self._cmd_pub.publish(cmd)

        pose = PoseStamped()
        pose.header.stamp = cmd.header.stamp
        pose.header.frame_id = self.cfg.base_frame
        pose.pose.position.x, pose.pose.position.y, pose.pose.position.z = position.tolist()
        w, x, y, z = rotation.wxyz.tolist()
        pose.pose.orientation.w, pose.pose.orientation.x = w, x
        pose.pose.orientation.y, pose.pose.orientation.z = y, z
        self._target_pub.publish(pose)


def main() -> None:
    rclpy.init()
    node = MinkTeleop()
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
