#!/usr/bin/env bash
# Download the pinned Qwen3-VL-4B GGUF files into the Hugging Face cache that the `llm` service
# mounts at /hf_cache (config.yaml points at this snapshot). Pins: docs/INTEGRATIONS.md §6.
set -euo pipefail
REPO=Qwen/Qwen3-VL-4B-Instruct-GGUF
REV=1cd86afb9a95c410a6038ab3b40d8b578c892266
uvx --from "huggingface_hub==1.31.0" hf download "${REPO}" --revision "${REV}" \
  Qwen3VL-4B-Instruct-Q4_K_M.gguf mmproj-Qwen3VL-4B-Instruct-Q8_0.gguf
