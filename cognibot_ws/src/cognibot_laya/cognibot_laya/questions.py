"""Typed questions for the two decision tracks (ADR-0008).

Every option is scored at its own `[MASK]` marker and the options of one question share a single
`head_max_len` budget (192 tokens on the shipped checkpoints), so option text is short by
necessity: long criteria push the later options out of the sequence and they are never scored.
"""

from __future__ import annotations

# Option text is truncated by the model if the set is too long; keep each criterion under ~60
# characters and the set under this many options.
MAX_OPTIONS = 12
# Upstream default; `questions_fit` compares against it so a bad option set fails in a test
# rather than in the container.
HEAD_MAX_LEN = 192
CHARS_PER_TOKEN = 4

# fetch and place open and close the gripper themselves (pick_place_server plans the grasp), so
# the set has no separate gripper options: measured on both shipped checkpoints, adding them made
# the model answer open_gripper / close_gripper regardless of the state (p = 0.87 / 0.93).
SKILLS: dict[str, str] = {
    "fetch": "pick up an object that is on the table",
    "place": "put the held object onto a destination",
    "home": "move the arm back to its home pose",
    "vla_skill": "run the learned policy for this task",
    "done": "the task is already finished",
    "ask_human": "unclear or unsafe, ask a person",
}

PRIMITIVES: dict[str, str] = {
    "forward": "move the gripper forward, away from the base",
    "back": "move the gripper back, toward the base",
    "left": "move the gripper left",
    "right": "move the gripper right",
    "up": "raise the gripper",
    "down": "lower the gripper",
    "grasp": "close the gripper on the object",
    "release": "open the gripper",
    "done": "the gripper is at the target",
}

NONE_LABEL = "none"


def skill_questions(labels: list[str]) -> dict:
    """Track A: which skill, and which object it applies to.

    `labels` are the grounded objects in the scene; `none` is always offered so a skill that needs
    no object (home, done) has somewhere to point.
    """
    options = [*labels[: MAX_OPTIONS - 1], NONE_LABEL]
    return {
        "skill": {
            "type": "choice",
            "instructions": (
                "Choose the next action for `task`. `holding` is what the gripper already holds: "
                "an object must be fetched before it can be placed, and only a held object can "
                "be placed."
            ),
            "criteria": dict(SKILLS),
        },
        "object": {
            "type": "choice",
            "instructions": (
                "Which object in `objects` does the chosen action apply to? For a fetch that is "
                "the object to pick up; for a place it is the destination to put it on."
            ),
            "criteria": {label: label for label in options},
        },
    }


def primitive_questions() -> dict:
    """Track B: one motion primitive, chosen from the gap between gripper and target."""
    return {
        "move": {
            "type": "choice",
            "instructions": (
                "Move the gripper toward `target`. `gap_cm` is the target minus the gripper: "
                "when forward is positive move forward, when it is negative move back; when left "
                "is positive move left, when it is negative move right; when up is positive move "
                "up, when it is negative move down. Take the largest gap first. Grasp only when "
                "`within_tolerance` is true."
            ),
            "criteria": dict(PRIMITIVES),
        }
    }


def guard_questions() -> dict:
    """Runs before a task starts: refuse, escalate, or go."""
    return {
        "unsafe": {
            "type": "noul",
            "instructions": (
                "Could carrying out `request` damage the robot, the objects or a person?"
            ),
        },
        "out_of_scope": {
            "type": "noul",
            "instructions": (
                "Does `request` ask for something this robot cannot do? It is a small table-top "
                "arm that can pick up and put down the objects in `objects_visible`."
            ),
        },
        "needs_human": {
            "type": "noul",
            "instructions": "Is `request` too vague or ambiguous to carry out without asking?",
        },
    }


def questions_fit(questions: dict, head_max_len: int = HEAD_MAX_LEN) -> bool:
    """True when every question's options fit the marker budget they share."""
    return all(_option_tokens(q) <= head_max_len for q in questions.values())


def _option_tokens(question: dict) -> int:
    criteria = question.get("criteria")
    if not criteria:  # noul questions score two implicit markers
        return 8
    rendered = criteria.values() if isinstance(criteria, dict) else criteria
    keys = criteria.keys() if isinstance(criteria, dict) else []
    text = "".join(str(v) for v in rendered) + "".join(str(k) for k in keys)
    return len(text) // CHARS_PER_TOKEN + 2 * len(criteria)
