from cognibot_laya.questions import (
    MAX_OPTIONS,
    MOTIONS,
    NONE_LABEL,
    PRIMITIVES,
    guard_questions,
    legal_motions,
    legal_skills,
    motions_toward,
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


def test_track_b_offers_only_motions_minus_the_blocked_ones():
    assert list(legal_motions()) == MOTIONS
    assert "down" not in legal_motions(frozenset({"down"}))
    assert list(legal_motions(frozenset(MOTIONS))) == MOTIONS  # never an empty option set


def test_skill_questions_cap_the_label_list():
    questions = skill_questions([f"cube {i}" for i in range(30)])
    assert len(questions["object"]["criteria"]) == MAX_OPTIONS
    assert NONE_LABEL in questions["object"]["criteria"]


def test_primitive_questions_offer_the_motions():
    assert set(primitive_questions()["move"]["criteria"]) == set(MOTIONS)
    assert set(MOTIONS) < set(PRIMITIVES)


def test_every_question_set_fits_the_marker_budget():
    assert questions_fit(skill_questions(["red cube", "green cube", "black rectangle"]))
    assert questions_fit(skill_questions(["black rectangle", "red cube"], holding=True))
    assert questions_fit(primitive_questions())
    assert questions_fit(guard_questions())


def test_an_overlong_option_set_is_rejected():
    bad = {"q": {"type": "choice", "criteria": {f"o{i}": "x" * 200 for i in range(12)}}}
    assert not questions_fit(bad)


def test_only_motions_toward_the_aim_are_offered():
    """The limit cycle: 9 cm left and 3 cm forward offered `back`, which undid every `forward`."""
    toward = motions_toward((0.03, 0.09, 0.0))
    assert toward == {"forward", "left"}
    assert set(legal_motions(toward=toward)) == {"forward", "left"}


def test_a_blocked_motion_falls_back_to_the_rest():
    toward = motions_toward((0.0, 0.09, 0.0))
    assert set(legal_motions(frozenset({"left"}), toward)) == set(MOTIONS) - {"left"}
