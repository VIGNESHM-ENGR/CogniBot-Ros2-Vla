# ADR-0005: Qwen3-VL-4B on llama.cpp behind llama-swap, with RAM offload profiles

- **Status:** Accepted
- **Date:** 2026-09-13

## Context

The VLM must ground objects in images and call tools, and share a 6 GB GPU with SmolVLA. The host has 40 GB of RAM and a 6-core CPU. The project owner chose llama.cpp as the inference runtime.

## Decision

- Model: **Qwen3-VL-4B-Instruct**, official GGUF (`Q4_K_M` weights + `Q8_0` mmproj). It has native 2D grounding and follows tool-call templates; the instruct variant avoids thinking-token latency.
- Server: **llama.cpp `llama-server`** (`--jinja` for OpenAI-style tool calls), managed by **llama-swap** (`ghcr.io/mostlygeek/llama-swap:unified-cuda`).
- Three llama-swap entries for the same files: `qwen3-vl-4b-gpu` (`-ngl 99`), `qwen3-vl-4b-hybrid` (`-ngl 16`), `qwen3-vl-4b-cpu` (`-ngl 0 --no-mmproj-offload`). They share one swap group, so only one is loaded at a time. `ttl` evicts idle models, and `/api/models/unload` is called before VLA streaming.

## Consequences

- VRAM can be traded for latency at runtime, with no restarts or config edits.
- One OpenAI-compatible endpoint serves the agent (the `openai` SDK), which makes the model swappable later.
- The agent must handle a 4B model's imperfect tool calls: schema validation, one repair retry, and a JSON `response_format` fallback.

## Alternatives considered

- **Ollama.** Simpler UX, but less direct control over llama-server flags; llama.cpp was preferred.
- **vLLM.** Pre-allocates VRAM; no CPU offload suited to this budget.
- **SmolVLM2-2.2B.** Weaker grounding; would require classical segmentation for coordinates.
