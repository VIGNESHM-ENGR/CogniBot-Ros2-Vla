#!/usr/bin/env python3
"""Scripted SO-101 pick-and-place in simulation (no planner): top-down IK + controller goals.

Solves 5-DOF IK on the MuJoCo scene (gripper position plus approach axis pointing down), then
sends each waypoint to joint_trajectory_controller and opens/closes gripper_controller.
Run inside the core image while `sim.launch.py robot:=so101` is up:
    python3 demo_pick_place.py
"""

from __future__ import annotations

import time

import mujoco
import numpy as np
import rclpy
from builtin_interfaces.msg import Duration
from cognibot_common.robot_registry import load_robot
from control_msgs.action import FollowJointTrajectory, ParallelGripperCommand
from rclpy.action import ActionClient
from rclpy.node import Node
from trajectory_msgs.msg import JointTrajectoryPoint

GRIPPER_OPEN = 1.2
GRIPPER_CLOSED = -0.1  # below the cube width so the jaws squeeze (the controller allows stalling)
HOVER = 0.06  # m above the grasp and drop heights
# Soft top-down preference: exact top-down poses are out of reach near the workspace edge.
ORIENTATION_WEIGHT = 0.1
# The gripperframe site sits 2 cm outboard of the jaw centre (MODIFICATIONS.md aligned it to the
# URDF gripper_frame_link), so grasp targets are shifted 2 cm towards the base.
GRASP_OFFSET = 0.02


def solve_top_down_ik(
    model: mujoco.MjModel,
    joints: list[str],
    site: str,
    target: np.ndarray,
    seed: np.ndarray,
    iters: int = 300,
) -> tuple[np.ndarray, float]:
    """Damped least squares on [position error, approach-axis error]; returns (q, pos error m)."""
    data = mujoco.MjData(model)
    qadr = [model.jnt_qposadr[model.joint(j).id] for j in joints]
    dadr = [model.jnt_dofadr[model.joint(j).id] for j in joints]
    lo = np.array([model.jnt_range[model.joint(j).id][0] for j in joints])
    hi = np.array([model.jnt_range[model.joint(j).id][1] for j in joints])
    sid = model.site(site).id
    q = seed.copy()
    jacp, jacr = np.zeros((3, model.nv)), np.zeros((3, model.nv))
    down = np.array([0.0, 0.0, -1.0])
    for _ in range(iters):
        data.qpos[qadr] = q
        mujoco.mj_kinematics(model, data)
        mujoco.mj_comPos(model, data)
        z_axis = data.site_xmat[sid].reshape(3, 3)[:, 2]
        err = np.concatenate(
            [target - data.site_xpos[sid], ORIENTATION_WEIGHT * np.cross(z_axis, down)]
        )
        if np.linalg.norm(err[:3]) < 1e-4 and np.linalg.norm(err[3:]) < 1e-3:
            break
        mujoco.mj_jacSite(model, data, jacp, jacr, sid)
        jac = np.vstack([jacp[:, dadr], ORIENTATION_WEIGHT * jacr[:, dadr]])
        dq = jac.T @ np.linalg.solve(jac @ jac.T + 1e-4 * np.eye(6), err)
        q = np.clip(q + dq, lo, hi)
    data.qpos[qadr] = q
    mujoco.mj_kinematics(model, data)
    return q, float(np.linalg.norm(target - data.site_xpos[sid]))


class PickPlaceDemo(Node):
    def __init__(self) -> None:
        super().__init__("demo_pick_place")
        self.cfg = load_robot("so101")
        self.model = mujoco.MjModel.from_xml_path(str(self.cfg.mjcf.scene))
        self.arm = ActionClient(
            self, FollowJointTrajectory, "/joint_trajectory_controller/follow_joint_trajectory"
        )
        self.gripper = ActionClient(self, ParallelGripperCommand, "/gripper_controller/gripper_cmd")
        self.q = np.array(self.cfg.home_pose)

    def _wait(self, future):
        rclpy.spin_until_future_complete(self, future)
        return future.result()

    def move_arm(self, q: np.ndarray, seconds: float) -> None:
        goal = FollowJointTrajectory.Goal()
        goal.trajectory.joint_names = list(self.cfg.arm_joints)
        point = JointTrajectoryPoint(positions=q.tolist())
        point.time_from_start = Duration(sec=int(seconds), nanosec=int(seconds % 1 * 1e9))
        goal.trajectory.points = [point]
        handle = self._wait(self.arm.send_goal_async(goal))
        self._wait(handle.get_result_async())
        self.q = q

    def move_gripper(self, position: float) -> None:
        goal = ParallelGripperCommand.Goal()
        goal.command.name = [self.cfg.gripper.joint]
        goal.command.position = [position]
        goal.command.effort = [5.0]
        handle = self._wait(self.gripper.send_goal_async(goal))
        self._wait(handle.get_result_async())
        time.sleep(0.5)

    def go_to(self, xyz: np.ndarray, seconds: float, label: str) -> None:
        q, err = solve_top_down_ik(
            self.model, list(self.cfg.arm_joints), self.cfg.ee_site, xyz, self.q
        )
        self.get_logger().info(f"{label}: target {np.round(xyz, 3)} IK error {err * 1000:.1f} mm")
        self.move_arm(q, seconds)

    def run(self) -> None:
        self.arm.wait_for_server()
        self.gripper.wait_for_server()
        cube = self.model.body("green_cube").pos.copy()
        target = self.model.body("blue_target").pos.copy()
        grasp = cube.copy()
        grasp[:2] -= GRASP_OFFSET * cube[:2] / np.linalg.norm(cube[:2])
        drop = target.copy()
        drop[:2] -= GRASP_OFFSET * target[:2] / np.linalg.norm(target[:2])
        drop[2] = cube[2] + 0.012

        self.get_logger().info("Home, open gripper")
        self.move_arm(np.array(self.cfg.home_pose), 2.0)
        self.move_gripper(GRIPPER_OPEN)
        self.go_to(grasp + [0, 0, HOVER], 2.5, "Above cube")
        self.go_to(grasp, 1.5, "Down to cube")
        self.get_logger().info("Close gripper")
        self.move_gripper(GRIPPER_CLOSED)
        self.go_to(grasp + [0, 0, HOVER], 1.5, "Lift")
        self.go_to(drop + [0, 0, HOVER], 2.5, "Carry to target")
        self.go_to(drop, 1.5, "Lower")
        self.get_logger().info("Release")
        self.move_gripper(GRIPPER_OPEN)
        self.go_to(drop + [0, 0, HOVER], 1.5, "Retreat")
        self.move_arm(np.array(self.cfg.home_pose), 2.5)
        self.get_logger().info("Done")


def main() -> None:
    rclpy.init()
    node = PickPlaceDemo()
    try:
        node.run()
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
