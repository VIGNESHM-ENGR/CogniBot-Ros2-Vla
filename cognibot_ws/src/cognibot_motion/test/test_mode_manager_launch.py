"""Launch test: mode_manager switches controllers IDLE → TELEOP → IDLE on the simulated SO-101."""

import unittest
from pathlib import Path

import launch
import launch_testing.actions
import pytest
import rclpy
from ament_index_python.packages import get_package_share_directory
from cognibot_interfaces.msg import ControlMode
from cognibot_interfaces.srv import SetControlMode
from controller_manager_msgs.srv import ListControllers
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.actions import Node
from rclpy.qos import DurabilityPolicy, QoSProfile


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
            launch_testing.actions.ReadyToTest(),
        ]
    )


class TestModeManager(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        rclpy.init()
        cls.node = rclpy.create_node("test_mode_manager")
        cls.set_mode = cls.node.create_client(SetControlMode, "/cognibot/set_mode")
        cls.list_ctrl = cls.node.create_client(
            ListControllers, "/controller_manager/list_controllers"
        )
        cls.modes = []
        cls.node.create_subscription(
            ControlMode,
            "/cognibot/mode",
            lambda m: cls.modes.append(m.mode),
            QoSProfile(depth=1, durability=DurabilityPolicy.TRANSIENT_LOCAL),
        )
        assert cls.set_mode.wait_for_service(timeout_sec=30.0)
        assert cls.list_ctrl.wait_for_service(timeout_sec=30.0)

    @classmethod
    def tearDownClass(cls):
        cls.node.destroy_node()
        rclpy.shutdown()

    def _call(self, client, request):
        future = client.call_async(request)
        rclpy.spin_until_future_complete(self.node, future, timeout_sec=15.0)
        self.assertIsNotNone(future.result(), "service call timed out")
        return future.result()

    def _active(self):
        return {
            c.name
            for c in self._call(self.list_ctrl, ListControllers.Request()).controller
            if c.state == "active"
        }

    def _set(self, mode):
        req = SetControlMode.Request()
        req.mode, req.requester, req.reason = mode, "test", "launch test"
        return self._call(self.set_mode, req)

    def test_idle_teleop_idle(self):
        deadline = self.node.get_clock().now().nanoseconds + int(20e9)
        while not self.modes and self.node.get_clock().now().nanoseconds < deadline:
            rclpy.spin_once(self.node, timeout_sec=0.2)
        self.assertEqual(self.modes[:1], [ControlMode.IDLE], "IDLE not published on startup")
        self.assertIn("joint_trajectory_controller", self._active())

        res = self._set(ControlMode.TELEOP)
        self.assertTrue(res.success, res.message)
        self.assertEqual(res.active_mode, ControlMode.TELEOP)
        active = self._active()
        self.assertIn("arm_position_controller", active)
        self.assertNotIn("joint_trajectory_controller", active)

        res = self._set(ControlMode.VLA)
        self.assertFalse(res.success, "TELEOP → VLA must be rejected")

        res = self._set(ControlMode.IDLE)
        self.assertTrue(res.success, res.message)
        active = self._active()
        self.assertIn("joint_trajectory_controller", active)
        self.assertNotIn("arm_position_controller", active)
        print(f"modes published: {self.modes}")
