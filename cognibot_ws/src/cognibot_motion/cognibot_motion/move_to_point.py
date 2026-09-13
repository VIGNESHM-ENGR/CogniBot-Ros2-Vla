"""Move the end effector to a Cartesian point with MoveIt 2 + pick_ik (position-only).

    ros2 run cognibot_motion move_to_point --x 0.35 --y 0.0 --z 0.142 [--home-first]

Prints one JSON line with the IK, planning and execution result and the executed end-effector
position error. Runs MoveItPy in its own process: constructing it inside launch_testing's test
thread segfaults moveit_py 2.12.
"""

from __future__ import annotations

import argparse
import gc
import json
import os
import sys
import time

import numpy as np
from geometry_msgs.msg import Pose
from moveit.core.robot_state import RobotState
from moveit.planning import MoveItPy

from cognibot_motion.moveit_config import PLANNING_GROUPS, write_moveit_py_params


def _plan_and_execute(moveit: MoveItPy, arm, goal: RobotState) -> str:
    arm.set_start_state_to_current_state()
    arm.set_goal_state(robot_state=goal)
    plan = arm.plan()
    if not plan:
        return "PLANNING_FAILED"
    return moveit.execute(plan.trajectory, controllers=[]).status


def run(moveit: MoveItPy, robot: str, target: np.ndarray, home: list[float] | None) -> dict:
    group, tip = PLANNING_GROUPS[robot]
    arm = moveit.get_planning_component(group)
    model = moveit.get_robot_model()
    result: dict = {"target": target.tolist()}

    if home is not None:
        home_state = RobotState(model)
        home_state.set_joint_group_positions(group, np.array(home))
        home_state.update()
        result["home"] = _plan_and_execute(moveit, arm, home_state)
        if result["home"] != "SUCCEEDED":
            return result

    goal = RobotState(model)
    if home is not None:
        seed = np.array(home)
    else:
        with moveit.get_planning_scene_monitor().read_only() as scene:
            seed = scene.current_state.get_joint_group_positions(group)
    goal.set_joint_group_positions(group, seed)
    pose = Pose()
    pose.position.x, pose.position.y, pose.position.z = target.tolist()
    pose.orientation.w = 1.0  # ignored: pick_ik runs position-only (rotation_scale 0)
    result["ik"] = bool(goal.set_from_ik(group, pose, tip, 1.0))
    if not result["ik"]:
        return result
    goal.update()
    result["joints"] = np.round(goal.get_joint_group_positions(group), 4).tolist()
    result["execution"] = _plan_and_execute(moveit, arm, goal)

    time.sleep(1.0)  # let /joint_states catch up with the settled controller
    with moveit.get_planning_scene_monitor().read_only() as scene:
        state = scene.current_state
        state.update()
        tip_position = state.get_global_link_transform(tip)[:3, 3]
    result["ee_position"] = np.round(tip_position, 4).tolist()
    result["ee_error_m"] = round(float(np.linalg.norm(tip_position - target)), 5)
    return result


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--robot", default="so101", choices=sorted(PLANNING_GROUPS))
    parser.add_argument("--x", type=float, required=True)
    parser.add_argument("--y", type=float, required=True)
    parser.add_argument("--z", type=float, required=True)
    parser.add_argument("--home-first", action="store_true", help="move to the registry home first")
    parser.add_argument("--no-sim-time", action="store_true", help="use wall clock (real robot)")
    args, _ = parser.parse_known_args(argv)

    from cognibot_common.robot_registry import load_robot

    home = list(load_robot(args.robot).home_pose) if args.home_first else None
    moveit = MoveItPy(
        node_name="move_to_point",
        launch_params_filepaths=[
            str(write_moveit_py_params(args.robot, use_sim_time=not args.no_sim_time))
        ],
    )
    try:
        result = run(moveit, args.robot, np.array([args.x, args.y, args.z]), home)
    finally:
        gc.collect()  # MoveIt objects must be released before shutdown
        moveit.shutdown()
    print(json.dumps(result), flush=True)
    code = 0 if result.get("execution") == "SUCCEEDED" else 1
    # moveit_py 2.12 segfaults in interpreter teardown after shutdown(); skip it once output is out.
    sys.stderr.flush()
    os._exit(code)


if __name__ == "__main__":
    main()
