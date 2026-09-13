"""Tests for robot_registry loader and schema."""

from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest
from cognibot_common.robot_registry import (
    RobotConfig,
    RobotRegistryError,
    load_robot,
    parse_robot_config,
)


@pytest.fixture
def sample_valid_dict() -> dict:
    return {
        "name": "test_arm",
        "base_frame": "base_link",
        "ee_frame": "gripper_link",
        "ee_site": "gripper_site",
        "arm_joints": ["j1", "j2", "j3"],
        "gripper": {"joint": "gripper", "open": 1.0, "closed": 0.0},
        "home_pose": [0.0, 0.0, 0.0],
        "mjcf": {
            "scene": "scenes/test_scene.xml",
            "ik_model": "robots/test/mjcf/ik.xml",
        },
        "urdf": "robots/test/urdf/test.urdf",
        "controllers": "robots/test/config/controllers.yaml",
        "moveit": {
            "config_package": "test_moveit_config",
            "kinematics_override": "config/test/kinematics.yaml",
        },
        "cameras": {
            "front": {
                "topic": "/camera/front",
                "frame": "front_cam_frame",
                "depth": True,
            }
        },
        "safety": {
            "collision_spheres": "config/test/spheres.yaml",
            "min_distance": 0.02,
            "max_joint_velocity": 1.5,
        },
        "reach": {
            "study_dir": "config/test/reach",
            "workspace_sphere": {
                "center": [0.0, 0.0, 0.1],
                "r_min": 0.05,
                "r_max": 0.35,
            },
        },
        "vla": {
            "lerobot_robot_type": "cognibot_test",
            "checkpoint": "lerobot/test_checkpoint",
        },
    }


def test_load_so101_valid():
    """Verify loading the real so101 robot.yaml succeeds."""
    config = load_robot("so101")
    assert isinstance(config, RobotConfig)
    assert config.name == "so101"
    assert config.base_frame == "base_link"
    assert config.ee_frame == "gripper_frame_link"
    assert config.ee_site == "gripperframe"
    assert config.arm_joints == (
        "shoulder_pan",
        "shoulder_lift",
        "elbow_flex",
        "wrist_flex",
        "wrist_roll",
    )
    assert config.gripper.joint == "gripper"
    assert config.gripper.open == 1.2
    assert config.gripper.closed == 0.0
    assert len(config.home_pose) == 5
    assert isinstance(config.mjcf.scene, Path)
    assert config.mjcf.scene.name == "so101_pick_and_place.xml"
    assert isinstance(config.mjcf.ik_model, Path)
    assert isinstance(config.urdf, Path)
    assert isinstance(config.controllers, Path)
    assert config.moveit.config_package == "so101_moveit_config"
    assert "front" in config.cameras
    assert config.cameras["front"].depth is True
    assert "wrist" in config.cameras
    assert config.cameras["wrist"].depth is False
    assert config.safety.min_distance == 0.01
    assert config.safety.max_joint_velocity == 2.0
    assert config.reach.workspace_sphere.center == (0.0, 0.0, 0.12)
    assert config.vla.lerobot_robot_type == "cognibot_so101"

    # Dataclasses must be frozen
    with pytest.raises(FrozenInstanceError):
        config.name = "mutated"  # type: ignore[misc]


def test_parse_robot_config_success(sample_valid_dict, tmp_path):
    base_dir = tmp_path
    config = parse_robot_config(sample_valid_dict, base_dir)
    assert config.name == "test_arm"
    assert config.mjcf.scene == (base_dir / "scenes/test_scene.xml").resolve()
    assert config.safety.min_distance == 0.02


def test_missing_required_keys(sample_valid_dict, tmp_path):
    """Missing top-level and nested keys must raise RobotRegistryError."""
    # Missing top-level key
    d = dict(sample_valid_dict)
    del d["base_frame"]
    with pytest.raises(RobotRegistryError, match="Missing required key 'base_frame'"):
        parse_robot_config(d, tmp_path)

    # Missing nested gripper key
    d2 = dict(sample_valid_dict)
    d2["gripper"] = {"open": 1.0, "closed": 0.0}
    with pytest.raises(RobotRegistryError, match="Missing required key 'joint'"):
        parse_robot_config(d2, tmp_path)

    # Missing reach workspace_sphere
    d3 = dict(sample_valid_dict)
    d3["reach"] = {"study_dir": "config/test/reach"}
    with pytest.raises(RobotRegistryError, match="Missing required key 'workspace_sphere'"):
        parse_robot_config(d3, tmp_path)


def test_bad_path_nonexistent_robot(tmp_path):
    """Loading a non-existent robot must raise RobotRegistryError."""
    with pytest.raises(RobotRegistryError, match="Robot configuration file not found"):
        load_robot("nonexistent_robot_xyz", sim_share_dir=tmp_path)


def test_bad_path_explicit_file(tmp_path):
    """Explicit registry_path that does not exist must raise RobotRegistryError."""
    fake_path = tmp_path / "does_not_exist.yaml"
    with pytest.raises(RobotRegistryError, match="Robot configuration file not found"):
        load_robot("test", registry_path=fake_path)


def test_invalid_type_formats(sample_valid_dict, tmp_path):
    """Invalid data types must raise RobotRegistryError."""
    d = dict(sample_valid_dict)
    d["arm_joints"] = "not-a-list"
    with pytest.raises(RobotRegistryError, match="'arm_joints' in test_arm must be a list"):
        parse_robot_config(d, tmp_path)

    d2 = dict(sample_valid_dict)
    d2["reach"] = {
        "study_dir": "config/test/reach",
        "workspace_sphere": {"center": [0.0, 0.0], "r_min": 0.05, "r_max": 0.35},
    }
    with pytest.raises(RobotRegistryError, match="'center' in test_arm.reach.workspace_sphere"):
        parse_robot_config(d2, tmp_path)
