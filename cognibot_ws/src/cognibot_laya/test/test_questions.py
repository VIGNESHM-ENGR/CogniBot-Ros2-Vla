from cognibot_laya.questions import (
    MAX_OPTIONS,
    MOTIONS,
    NONE_LABEL,
    PRIMITIVES,
    guard_questions,
    legal_primitives,
    legal_skills,
    primitive_questions,
    questions_fit,
    skill_questions,
)


def test_skill_questions_offer_the_legal_skills_and_the_candidates():
    questions = skill_questions(["red cube", "black rectangle"])
    assert "fetch" in questions["skill"]["criteria"]
    assert "place" not in questions["skill"]["criteria"]
    assert list(questions["object"]["criteria"]) == ["red cube", "black rectangle", NONE_LABEL]


def test_an_empty_gripper_cannot_place_and_a_full_one_cannot_fetch():
    assert "place" not in legal_skills(holding=False) and "fetch" in legal_skills(holding=False)
    assert "fetch" not in legal_skills(holding=True) and "place" in legal_skills(holding=True)
    assert "done" in legal_skills(True) and "done" in legal_skills(False)


def test_grasp_and_release_are_offered_only_when_they_can_happen():
    far = legal_primitives(within_reach=False, gripper_open=True)
    assert list(far) == MOTIONS
    near = legal_primitives(within_reach=True, gripper_open=True)
    assert list(near) == ["grasp", "done"]  # a 2.5 cm jog inside a 3 cm reach only overshoots
    closed = legal_primitives(within_reach=False, gripper_open=False)
    assert "release" in closed and "grasp" not in closed


def test_skill_questions_cap_the_label_list():
    questions = skill_questions([f"cube {i}" for i in range(30)])
    assert len(questions["object"]["criteria"]) == MAX_OPTIONS
    assert NONE_LABEL in questions["object"]["criteria"]


def test_primitive_questions_offer_every_primitive_unless_masked():
    assert set(primitive_questions()["move"]["criteria"]) == set(PRIMITIVES)
    masked = legal_primitives(within_reach=False, gripper_open=True)
    assert set(primitive_questions(masked)["move"]["criteria"]) == set(MOTIONS)


def test_every_question_set_fits_the_marker_budget():
    assert questions_fit(skill_questions(["red cube", "green cube", "black rectangle"]))
    assert questions_fit(skill_questions(["black rectangle", "red cube"], holding=True))
    assert questions_fit(primitive_questions())
    assert questions_fit(guard_questions())


def test_an_overlong_option_set_is_rejected():
    bad = {"q": {"type": "choice", "criteria": {f"o{i}": "x" * 200 for i in range(12)}}}
    assert not questions_fit(bad)


def test_a_blocked_motion_is_not_offered_again():
    options = legal_primitives(False, True, frozenset({"down"}))
    assert "down" not in options and "left" in options
    assert list(legal_primitives(True, True, frozenset({"grasp", "done"}))) == ["done"]
