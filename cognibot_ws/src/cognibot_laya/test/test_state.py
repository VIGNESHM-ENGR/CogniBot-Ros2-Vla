from cognibot_laya.state import (
    MAX_STATE_TOKENS,
    Pose,
    SceneObject,
    estimate_tokens,
    guard_state,
    primitive_state,
    skill_state,
)


def cube(label: str, x: float, y: float) -> SceneObject:
    return SceneObject(label, x, y, 0.012, 0.025)


def test_skill_state_lists_objects_and_holding():
    state = skill_state("stack the cubes", [cube("red cube", 0.3, 0.1)], held="green cube")
    assert state["task"] == "stack the cubes"
    assert state["holding"] == "green cube"
    assert state["objects"][0]["label"] == "red cube"
    assert state["objects"][0]["x"] == 0.3


def test_skill_state_keeps_the_objects_nearest_the_gripper():
    objects = [cube("far", 0.6, 0.6), cube("near", 0.31, 0.1), cube("middle", 0.4, 0.2)]
    state = skill_state("pick one", objects, gripper=Pose(0.3, 0.1, 0.1), max_objects=2)
    assert [o["label"] for o in state["objects"]] == ["near", "middle"]


def test_skill_state_stays_inside_the_token_budget():
    objects = [cube(f"cube number {i} with a long label", 0.3 + i / 100, 0.1) for i in range(40)]
    state = skill_state("pick one", objects, gripper=Pose(0.3, 0.1, 0.1), max_objects=40)
    assert estimate_tokens(state) <= MAX_STATE_TOKENS
    assert state["objects"], "the budget must not empty the scene"


def test_primitive_state_gives_the_gap_in_centimetres():
    state = primitive_state(
        "pick up the red cube",
        Pose(0.28, 0.02, 0.14),
        SceneObject("red cube", 0.31, 0.19, 0.012, 0.025),
        {"shoulder_pan": -12.4},
    )
    assert state["gap_cm"] == {"forward": 3.0, "left": 17.0, "up": -12.8}
    assert state["distance_cm"] == 21.5
    assert state["within_tolerance"] is False
    assert state["joints_deg"]["shoulder_pan"] == -12.4


def test_primitive_state_reports_arrival_inside_tolerance():
    target = SceneObject("red cube", 0.30, 0.10, 0.05, 0.06)
    state = primitive_state("go", Pose(0.295, 0.10, 0.055), target, {}, tolerance_m=0.02)
    assert state["within_tolerance"] is True


def test_guard_state_lists_what_is_visible():
    state = guard_state("set the table on fire", "IDLE", [cube("red cube", 0.3, 0.1)])
    assert state["objects_visible"] == ["red cube"]
    assert state["control_mode"] == "IDLE"
