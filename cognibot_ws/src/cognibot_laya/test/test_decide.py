from cognibot_laya.decide import (
    Escalate,
    PrimitiveAction,
    SkillAction,
    guard_verdict,
    primitive_action,
    read_answers,
    routed_model,
    skill_action,
)


def choice(qid_probs: dict, confidence: float = 0.9, act: float = 0.9) -> dict:
    """A choice answer in the shape laya.Agent.system_one returns."""
    best = max(qid_probs, key=qid_probs.get)
    return {
        "type": "choice",
        "choice": best,
        "probabilities": qid_probs,
        "confidence": confidence,
        "action": {"act_probability": act},
    }


def payload(**answers) -> dict:
    return {"model": "laya-rl-agent", "answers": answers}


LABELS = ["red cube", "black rectangle"]


def test_skill_action_reads_skill_and_object():
    result, answers = skill_action(
        payload(
            skill=choice({"fetch": 0.8, "place": 0.2}),
            object=choice({"red cube": 0.9, "black rectangle": 0.1}),
        ),
        LABELS,
        0.5,
    )
    assert result == SkillAction("fetch", "red cube", 0.9)
    assert answers["skill"].options == ["fetch", "place"]
    assert answers["skill"].probabilities == [0.8, 0.2]


def test_skills_without_an_object_ignore_the_object_answer():
    result, _ = skill_action(payload(skill=choice({"home": 0.9})), LABELS, 0.5)
    assert result == SkillAction("home", "", 0.9)


def test_low_confidence_escalates_instead_of_moving():
    result, _ = skill_action(
        payload(skill=choice({"fetch": 0.6}, confidence=0.3)),
        LABELS,
        0.5,
    )
    assert isinstance(result, Escalate)
    assert "below" in result.reason


def test_a_label_that_is_not_in_the_scene_escalates():
    result, _ = skill_action(
        payload(skill=choice({"fetch": 0.9}), object=choice({"blue cube": 0.9})),
        LABELS,
        0.5,
    )
    assert isinstance(result, Escalate)
    assert "not in the scene" in result.reason


def test_fetch_without_an_object_escalates():
    result, _ = skill_action(
        payload(skill=choice({"fetch": 0.9}), object=choice({"none": 0.9})), LABELS, 0.5
    )
    assert isinstance(result, Escalate)


def test_ask_human_escalates():
    result, _ = skill_action(payload(skill=choice({"ask_human": 0.9})), LABELS, 0.5)
    assert isinstance(result, Escalate)


def test_primitive_action_reads_the_move():
    result, answers = primitive_action(payload(move=choice({"left": 0.7, "up": 0.3})), 0.5)
    assert result == PrimitiveAction("left", 0.9)
    assert answers["move"].choice == "left"


def test_an_unknown_primitive_escalates():
    result, _ = primitive_action(payload(move=choice({"teleport": 0.9})), 0.5)
    assert isinstance(result, Escalate)


def test_guard_blocks_on_a_flag_above_the_threshold():
    allowed, reason = guard_verdict(
        {
            "answers": {
                "unsafe": {"type": "noul", "noul": 0.81, "confidence": 0.81, "action": {}},
                "out_of_scope": {"type": "noul", "noul": 0.1, "confidence": 0.9, "action": {}},
            }
        }
    )
    assert not allowed
    assert "unsafe" in reason


def test_only_the_unsafe_flag_blocks():
    # Measured: out_of_scope and needs_human swing with the object list, so they are advisory.
    allowed, reason = guard_verdict(
        {
            "answers": {
                "out_of_scope": {"type": "noul", "noul": 0.85, "confidence": 0.85, "action": {}},
                "needs_human": {"type": "noul", "noul": 0.70, "confidence": 0.70, "action": {}},
                "unsafe": {"type": "noul", "noul": 0.01, "confidence": 0.99, "action": {}},
            }
        },
        0.6,
    )
    assert allowed and reason == ""


def test_guard_allows_a_clean_request():
    allowed, reason = guard_verdict(
        {"answers": {"unsafe": {"type": "noul", "noul": 0.02, "confidence": 0.98, "action": {}}}}
    )
    assert allowed and reason == ""


def test_noul_answers_are_flattened_for_publishing():
    answers = read_answers(
        {"answers": {"unsafe": {"type": "noul", "noul": 0.25, "confidence": 0.75, "action": {}}}}
    )
    assert answers["unsafe"].options == ["false", "true"]
    assert answers["unsafe"].probabilities == [0.75, 0.25]
    assert answers["unsafe"].choice == "false"


def test_routed_model_is_reported_when_the_router_answered():
    assert routed_model({"routing": {"model": "multilingual"}}) == "multilingual"
    assert routed_model({}) == ""
