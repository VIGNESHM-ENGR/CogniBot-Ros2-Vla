"""Answers → a typed action, with the confidence gate (ADR-0008).

Laya returns a choice per question with per-option probabilities, a calibrated confidence and an
`act_probability` (act vs escalate). Nothing moves on a low-confidence answer: the loop escalates
instead, which is the whole reason for using a calibrated model rather than a generative one.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from cognibot_laya.questions import NONE_LABEL, PRIMITIVES, SKILLS

# Skills that need an object; the others ignore the `object` answer.
NEEDS_OBJECT = {"fetch", "place"}


@dataclass(frozen=True)
class SkillAction:
    skill: str
    label: str = ""
    confidence: float = 0.0

    def describe(self) -> str:
        return f"{self.skill} {self.label}".strip()


@dataclass(frozen=True)
class PrimitiveAction:
    primitive: str
    confidence: float = 0.0

    def describe(self) -> str:
        return self.primitive


@dataclass(frozen=True)
class Escalate:
    reason: str
    confidence: float = 0.0

    def describe(self) -> str:
        return f"escalate: {self.reason}"


Action = SkillAction | PrimitiveAction | Escalate


@dataclass(frozen=True)
class Answer:
    """One question's answer, flattened out of the model payload for publishing."""

    question_id: str
    choice: str
    options: list[str] = field(default_factory=list)
    probabilities: list[float] = field(default_factory=list)
    confidence: float = 0.0
    act_probability: float = 0.0


def read_answers(payload: dict[str, Any]) -> dict[str, Answer]:
    """Flatten `{"answers": {qid: {...}}}` into `Answer`s (choice and noul questions)."""
    out: dict[str, Answer] = {}
    for qid, answer in payload.get("answers", {}).items():
        act = float(answer.get("action", {}).get("act_probability", 0.0))
        confidence = float(answer.get("confidence", 0.0))
        if answer.get("type") == "choice":
            probabilities = answer.get("probabilities", {})
            out[qid] = Answer(
                qid,
                str(answer.get("choice", "")),
                list(probabilities.keys()),
                [float(v) for v in probabilities.values()],
                confidence,
                act,
            )
        else:  # noul: two implicit options, kept in the same shape for the dashboard
            p_true = float(answer.get("noul", 0.0))
            out[qid] = Answer(
                qid,
                "true" if p_true >= 0.5 else "false",
                ["false", "true"],
                [1.0 - p_true, p_true],
                confidence,
                act,
            )
    return out


def routed_model(payload: dict[str, Any]) -> str:
    """Which checkpoint answered; empty when a bare Agent (not the Router) was used."""
    return str(payload.get("routing", {}).get("model", ""))


def skill_action(
    payload: dict[str, Any], labels: list[str], min_confidence: float
) -> tuple[Action, dict[str, Answer]]:
    """Track A: `skill` + `object` → a `SkillAction`, or `Escalate`."""
    answers = read_answers(payload)
    skill = answers.get("skill")
    if skill is None:
        return Escalate("the model returned no skill answer"), answers
    if skill.choice not in SKILLS:
        return Escalate(f"unknown skill '{skill.choice}'", skill.confidence), answers
    if skill.confidence < min_confidence:
        return Escalate(
            f"skill confidence {skill.confidence:.2f} below {min_confidence:.2f}", skill.confidence
        ), answers
    if skill.choice == "ask_human":
        return Escalate("the model asked for a person", skill.confidence), answers
    if skill.choice not in NEEDS_OBJECT:
        return SkillAction(skill.choice, "", skill.confidence), answers

    chosen = answers.get("object")
    if chosen is None or chosen.choice in ("", NONE_LABEL):
        return Escalate(
            f"{skill.choice} needs an object, none was chosen", skill.confidence
        ), answers
    if chosen.choice not in labels:
        return Escalate(f"'{chosen.choice}' is not in the scene", chosen.confidence), answers
    if chosen.confidence < min_confidence:
        return Escalate(
            f"object confidence {chosen.confidence:.2f} below {min_confidence:.2f}",
            chosen.confidence,
        ), answers
    return SkillAction(
        skill.choice, chosen.choice, min(skill.confidence, chosen.confidence)
    ), answers


def primitive_action(
    payload: dict[str, Any], min_confidence: float
) -> tuple[Action, dict[str, Answer]]:
    """Track B: `move` → a `PrimitiveAction`, or `Escalate`."""
    answers = read_answers(payload)
    move = answers.get("move")
    if move is None:
        return Escalate("the model returned no move answer"), answers
    if move.choice not in PRIMITIVES:
        return Escalate(f"unknown primitive '{move.choice}'", move.confidence), answers
    if move.confidence < min_confidence:
        return Escalate(
            f"move confidence {move.confidence:.2f} below {min_confidence:.2f}", move.confidence
        ), answers
    return PrimitiveAction(move.choice, move.confidence), answers


def guard_verdict(payload: dict[str, Any], threshold: float = 0.5) -> tuple[bool, str]:
    """(allowed, reason) from the guard questions; any flag above `threshold` blocks the run."""
    answers = read_answers(payload)
    flags = {
        "unsafe": "the request looks unsafe",
        "out_of_scope": "the request is outside what this arm does",
        "needs_human": "the request is too vague to carry out",
    }
    for qid, reason in flags.items():
        answer = answers.get(qid)
        if answer is None:
            continue
        p_true = answer.probabilities[-1] if answer.probabilities else 0.0
        if p_true > threshold:
            return False, f"{reason} (p={p_true:.2f})"
    return True, ""
