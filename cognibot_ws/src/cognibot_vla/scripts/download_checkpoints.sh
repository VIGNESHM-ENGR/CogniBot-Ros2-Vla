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
  "act_mujoco_tray|bendca61/act-so101-mujoco-cube_on_tray-v1|676050ad8a25816c238389a31795d1498691ec32|act|MuJoCo SO-101"
  "act_mujoco_pickplace|szk1ck/so101-pickplace-sim-mujoco|3dcc200be7aa0f8b19130586ab7b99d6ff304494|act|MuJoCo SO-101"
  "diffusion_real_cube|Chaenn/diffusion_so101_cube_multitask_hil_0729|1d39f411a36821e4b885f7d7dee1ac51ed0d4fb1|diffusion|real SO-101"
)

HF=(uvx --from "huggingface_hub==1.31.0" hf)

want=("$@")
for entry in "${CHECKPOINTS[@]}"; do
  IFS="|" read -r name repo rev policy origin <<<"${entry}"
  if [ "${#want[@]}" -gt 0 ] && [[ ! " ${want[*]} " =~ " ${name} " ]]; then
    continue
  fi
  echo ">>> ${name}: ${repo}@${rev:0:8} (${policy}, ${origin})"
  "${HF[@]}" download "${repo}" --revision "${rev}"
done
