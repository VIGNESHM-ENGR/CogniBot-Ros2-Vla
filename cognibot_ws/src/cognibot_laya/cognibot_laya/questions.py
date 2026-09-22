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

MOTIONS = ["forward", "back", "left", "right", "up", "down"]


def legal_skills(holding: bool) -> dict[str, str]:
    """Skills that can run from this gripper state: fetch needs it empty, place needs it full.

    Offered every skill, the model chose `place` with an empty gripper twelve steps in a row on
    the live arm. An option that cannot run is not a choice the model should get.
    """
    blocked = "fetch" if holding else "place"
    return {k: v for k, v in SKILLS.items() if k != blocked}


def legal_motions(blocked: frozenset[str] = frozenset()) -> dict[str, str]:
    """The six motions, minus any that just failed to move the gripper.

    Track B asks the model only for motions. Grasp, release and done are executed when the stage
    reaches its point (`pickplace.plan_stage`): there a motion is a no-op or moves away, and the
    model, offered both, chose `down` over `grasp`/`release` at the aim 0 of 6 times correctly.
    `blocked` motions (a joint limit, contact) are left out until one succeeds again.
    """
    keys = [k for k in MOTIONS if k not in blocked] or list(MOTIONS)
    return {k: PRIMITIVES[k] for k in keys}


def skill_questions(labels: list[str], holding: bool = False) -> dict:
    """Track A: which skill, and which object it applies to.

    `labels` are the candidates for this gripper state (movable objects to fetch, or destinations
    for the held one); `none` is always offered so a skill that needs no object (home, done) has
    somewhere to point. The skill options are `legal_skills(holding)`.
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
            "criteria": legal_skills(holding),
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


def primitive_questions(options: dict[str, str] | None = None) -> dict:
    """Track B: one motion, read from `go_to` (see `state.worded_gap`) for the current `stage`."""
    return {
        "move": {
            "type": "choice",
            "instructions": (
                "`go_to` says where the gripper must move for `stage`, largest distance first. "
                "Which motion moves it that way?"
            ),
            "criteria": dict(options if options is not None else legal_motions()),
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
