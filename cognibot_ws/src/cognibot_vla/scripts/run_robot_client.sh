#!/usr/bin/env bash
# Run LeRobot's async robot_client against the CogniBot arm (vla image).
# The policy runs on the policy-server; this client streams observations from ROS and joint
# targets to /cognibot/joint_command (safety filter). Configure through the environment:
#   POLICY_TYPE      act | smolvla | diffusion            (default act)
#   VLA_CHECKPOINT   HF repo id or local path            (default szk1ck/so101-pickplace-sim-mujoco)
#   TASK             language instruction               (default "pick up the cube and place it on the target")
#   CAMERA_TOPICS    {policy_key: topic, ...}            (default front/wrist simulator cameras)
#   ACTION_DEGREES   true if the checkpoint outputs degrees (default false)
#   STATE_DEGREES    true if it expects state in degrees (default false)
#   ROBOT_TYPE       cognibot_so101 | cognibot_panda     (default cognibot_so101)
#   FPS, ACTIONS_PER_CHUNK, CHUNK_SIZE_THRESHOLD, POLICY_SERVER_ADDRESS
set -euo pipefail
cd /tmp  # robot_client writes ./logs
DEFAULT_CAMERAS="{front: /mujoco_camera_plugin/front_rgbd/color, wrist: /mujoco_camera_plugin/wrist_cam/color}"
exec python3 -m lerobot.async_inference.robot_client \
  --server_address="${POLICY_SERVER_ADDRESS:-127.0.0.1:8090}" \
  --robot.type="${ROBOT_TYPE:-cognibot_so101}" \
  --robot.camera_topics="${CAMERA_TOPICS:-$DEFAULT_CAMERAS}" \
  --robot.action_degrees="${ACTION_DEGREES:-false}" \
  --robot.state_degrees="${STATE_DEGREES:-false}" \
  --task="${TASK:-pick up the cube and place it on the target}" \
  --policy_type="${POLICY_TYPE:-act}" \
  --pretrained_name_or_path="${VLA_CHECKPOINT:-szk1ck/so101-pickplace-sim-mujoco}" \
  --policy_device="${POLICY_DEVICE:-cuda}" \
  --actions_per_chunk="${ACTIONS_PER_CHUNK:-50}" \
  --chunk_size_threshold="${CHUNK_SIZE_THRESHOLD:-0.5}" \
  --aggregate_fn_name=weighted_average \
  --fps="${FPS:-30}" \
  "$@"
