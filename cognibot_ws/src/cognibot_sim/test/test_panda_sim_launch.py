"""Launch test for sim.launch.py with robot:=panda.

Asserts:
1. Required controllers are spawned and in expected states:
   - joint_state_broadcaster: active
   - joint_trajectory_controller: active
   - gripper_controller: active
   - arm_position_controller: inactive
2. /joint_states is published at >= 100 Hz.
3. A 2-second JTC trajectory goal to home_pose succeeds and reaches within 0.05 rad.
"""

import time
import unittest
from pathlib import Path

import launch
import launch_testing
import launch_testing.actions
import pytest
import rclpy
from ament_index_python.packages import get_package_share_directory
from builtin_interfaces.msg import Duration
from cognibot_common.robot_registry import load_robot
from control_msgs.action import FollowJointTrajectory
from controller_manager_msgs.srv import ListControllers
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from rclpy.action import ActionClient
from sensor_msgs.msg import JointState
from trajectory_msgs.msg import JointTrajectoryPoint


@pytest.mark.launch_test
def generate_test_description():
    sim_launch_path = Path(get_package_share_directory("cognibot_sim")) / "launch/sim.launch.py"

    sim_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(str(sim_launch_path)),
        launch_arguments={
            "robot": "panda",
            "headless": "true",
            "use_sim_time": "true",
        }.items(),
    )

    return (
        launch.LaunchDescription(
            [
                sim_launch,
                launch_testing.actions.ReadyToTest(),
            ]
        ),
        {"sim_launch": sim_launch},
    )


class TestPandaSimLaunch(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        rclpy.init()

    @classmethod
    def tearDownClass(cls):
        rclpy.shutdown()

    def setUp(self):
        self.node = rclpy.create_node("test_panda_sim_launch_client")

    def tearDown(self):
        self.node.destroy_node()

    def test_panda_controllers_and_trajectory(self):
        robot_cfg = load_robot("panda")
        expected_home = robot_cfg.home_pose
        arm_joints = robot_cfg.arm_joints

        # 1. Wait for controller_manager service
        cli_list = self.node.create_client(ListControllers, "/controller_manager/list_controllers")
        start_time = time.time()
        while not cli_list.wait_for_service(timeout_sec=1.0):
            if time.time() - start_time > 30.0:
                self.fail("Timed out waiting for /controller_manager/list_controllers service")

        # Query controllers until all 4 expected controllers are present and in target states
        controllers_ready = False
        controllers_map = {}
        for _ in range(60):
            req = ListControllers.Request()
            future = cli_list.call_async(req)
            rclpy.spin_until_future_complete(self.node, future, timeout_sec=2.0)
            if future.result() is not None:
                controllers_map = {c.name: c.state for c in future.result().controller}
                if (
                    controllers_map.get("joint_state_broadcaster") == "active"
                    and controllers_map.get("joint_trajectory_controller") == "active"
                    and controllers_map.get("gripper_controller") == "active"
                    and controllers_map.get("arm_position_controller") == "inactive"
                ):
                    controllers_ready = True
                    break
            time.sleep(0.5)

        self.assertTrue(
            controllers_ready,
            f"Controllers did not enter expected states in time. Current states: {controllers_map}",
        )

        # 2. Collect /joint_states to measure rate
        joint_state_msgs = []

        def js_cb(msg: JointState):
            joint_state_msgs.append(msg)

        _sub_js = self.node.create_subscription(JointState, "/joint_states", js_cb, 100)

        start_wait = time.time()
        while len(joint_state_msgs) < 100 and (time.time() - start_wait) < 5.0:
            rclpy.spin_once(self.node, timeout_sec=0.05)

        self.assertGreaterEqual(
            len(joint_state_msgs),
            50,
            f"Expected at least 50 joint_states messages, received {len(joint_state_msgs)}",
        )

        stamps = [m.header.stamp.sec + m.header.stamp.nanosec * 1e-9 for m in joint_state_msgs]
        duration = stamps[-1] - stamps[0]
        if duration > 0.1:
            rate = (len(stamps) - 1) / duration
            self.assertGreaterEqual(rate, 90.0, f"Rate {rate:.1f} Hz is below target")

        # 3. Send 2.0s JTC goal to home_pose
        action_client = ActionClient(
            self.node, FollowJointTrajectory, "/joint_trajectory_controller/follow_joint_trajectory"
        )
        self.assertTrue(
            action_client.wait_for_server(timeout_sec=10.0),
            "Timed out waiting for the /joint_trajectory_controller/follow_joint_trajectory "
            "action server",
        )

        goal_msg = FollowJointTrajectory.Goal()
        goal_msg.trajectory.joint_names = list(arm_joints)

        point = JointTrajectoryPoint()
        point.positions = list(expected_home)
        point.time_from_start = Duration(sec=2, nanosec=0)
        goal_msg.trajectory.points = [point]

        send_future = action_client.send_goal_async(goal_msg)
        rclpy.spin_until_future_complete(self.node, send_future, timeout_sec=5.0)
        goal_handle = send_future.result()
        self.assertIsNotNone(goal_handle, "Failed to get goal handle")
        self.assertTrue(goal_handle.accepted, "Trajectory goal was rejected")

        res_future = goal_handle.get_result_async()
        rclpy.spin_until_future_complete(self.node, res_future, timeout_sec=6.0)
        action_res = res_future.result()
        self.assertIsNotNone(action_res, "Trajectory goal timed out or failed to return result")
        self.assertEqual(
            action_res.result.error_code,
            FollowJointTrajectory.Result.SUCCESSFUL,
            f"Goal execution failed with error code: {action_res.result.error_code}",
        )

        latest_js = None

        def latest_cb(msg: JointState):
            nonlocal latest_js
            latest_js = msg

        _sub_latest = self.node.create_subscription(JointState, "/joint_states", latest_cb, 10)
        for _ in range(20):
            rclpy.spin_once(self.node, timeout_sec=0.1)
            if latest_js is not None:
                break

        self.assertIsNotNone(latest_js, "Failed to receive /joint_states after goal execution")
        name_to_pos = dict(zip(latest_js.name, latest_js.position, strict=False))

        for j_name, exp_pos in zip(arm_joints, expected_home, strict=False):
            actual_pos = name_to_pos.get(j_name)
            self.assertIsNotNone(actual_pos, f"Joint {j_name} not found in /joint_states")
            diff = abs(actual_pos - exp_pos)
            self.assertLessEqual(
                diff,
                0.05,
                f"Joint {j_name} error {diff:.4f} rad exceeds 0.05 rad "
                f"(actual: {actual_pos:.4f}, exp: {exp_pos:.4f})",
            )
