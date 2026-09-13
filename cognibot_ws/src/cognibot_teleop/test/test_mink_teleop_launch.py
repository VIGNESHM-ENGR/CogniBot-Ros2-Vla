"""Launch test: TeleopCommand jogs the simulated arm through mink_teleop and the safety filter.

Sends -X (towards the base) at full deflection for 1.5 s, then nothing; checks TELEOP was
requested, the end-effector target advanced along -X, joint commands streamed to the filter at
>= 50 Hz, the arm moved, and motion stops after the dead-man.
"""

import unittest
from pathlib import Path

import launch
import launch_testing.actions
import pytest
import rclpy
from ament_index_python.packages import get_package_share_directory
from cognibot_interfaces.msg import ControlMode, TeleopCommand
from geometry_msgs.msg import PoseStamped
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.actions import Node
from rclpy.qos import DurabilityPolicy, QoSProfile, qos_profile_sensor_data
from sensor_msgs.msg import JointState


@pytest.mark.launch_test
def generate_test_description():
    sim = Path(get_package_share_directory("cognibot_sim")) / "launch" / "sim.launch.py"
    teleop_cfg = Path(get_package_share_directory("cognibot_teleop")) / "config" / "teleop.yaml"
    return launch.LaunchDescription(
        [
            IncludeLaunchDescription(
                PythonLaunchDescriptionSource(str(sim)),
                launch_arguments={"robot": "so101", "headless": "true"}.items(),
            ),
            Node(package="cognibot_motion", executable="mode_manager", output="screen"),
            Node(package="cognibot_motion", executable="safety_filter", output="screen"),
            Node(
                package="cognibot_teleop",
                executable="mink_teleop",
                output="screen",
                parameters=[str(teleop_cfg)],
            ),
            launch_testing.actions.ReadyToTest(),
        ]
    )


class TestMinkTeleop(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        rclpy.init()
        cls.node = rclpy.create_node("test_mink_teleop")
        cls.pub = cls.node.create_publisher(TeleopCommand, "/cognibot/teleop/cmd", 10)
        cls.joints = {}
        cls.targets = []
        cls.commands = []
        cls.modes = []
        cls.node.create_subscription(
            JointState,
            "/joint_states",
            lambda m: cls.joints.update(zip(m.name, m.position, strict=False)),
            qos_profile_sensor_data,
        )
        cls.node.create_subscription(
            PoseStamped, "/cognibot/teleop/ee_target", lambda m: cls.targets.append(m), 10
        )
        cls.node.create_subscription(
            JointState, "/cognibot/joint_command", lambda m: cls.commands.append(m), 10
        )
        cls.node.create_subscription(
            ControlMode,
            "/cognibot/mode",
            lambda m: cls.modes.append(m.mode),
            QoSProfile(depth=1, durability=DurabilityPolicy.TRANSIENT_LOCAL),
        )

    @classmethod
    def tearDownClass(cls):
        cls.node.destroy_node()
        rclpy.shutdown()

    def _spin(self, seconds):
        end = self.node.get_clock().now().nanoseconds + int(seconds * 1e9)
        while self.node.get_clock().now().nanoseconds < end:
            rclpy.spin_once(self.node, timeout_sec=0.02)

    def _jog(self, x, seconds):
        end = self.node.get_clock().now().nanoseconds + int(seconds * 1e9)
        while self.node.get_clock().now().nanoseconds < end:
            msg = TeleopCommand()
            msg.header.frame_id = "base_link"
            msg.linear.x = x
            self.pub.publish(msg)
            self._spin(1 / 30)

    def test_jog_minus_x(self):
        self._spin(4.0)
        self.assertIn("shoulder_pan", self.joints, "no joint states")
        start_lift = self.joints["shoulder_lift"]

        # The zero pose sits outside the placeholder workspace shell (r_max 0.38 until P2-T07),
        # so jog inwards where there is room.
        self._jog(-1.0, 1.5)
        self.assertIn(ControlMode.TELEOP, self.modes, "teleop did not request TELEOP")
        self.assertGreater(len(self.targets), 20, "no EE targets published")
        dx = self.targets[0].pose.position.x - self.targets[-1].pose.position.x
        self.assertGreater(dx, 0.05, f"EE target advanced only {dx:.3f} m along -X")

        rate = len(self.commands) / 1.5
        self.assertGreater(rate, 50.0, f"joint_command rate {rate:.0f} Hz")
        self.assertNotAlmostEqual(self.joints["shoulder_lift"], start_lift, delta=0.02)

        self._spin(1.0)  # dead-man: target must stop drifting
        n = len(self.targets)
        self._spin(0.5)
        drift = abs(self.targets[-1].pose.position.x - self.targets[n - 1].pose.position.x)
        self.assertLess(drift, 1e-3, f"EE target kept moving {drift:.4f} m after dead-man")
        print(f"dx {dx:.3f} m, joint_command {rate:.0f} Hz, targets {len(self.targets)}")
