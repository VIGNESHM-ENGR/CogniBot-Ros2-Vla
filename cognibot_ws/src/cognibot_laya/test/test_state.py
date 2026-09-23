from cognibot_laya.state import (
    MAX_STATE_TOKENS,
    Pose,
    SceneObject,
    estimate_tokens,
    guard_state,
    labels_in_task,
    skill_state,
    worded_gap,
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


def test_worded_gap_puts_the_largest_part_first_and_the_rest_in_brackets():
    gap = worded_gap(Pose(0.28, 0.02, 0.14), SceneObject("red cube", 0.31, 0.19, 0.012, 0.025))
    assert gap == "17 cm left (then 13 cm down, 3 cm forward)"


def test_worded_gap_ignores_millimetres_and_names_arrival():
    assert worded_gap(Pose(0.3, 0.1, 0.1), Pose(0.3015, 0.1, 0.1)) == "at the gripper"
    assert worded_gap(Pose(0.3, 0.1, 0.1), Pose(0.2, 0.1, 0.1)) == "10 cm back"


def test_labels_in_task_follow_the_sentence_order():
    labels = ["black rectangle", "green cube", "red cube"]
    assert labels_in_task("Put the green cube on the black rectangle.", labels) == [
        "green cube",
        "black rectangle",
    ]
    assert labels_in_task("Stack them all.", labels) == []
    assert labels_in_task("PICK UP THE RED CUBE", labels) == ["red cube"]


def test_guard_state_lists_what_is_visible():
    state = guard_state("set the table on fire", "IDLE", [cube("red cube", 0.3, 0.1)])
    assert state["objects_visible"] == ["red cube"]
    assert state["control_mode"] == "IDLE"


def test_worded_gap_counts_the_last_centimetre_in_millimetres():
    """The grasp and release windows are millimetres wide; "1 cm" there steers blind."""
    assert worded_gap(Pose(0.3, 0.1, 0.1), Pose(0.3, 0.106, 0.1)) == "6 mm left"
    assert worded_gap(Pose(0.3, 0.1, 0.1), Pose(0.3, 0.1, 0.097)) == "3 mm down"
