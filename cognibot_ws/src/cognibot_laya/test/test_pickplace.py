import math

from cognibot_laya.pickplace import (
    IN_GRIPPER,
    MISSED,
    ON_TABLE,
    PLACED,
    SLIPPED,
    Area,
    Geometry,
    jaw_centre,
    jog_distance,
    plan_stage,
    stage_state,
    toward_base,
    within,
)
from cognibot_laya.state import Pose, SceneObject

G = Geometry()
AREA = Area("black rectangle", 0.307, 0.197, 0.002, 0.080, 0.056)
CUBE = SceneObject("green cube", 0.274, -0.020, 0.012, 0.025)
GX, GY = toward_base(CUBE.x, CUBE.y, G.grasp_offset)


def stage(gripper, gripper_open=True, was_held=False, cube=CUBE, previous=""):
    return plan_stage(cube, gripper, gripper_open, was_held, AREA, previous, G)


def test_far_from_the_cube_the_arm_first_goes_above_it():
    s = stage(Pose(0.255, 0.0, 0.072))
    assert s.name == "move above the green cube" and s.cube_state == ON_TABLE
    assert math.isclose(s.aim.z, CUBE.z + G.hover) and s.action == ""


def test_aligned_above_the_cube_it_descends_and_may_grasp_at_the_bottom():
    s = stage(Pose(GX, GY, 0.07))
    assert s.name == "lower onto the green cube" and s.action == "grasp"
    assert not within(s, Pose(GX, GY, 0.07))
    assert within(s, Pose(GX, GY, CUBE.z + 0.005))


def test_a_descent_tolerates_drift_up_to_the_realign_threshold():
    drifted = Pose(GX + 0.02, GY, 0.04)  # 2 cm off: inside realign, outside align
    assert stage(drifted, previous="lower onto the green cube").name.startswith("lower onto")
    assert stage(drifted, previous="move above the green cube").name.startswith("move above")


def test_a_closed_gripper_around_the_cube_holds_it_and_lifts_first():
    jaws_at_cube = Pose(GX, GY, CUBE.z)
    assert jaw_centre(jaws_at_cube, G).distance_to(Pose(CUBE.x, CUBE.y, CUBE.z)) < 0.001
    s = stage(jaws_at_cube, gripper_open=False)
    assert s.cube_state == IN_GRIPPER and s.name == "lift the green cube"


def test_a_lifted_cube_is_carried_above_the_target_then_lowered_and_released():
    lifted = SceneObject("green cube", CUBE.x, CUBE.y, 0.07, 0.083)
    s = stage(Pose(GX, GY, 0.07), gripper_open=False, cube=lifted)
    assert s.name == "carry the green cube above the black rectangle"
    dx, dy = toward_base(AREA.x, AREA.y, G.grasp_offset)
    over = SceneObject("green cube", *toward_base(dx, dy, -G.grasp_offset), 0.07, 0.083)
    s = stage(Pose(dx, dy, 0.07), gripper_open=False, cube=over)
    assert s.name == "lower the green cube onto the black rectangle" and s.action == "release"


def test_a_grasp_that_closed_on_nothing_is_released_and_retried():
    s = stage(Pose(GX, GY + 0.05, CUBE.z), gripper_open=False)
    assert s.cube_state == MISSED and s.action == "release"
    assert within(s, Pose(0.0, 0.0, 1.0))  # release is available wherever the gripper is


def test_a_cube_that_fell_while_carried_is_reported_and_re_approached():
    fallen = SceneObject("green cube", 0.29, 0.10, 0.012, 0.025)
    s = stage(Pose(0.28, 0.15, 0.08), gripper_open=False, was_held=True, cube=fallen)
    assert s.cube_state == SLIPPED and s.action == "release"
    s = stage(Pose(0.28, 0.15, 0.08), gripper_open=True, was_held=True, cube=fallen)
    assert s.cube_state == SLIPPED and s.name == "move above the green cube"


def test_a_cube_inside_the_area_with_an_open_gripper_is_placed():
    placed = SceneObject("green cube", 0.30, 0.19, 0.012, 0.025)
    s = stage(Pose(0.28, 0.18, 0.02), cube=placed)
    assert s.cube_state == PLACED and s.action == "done" and s.name.startswith("move up")


def test_the_model_state_carries_positions_and_the_worded_direction():
    s = stage(Pose(0.255, 0.0, 0.072))
    st = stage_state(
        "Put the green cube on the black rectangle.", s, CUBE, Pose(0.255, 0, 0.072), True, AREA
    )
    assert st["cube"] == {
        "label": "green cube",
        "state": ON_TABLE,
        "position_cm": {"x": 27.4, "y": -2.0, "z": 1.2},
    }
    assert st["target_area"]["size_cm"] == {"x": 16.0, "y": 11.2}
    assert "right" in st["go_to"]
    assert "position_cm" not in stage_state("t", s, CUBE, Pose(0, 0, 0), True, AREA, False)["cube"]


def test_a_jog_stops_at_the_aim_along_its_axis_but_a_wrong_way_jog_is_a_full_step():
    here, aim = Pose(0.30, 0.0, 0.10), Pose(0.30, 0.0, 0.09)
    assert math.isclose(jog_distance("down", here, aim, 0.025), 0.01)
    assert math.isclose(jog_distance("up", here, aim, 0.025), 0.025)
    assert math.isclose(jog_distance("down", here, Pose(0.3, 0.0, 0.0999), 0.025), 0.003)
