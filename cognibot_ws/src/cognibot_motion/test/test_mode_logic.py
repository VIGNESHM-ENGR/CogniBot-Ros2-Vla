"""Mode table: transitions and STRICT switch lists (no ROS graph)."""

from pathlib import Path

import pytest
from cognibot_interfaces.msg import ControlMode
from cognibot_motion.mode_logic import ModeError, load_mode_table

TABLE = Path(__file__).resolve().parents[1] / "config" / "modes.yaml"


@pytest.fixture(scope="module")
def table():
    return load_mode_table(TABLE)


def test_idle_to_teleop_swaps_commanders(table):
    activate, deactivate = table.switch(ControlMode.IDLE, ControlMode.TELEOP)
    assert activate == ["arm_position_controller"]
    assert sorted(deactivate) == ["gripper_controller", "joint_trajectory_controller"]


def test_teleop_back_to_idle(table):
    activate, deactivate = table.switch(ControlMode.TELEOP, ControlMode.IDLE)
    assert activate == ["joint_trajectory_controller", "gripper_controller"]
    assert deactivate == ["arm_position_controller"]


def test_idle_to_motion_changes_nothing(table):
    assert table.switch(ControlMode.IDLE, ControlMode.MOTION) == ([], [])


def test_forbidden_transition(table):
    with pytest.raises(ModeError, match="not allowed"):
        table.switch(ControlMode.VLA, ControlMode.TELEOP)


def test_declared_transition(table):
    activate, deactivate = table.switch(ControlMode.TELEOP, ControlMode.MOTION)
    assert "joint_trajectory_controller" in activate
    assert deactivate == ["arm_position_controller"]


def test_unknown_mode(table):
    with pytest.raises(ModeError, match="unknown"):
        table.switch(ControlMode.IDLE, 42)


def test_managed_controllers_cover_every_mode(table):
    assert set(table.managed) == {
        "joint_trajectory_controller",
        "gripper_controller",
        "arm_position_controller",
    }
