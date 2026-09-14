# ADR-0007: Thin `openai` tool-call loop as the VLM agent runtime (RAI not adopted)

- **Status:** Accepted
- **Date:** 2026-09-14

## Context

P4-T01 asked whether [RAI](https://github.com/RobotecAI/rai) (RobotecAI's ROS 2 agent framework, pinned candidate `6802d40`) should run the VLM agent, or a thin loop on the `openai` SDK against llama-swap (ADR-0005). The agent has seven tools, one camera, a 4B model with imperfect tool-call formatting, and must run in the 2 GB `vlm-agent` container beside a 6 GB GPU shared with SmolVLA.

Measured on 2026-09-14 with `uv pip install --dry-run` (Python 3.12):

| Candidate | Packages | Notable dependencies |
|---|---|---|
| `rai-core` (PyPI, current) | **123** | langchain 1.4 (+ community, classic, aws, google-genai, ollama, openai), langgraph 1.2 (+ checkpoint, prebuilt, sdk), opencv-python **and** opencv-python-headless, pydantic-settings |
| `openai==3.13.0` | 16 | httpx, pydantic |

RAI's value is its LangGraph agent, its vendor abstraction and its ROS 2 connectors (topic/service/action tools). Our tools are already ROS-native (`FetchObject`, `PlaceObject`, `ExecuteSkill`, `GetObjectCoordinates` …), the model vendor is fixed by ADR-0005, and the loop we need (system prompt + image → tool calls → results, max 12 steps, one repair retry) is ~150 lines. RAI also brings two OpenCV builds and cloud vendor SDKs into an image that must stay small, and its LangChain 1.x line moves quickly, which conflicts with the pin-everything rule.

## Decision

Write the agent loop on the `openai` SDK (`openai==3.13.0`, `vlm` venv) talking to llama-swap's OpenAI-compatible endpoint. Tools are plain JSON schemas (`cognibot_vlm/tools`), dispatched to rclpy clients by name; the loop validates arguments with the schema, retries once on invalid JSON, and emits `AgentEvent` per step.

## Consequences

- No agent framework to track; the loop is unit-tested with a fake chat client and a fake ROS layer.
- Vendor swap later means changing `LLM_BASE_URL`/`LLM_MODEL`; anything OpenAI-compatible works.
- Multi-agent graphs, memory and RAI's built-in tools are out of scope; revisit if the agent needs them.

## Alternatives considered

- **RAI at `6802d40`.** Rejected for dependency weight (123 packages, two OpenCV builds) and framework churn; its ROS connectors duplicate clients we already have. Revisit if a second robot-agent (e.g. a navigation or multi-step planner) needs LangGraph state machines.
- **LangGraph alone.** Smaller than RAI but still an abstraction over a seven-tool loop.
