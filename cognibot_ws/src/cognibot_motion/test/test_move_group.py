"""Launch test: MoveIt 2 + pick_ik plans and executes on the simulated SO-101.

1. move_group starts and serves /move_action.
2. move_to_point (MoveItPy in a subprocess) plans and executes home, then an IK goal 10 cm in
   front of the home end-effector position.
3. The executed end-effector position (from /joint_states) is within 1 cm of the target.
"""

import json
import subprocess
import sys
import unittest
from pathlib import Path

import launch
import launch_testing.actions
import pytest
import rclpy
from ament_index_python.packages import get_package_share_directory
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from moveit_msgs.action import MoveGroup
from rclpy.action import ActionClient

ROBOT = "so101"
# 10 cm in front of the home end-effector position (0.251, 0, 0.142) along the base x axis.
TARGET = (0.35, 0.0, 0.142)
TOLERANCE_M = 0.01


def _include(package: str, launch_file: str, **args: str) -> IncludeLaunchDescription:
    path = Path(get_package_share_directory(package)) / "launch" / launch_file
    return IncludeLaunchDescription(
        PythonLaunchDescriptionSource(str(path)), launch_arguments=args.items()
    )


@pytest.mark.launch_test
def generate_test_description():
    return launch.LaunchDescription(
        [
            _include("cognibot_sim", "sim.launch.py", robot=ROBOT, headless="true"),
            _include("cognibot_motion", "move_group.launch.py", robot=ROBOT),
            launch_testing.actions.ReadyToTest(),
        ]
    )


class TestMoveGroup(unittest.TestCase):
    def test_1_move_group_serves_move_action(self):
        rclpy.init()
        node = rclpy.create_node("test_move_group_client")
        try:
            client = ActionClient(node, MoveGroup, "/move_action")
            self.assertTrue(client.wait_for_server(timeout_sec=60.0), "move_group not serving")
        finally:
            node.destroy_node()
            rclpy.shutdown()

    def test_2_plan_and_execute_ik_goal(self):
        x, y, z = TARGET
        cmd = [
            sys.executable,
            "-m",
            "cognibot_motion.move_to_point",
            "--robot",
            ROBOT,
            "--x",
            str(x),
            "--y",
            str(y),
            "--z",
            str(z),
            "--home-first",
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        lines = [ln for ln in proc.stdout.splitlines() if ln.startswith("{")]
        self.assertTrue(lines, f"no result from move_to_point:\n{proc.stderr[-2000:]}")
        self.assertEqual(proc.returncode, 0, proc.stderr[-2000:])
        result = json.loads(lines[-1])
        print(result)
        self.assertEqual(result.get("home"), "SUCCEEDED", result)
        self.assertTrue(result.get("ik"), result)
        self.assertEqual(result.get("execution"), "SUCCEEDED", result)
        self.assertLess(result["ee_error_m"], TOLERANCE_M, result)
