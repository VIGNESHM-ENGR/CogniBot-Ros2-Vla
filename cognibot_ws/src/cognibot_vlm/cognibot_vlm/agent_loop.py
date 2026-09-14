"""The tool-calling loop, independent of ROS and of the OpenAI SDK (ADR-0007).

`ChatClient.complete` returns the assistant turn for a message list; `ToolRunner.run` executes a
validated tool call and returns a short result string for the model. Both are protocols so the
loop is unit-tested with fakes and the node supplies the real ones.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Protocol

from cognibot_vlm.tools.schemas import TOOLS, ToolError, validate_arguments

MAX_STEPS = 12


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    arguments: str  # raw JSON text from the model


@dataclass(frozen=True)
class AssistantTurn:
    content: str
    tool_calls: tuple[ToolCall, ...] = ()


class ChatClient(Protocol):
    def complete(self, messages: list[dict[str, Any]], tools: list[dict]) -> AssistantTurn: ...


class ToolRunner(Protocol):
    def run(self, name: str, arguments: dict[str, Any]) -> str: ...


@dataclass(frozen=True)
class Event:
    """Mirror of cognibot_interfaces/AgentEvent, without the ROS header."""

    step: int
    type: str  # thought | tool_call | tool_result | info | error | done
    content: str
    tool_name: str = ""
    duration_s: float = 0.0


@dataclass
class TaskResult:
    success: bool
    summary: str
    events: list[Event] = field(default_factory=list)


def user_message(task: str, image_jpeg_b64: str | None) -> dict[str, Any]:
    """The first user turn: the task text plus the current camera frame when available."""
    if image_jpeg_b64 is None:
        return {"role": "user", "content": task}
    return {
        "role": "user",
        "content": [
            {"type": "text", "text": task},
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{image_jpeg_b64}"},
            },
        ],
    }


def run_task(
    chat: ChatClient,
    tools: ToolRunner,
    system_prompt: str,
    task: str,
    image_jpeg_b64: str | None,
    on_event: Callable[[Event], None] = lambda _e: None,
    is_canceled: Callable[[], bool] = lambda: False,
    max_steps: int = MAX_STEPS,
) -> TaskResult:
    """Drive the model until it answers without tool calls, `max_steps` is hit, or cancel."""
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": system_prompt},
        user_message(task, image_jpeg_b64),
    ]
    result = TaskResult(success=False, summary="")

    def emit(event: Event) -> None:
        result.events.append(event)
        on_event(event)

    repaired = False
    for step in range(1, max_steps + 1):
        if is_canceled():
            emit(Event(step, "error", "canceled"))
            result.summary = "canceled"
            return result
        started = time.monotonic()
        turn = chat.complete(messages, TOOLS)
        model_s = time.monotonic() - started
        if turn.content:
            emit(Event(step, "thought", turn.content, duration_s=model_s))
        if not turn.tool_calls:
            result.success = True
            result.summary = turn.content or "done"
            emit(Event(step, "done", result.summary))
            return result
        messages.append(
            {
                "role": "assistant",
                "content": turn.content or None,
                "tool_calls": [
                    {
                        "id": c.id,
                        "type": "function",
                        "function": {"name": c.name, "arguments": c.arguments},
                    }
                    for c in turn.tool_calls
                ],
            }
        )
        for call in turn.tool_calls:
            emit(Event(step, "tool_call", call.arguments, call.name, model_s))
            try:
                arguments = validate_arguments(call.name, json.loads(call.arguments or "{}"))
            except (json.JSONDecodeError, ToolError) as exc:
                # One repair round: tell the model what was wrong and let it call again.
                text = f"invalid tool call: {exc}"
                emit(Event(step, "error", text, call.name))
                messages.append({"role": "tool", "tool_call_id": call.id, "content": text})
                if repaired:
                    result.summary = text
                    emit(Event(step, "done", result.summary))
                    return result
                repaired = True
                continue
            started = time.monotonic()
            try:
                output = tools.run(call.name, arguments)
            except Exception as exc:  # tool failures go back to the model, not up the stack
                output = f"error: {exc}"
            emit(Event(step, "tool_result", output, call.name, time.monotonic() - started))
            messages.append({"role": "tool", "tool_call_id": call.id, "content": output})
    result.summary = f"stopped after {max_steps} steps without finishing"
    emit(Event(max_steps, "done", result.summary))
    return result
