#!/usr/bin/env bash
# Download the pinned Laya decision checkpoints into the Hugging Face cache that the `laya` service
# mounts at /hf_cache. All three checkpoints live in one repo (english at the root, multilingual and
# typed-decisions in subfolders); the benchmark plots and logos are skipped. Pins: INTEGRATIONS §6.
set -euo pipefail
REPO=convaiinnovations/laya
REV=1c5edc17a7acd8701df6fc341c0d179f1c62c982
uvx --from "huggingface_hub==1.31.0" hf download "${REPO}" --revision "${REV}" \
  --exclude "assets/*" --exclude "eval/*"
