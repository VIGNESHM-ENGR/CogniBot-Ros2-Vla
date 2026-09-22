from cognibot_laya.questions import (
    MAX_OPTIONS,
    NONE_LABEL,
    PRIMITIVES,
    SKILLS,
    guard_questions,
    primitive_questions,
    questions_fit,
    skill_questions,
)


def test_skill_questions_offer_every_skill_and_the_scene_labels():
    questions = skill_questions(["red cube", "black rectangle"])
    assert set(questions["skill"]["criteria"]) == set(SKILLS)
    assert list(questions["object"]["criteria"]) == ["red cube", "black rectangle", NONE_LABEL]


def test_skill_questions_cap_the_label_list():
    questions = skill_questions([f"cube {i}" for i in range(30)])
    assert len(questions["object"]["criteria"]) == MAX_OPTIONS
    assert NONE_LABEL in questions["object"]["criteria"]


def test_primitive_questions_offer_every_primitive():
    assert set(primitive_questions()["move"]["criteria"]) == set(PRIMITIVES)


def test_every_question_set_fits_the_marker_budget():
    assert questions_fit(skill_questions(["red cube", "green cube", "black rectangle"]))
    assert questions_fit(primitive_questions())
    assert questions_fit(guard_questions())


def test_an_overlong_option_set_is_rejected():
    bad = {"q": {"type": "choice", "criteria": {f"o{i}": "x" * 200 for i in range(12)}}}
    assert not questions_fit(bad)
