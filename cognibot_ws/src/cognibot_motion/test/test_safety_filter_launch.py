"""Launch test: streamed commands reach arm_position_controller only through the safety filter,
only in TELEOP, clamped to joint limits and rate-limited."""

import unittest
from pathlib import Path

import launch
import launch_testing.actions
import pytest
import rclpy
from ament_index_python.packages import get_package_share_directory
from cognibot_interfaces.msg import ControlMode
from cognibot_interfaces.srv import SetControlMode
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.actions import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import JointState
from std_msgs.msg import Float64MultiArray

ARM = ["shoulder_pan", "shoulder_lift", "elbow_flex", "wrist_flex", "wrist_roll", "gripper"]


@pytest.mark.launch_test
def generate_test_description():
    sim = Path(get_package_share_directory("cognibot_sim")) / "launch" / "sim.launch.py"
    return launch.LaunchDescription(
        [
            IncludeLaunchDescription(
                PythonLaunchDescriptionSource(str(sim)),
                launch_arguments={"robot": "so101", "headless": "true"}.items(),
            ),
            Node(package="cognibot_motion", executable="mode_manager", output="screen"),
            Node(package="cognibot_motion", executable="safety_filter", output="screen"),
            launch_testing.actions.ReadyToTest(),
        ]
    )


class TestSafetyFilter(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        rclpy.init()
        cls.node = rclpy.create_node("test_safety_filter")
        cls.cmd = cls.node.create_publisher(JointState, "/cognibot/joint_command", 10)
        cls.forwarded = []
        cls.node.create_subscription(
            Float64MultiArray,
            "/arm_position_controller/commands",
            lambda m: cls.forwarded.append(list(m.data)),
            10,
        )
        cls.joints = {}
        cls.node.create_subscription(
            JointState,
            "/joint_states",
            lambda m: cls.joints.update(zip(m.name, m.position, strict=False)),
            qos_profile_sensor_data,
        )
        cls.set_mode = cls.node.create_client(SetControlMode, "/cognibot/set_mode")
        assert cls.set_mode.wait_for_service(timeout_sec=60.0)

    @classmethod
    def tearDownClass(cls):
        cls.node.destroy_node()
        rclpy.shutdown()

    def _spin(self, seconds):
        end = self.node.get_clock().now().nanoseconds + int(seconds * 1e9)
        while self.node.get_clock().now().nanoseconds < end:
            rclpy.spin_once(self.node, timeout_sec=0.05)

    def _mode(self, mode):
        req = SetControlMode.Request()
        req.mode, req.requester, req.reason = mode, "test", "launch test"
        fut = self.set_mode.call_async(req)
        rclpy.spin_until_future_complete(self.node, fut, timeout_sec=15.0)
        self.assertTrue(fut.result() and fut.result().success, "mode switch failed")

    def _send(self, positions, repeats=10):
        for _ in range(repeats):
            msg = JointState()
            msg.name, msg.position = ARM, positions
            self.cmd.publish(msg)
            self._spin(0.05)

    def test_filter(self):
        self._spin(3.0)
        self.assertTrue(self.joints, "no joint states")
        # IDLE: nothing may reach the controller
        self._send([0.3, 0.0, 0.0, 0.0, 0.0, 0.5])
        self.assertEqual(self.forwarded, [], "commands forwarded outside a streaming mode")

        self._mode(ControlMode.TELEOP)
        self._spin(0.5)
        # a wild target: far beyond limits and far from the current pose
        self._send([10.0, 0.0, 0.0, 0.0, 0.0, 0.0], repeats=20)
        self.assertTrue(self.forwarded, "nothing forwarded in TELEOP")
        pans = [f[0] for f in self.forwarded]
        self.assertLessEqual(max(pans), 1.92, "joint range not enforced")
        steps = [abs(b - a) for a, b in zip(pans, pans[1:], strict=False)]
        self.assertLessEqual(max(steps), 2.0 / 100 + 1e-6, "velocity limit not enforced")
        self._spin(1.5)
        self.assertGreater(self.joints["shoulder_pan"], 0.1, "arm did not follow the stream")

        self._mode(ControlMode.IDLE)
        n = len(self.forwarded)
        self._send([0.0, 0.0, 0.0, 0.0, 0.0, 0.0])
        self.assertEqual(len(self.forwarded), n, "commands forwarded after leaving TELEOP")
        print(f"forwarded {n} commands; max pan {max(pans):.3f}; max step {max(steps):.4f} rad")
