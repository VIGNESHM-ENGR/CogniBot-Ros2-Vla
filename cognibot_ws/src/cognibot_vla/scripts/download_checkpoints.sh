#!/usr/bin/env bash
# Download pinned LeRobot policy checkpoints into the Hugging Face cache.
# Pins and selection rationale: docs/INTEGRATIONS.md §6.
#   bash download_checkpoints.sh            # all checkpoints
#   bash download_checkpoints.sh smolvla_base act_mujoco_tray
# HF_HOME selects the cache (default ~/.cache/huggingface).
set -euo pipefail

# name | repo | revision (HF commit) | policy | trained in
CHECKPOINTS=(
  "smolvla_base|lerobot/smolvla_base|c83c3163b8ca9b7e67c509fffd9121e66cb96205|smolvla|pretrained (community real-arm data)"
  "smolvla_mujoco_tray|bendca61/smolvla-mujoco-so101-cube_on_tray|d9da3285e866aa6464ea1c6e71363d03d4c85682|smolvla|MuJoCo SO-101"
  "smolvla_isaac_orange|edge-inference/smolvla-so101-pick-orange|71cf4a9d35ce317f6706efe1a9f9d4cbb2b8fb4d|smolvla|Isaac Sim SO-101 (LeIsaac)"
  "smolvla_arena_multitask|Chaenn/smolvla_policy_so101_cube_multitask_sim_0824|111cf91950868312aa64d89f83595e5da981f6ed|smolvla|capstone_arena sim SO-101 (295 episodes, degrees)"
  "act_mujoco_tray|bendca61/act-so101-mujoco-cube_on_tray-v1|676050ad8a25816c238389a31795d1498691ec32|act|MuJoCo SO-101"
  "act_mujoco_pickplace|szk1ck/so101-pickplace-sim-mujoco|3dcc200be7aa0f8b19130586ab7b99d6ff304494|act|MuJoCo SO-101"
  "diffusion_real_cube|Chaenn/diffusion_so101_cube_multitask_hil_0729|1d39f411a36821e4b885f7d7dee1ac51ed0d4fb1|diffusion|real SO-101"
  # Vision-language backbone every SmolVLA checkpoint loads at start (policy config vlm_model_name).
  "smolvlm2_backbone|HuggingFaceTB/SmolVLM2-500M-Video-Instruct|7b375e1b73b11138ff12fe22c8f2822d8fe03467|vlm backbone|SmolVLA dependency"
)

HF=(uvx --from "huggingface_hub==1.31.0" hf)

want=("$@")
for entry in "${CHECKPOINTS[@]}"; do
  IFS="|" read -r name repo rev policy origin <<<"${entry}"
  if [ "${#want[@]}" -gt 0 ] && [[ ! " ${want[*]} " =~ " ${name} " ]]; then
    continue
  fi
  echo ">>> ${name}: ${repo}@${rev:0:8} (${policy}, ${origin})"
  snapshot="$("${HF[@]}" download "${repo}" --revision "${rev}" 2>/dev/null | tail -n1 | sed "s/^path=//")"
  if [ "${policy}" = "smolvla" ]; then
    # Some SmolVLA fine-tunes ship compile_model=true / compile_mode=max-autotune, which costs a
    # ~3 min autotune on every server start and fails CUDA-graph capture next to the simulator's
    # EGL context. Publish a local variant with compilation off under $HF_HOME/cognibot/<name>.
    variant="${HF_HOME:-$HOME/.cache/huggingface}/cognibot/${name}"
    mkdir -p "${variant}"
    # Relative links: the cache is mounted at a different path inside the policy-server container.
    rel="$(realpath --relative-to="${variant}" "${snapshot}")"
    for f in "${snapshot}"/*; do ln -sfn "${rel}/$(basename "${f}")" "${variant}/$(basename "${f}")"; done
    rm -f "${variant}/config.json"
    python3 - "${snapshot}/config.json" "${variant}/config.json" <<'PY'
import json, sys
cfg = json.load(open(sys.argv[1]))
cfg["compile_model"] = False
json.dump(cfg, open(sys.argv[2], "w"), indent=2)
PY
    echo "    uncompiled variant: ${variant}"
  fi
done
