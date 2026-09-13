"""Shared MoveIt configuration for launch files, MoveItPy scripts and tests."""

from __future__ import annotations

import tempfile
from pathlib import Path

import yaml
from ament_index_python.packages import get_package_share_directory
from cognibot_common.robot_registry import load_robot
from moveit_configs_utils import MoveItConfigs, MoveItConfigsBuilder

# MoveIt group and tip link per robot (the SRDF lives in the upstream config package).
PLANNING_GROUPS = {"so101": ("manipulator", "gripper_frame_link")}


def build_moveit_config(robot: str) -> MoveItConfigs:
    """Build MoveIt configs for `robot`, overriding kinematics and controllers with ours."""
    if robot not in PLANNING_GROUPS:
        raise ValueError(
            f"No MoveIt configuration for robot '{robot}' (have {list(PLANNING_GROUPS)})"
        )
    cfg = load_robot(robot)
    config_dir = Path(get_package_share_directory("cognibot_motion")) / "config" / robot
    xacro_path = (
        Path(get_package_share_directory("so101_description")) / "urdf" / "so101_arm.urdf.xacro"
    )
    return (
        MoveItConfigsBuilder("so101_arm", package_name=cfg.moveit.config_package)
        .robot_description(
            file_path=str(xacro_path),
            mappings={"variant": "follower", "use_ros2_control": "false"},
        )
        .robot_description_semantic()
        .robot_description_kinematics(file_path=str(config_dir / "kinematics_pick_ik.yaml"))
        .planning_pipelines(pipelines=["ompl"])
        .joint_limits()
        .trajectory_execution(
            file_path=str(config_dir / "moveit_controllers.yaml"),
            moveit_manage_controllers=False,
        )
        .moveit_cpp(file_path=str(config_dir / "moveit_py.yaml"))
        .to_moveit_configs()
    )


def write_moveit_py_params(robot: str, use_sim_time: bool = True) -> Path:
    """Write MoveItPy parameters to a params file and return its path.

    Pass the file as ``MoveItPy(launch_params_filepaths=[...])``. Passing ``use_sim_time`` through
    ``config_dict`` instead aborts moveit_py 2.12 (``qos_overrides./clock`` InvalidParameterValue).
    """
    params = build_moveit_config(robot).to_dict()
    params["use_sim_time"] = use_sim_time
    with tempfile.NamedTemporaryFile("w", prefix="moveit_py_", suffix=".yaml", delete=False) as f:
        yaml.safe_dump({"/**": {"ros__parameters": params}}, f)
    return Path(f.name)
