"""The tool-call loop with a scripted model and a recording tool runner."""

import json

from cognibot_vlm.agent_loop import AssistantTurn, ToolCall, run_task


class ScriptedChat:
    def __init__(self, turns):
        self.turns = list(turns)
        self.seen = []

    def complete(self, messages, tools):
        self.seen.append([m["role"] for m in messages])
        return self.turns.pop(0)


class Recorder:
    def __init__(self, results=None):
        self.calls = []
        self.results = results or {}

    def run(self, name, arguments):
        self.calls.append((name, arguments))
        value = self.results.get(name, "ok")
        if isinstance(value, Exception):
            raise value
        return value


def call(i, name, **args):
    return ToolCall(id=f"c{i}", name=name, arguments=json.dumps(args))


def test_pick_and_place_sequence_runs_each_tool_and_finishes():
    chat = ScriptedChat(
        [
            AssistantTurn(
                "Looking for the cube.", (call(1, "get_object_coordinates", label="red cube"),)
            ),
            AssistantTurn("", (call(2, "fetch_object", label="red cube"),)),
            AssistantTurn("", (call(3, "place_object", label="black rectangle"),)),
            AssistantTurn("Placed the red cube on the target."),
        ]
    )
    tools = Recorder({"get_object_coordinates": '{"x": 0.27, "y": -0.02, "z": 0.01}'})
    events = []
    result = run_task(chat, tools, "sys", "pick the red cube", "AAAA", events.append)
    assert result.success and result.summary.startswith("Placed")
    assert [c[0] for c in tools.calls] == ["get_object_coordinates", "fetch_object", "place_object"]
    assert [e.type for e in events] == [
        "thought", "tool_call", "tool_result", "tool_call", "tool_result",
        "tool_call", "tool_result", "thought", "done",
    ]  # fmt: skip
    # the model sees system, user(image), then assistant/tool pairs
    assert chat.seen[-1] == [
        "system",
        "user",
        "assistant",
        "tool",
        "assistant",
        "tool",
        "assistant",
        "tool",
    ]


def test_invalid_tool_call_is_repaired_once_then_ends():
    chat = ScriptedChat(
        [
            AssistantTurn("", (ToolCall("c1", "fetch_object", "{not json"),)),
            AssistantTurn("", (call(2, "fetch_object", object="cube"),)),  # still wrong: no label
            AssistantTurn("never reached"),
        ]
    )
    tools = Recorder()
    result = run_task(chat, tools, "sys", "task", None)
    assert not result.success and "missing" in result.summary
    assert tools.calls == []
    assert len(chat.turns) == 1


def test_tool_exceptions_are_reported_to_the_model():
    chat = ScriptedChat([AssistantTurn("", (call(1, "move_home"),)), AssistantTurn("gave up")])
    tools = Recorder({"move_home": RuntimeError("controller offline")})
    result = run_task(chat, tools, "sys", "go home", None)
    assert result.success  # the model decided to stop; the loop reports what it said
    assert any(e.type == "tool_result" and "controller offline" in e.content for e in result.events)


def test_step_limit_and_cancel():
    chat = ScriptedChat([AssistantTurn("", (call(i, "move_home"),)) for i in range(5)])
    result = run_task(chat, Recorder(), "sys", "loop", None, max_steps=3)
    assert not result.success and "3 steps" in result.summary
    flags = iter([False, True])
    result = run_task(
        ScriptedChat([AssistantTurn("", (call(1, "move_home"),))] * 3),
        Recorder(),
        "s",
        "t",
        None,
        is_canceled=lambda: next(flags),
    )
    assert result.summary == "canceled"
