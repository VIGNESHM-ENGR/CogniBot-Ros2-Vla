# Integrations: third-party components and pins

Related: [ADR-0006](adr/0006-integrate-dont-invent.md) · [THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md)

CogniBot is an integration project. This file lists **every external component**, what we use it for, how it's pinned, and what glue we wrote around it. Bump a pin in its own commit (`build(deps): bump <component> to <version>`) and re-run the verification for the affected phase.

> Pins marked **TBD** get resolved by the task named in the "Pinned by" column. That task must replace TBD with an exact tag, digest or SHA.

## 1. Container base images

| Image | Used by | Pin | Pinned by | Why this image |
|---|---|---|---|---|
| `moveit/moveit2:jazzy-release` | `core` image (`sim`, `motion`, `bridge`, `twin`) | tag now → digest **TBD** | P0 / P1-T01 | Official MoveIt image on `ros:jazzy-ros-base`, with MoveIt 2 binaries (incl. `moveit_py`) preinstalled |
| `ros:jazzy-ros-base-noble` | `interfaces` build stage, `vlm`, `vla` images | tag now → digest **TBD** | P0 | Official OSRF image, Python 3.12 |
| `ghcr.io/mostlygeek/llama-swap:unified-cuda13` | `llm` | tag now → versioned tag **TBD** | P4-T01 | llama-swap + llama.cpp `llama-server` (CUDA) in one image; model hot-swap/TTL/unload API |
| `huggingface/lerobot-gpu:latest` | `policy-server` | digest **TBD** | P5-T01 | Official LeRobot GPU image; runs `lerobot.async_inference.policy_server` unmodified |
| `node:22-alpine` → `nginx:1.27-alpine` | `dashboard` | tags | P3-T03 | Standard SPA build and serve |

## 2. ROS 2 packages (apt, Jazzy binaries)

| Package | Version seen | Purpose |
|---|---|---|
| `ros-jazzy-mujoco-ros2-control` (+ `-plugins`) | 0.1.2 | MuJoCo ↔ ros2_control system interface, camera plugin, headless simulate |
| `ros-jazzy-ros2-controllers` / `ros2-control` | distro | joint_state_broadcaster, joint_trajectory_controller, position_controllers, parallel_gripper_action_controller |
| `ros-jazzy-pick-ik` | 1.1.2 (binary in the pinned MoveIt image, 2026-09-03) | IK plugin for 5-DOF SO-101 (position-only: `rotation_scale: 0.0`) |
| `ros-jazzy-moveit` (in base image) | distro | Planning, planning scene, MoveItPy |
| `ros-jazzy-moveit-resources-panda-moveit-config` | distro | Franka Panda MoveIt config |
| `ros-jazzy-rosbridge-server` | distro | WebSocket bridge for the dashboard |
| `ros-jazzy-web-video-server` | distro | MJPEG streams for the dashboard |
| `ros-jazzy-rmw-cyclonedds-cpp` | distro | Middleware ([ADR-0004](adr/0004-cyclonedds-host-network.md)) |
| `ros-jazzy-xacro`, `-robot-state-publisher`, `-tf2-ros` | distro | Description and TF |

## 3. ROS 2 sources (vcstool, `cognibot_ws/third_party.repos`)

| Repository | Pin (commit) | Packages we build | Purpose | License |
|---|---|---|---|---|
| [legalaspro/so101-ros-physical-ai](https://github.com/legalaspro/so101-ros-physical-ai) | `58318c905a2c61289fa907de85cb8473322fbe68` | `so101_description`, `so101_moveit_config` | SO-101 URDF/meshes and MoveIt config (the base for our MuJoCo xacro wrapper) | Apache-2.0 |
| [legalaspro/feetech_ros2_driver](https://github.com/legalaspro/feetech_ros2_driver) | `4c0fdbfe16c84c686f8ace09526c52d98d0110ca` | `feetech_ros2_driver` | STS3215 serial-bus ros2_control hardware interface (digital twin, P6) | BSD-3-Clause |
| [ros-industrial/reach_ros2](https://github.com/ros-industrial/reach_ros2) | `cd048ffcb69c5a0ba2b74124f15afa1ad63c27b5` | `reach_ros` | MoveIt-based REACH evaluators/IK plugins | Apache-2.0 |
| [ros-industrial/reach](https://github.com/ros-industrial/reach) | `33160eb67b1c711700b766ba325666b8ce5b061f` (P2-T05 switches to apt `ros-jazzy-reach` if the binary works) | `reach` | Reachability study core | Apache-2.0 |

The so101 repository contains more packages (`so101_kinematics`, `so101_inference`, `episode_recorder`, …) with pixi-managed Python dependencies. We **skip** them in colcon (`--packages-up-to` our packages only) so we don't pull their environment.

## 4. Robot models and scenes (downloaded, never hand-written)

**Where "official" SO-101 MuJoCo files come from.** LeRobot itself doesn't ship an SO-101 MJCF. The lineage is:

1. **TheRobotStudio/SO-ARM100** (the arm's designer; 7.4k★, Apache-2.0). `Simulation/SO101/` holds the official URDF and MJCF, generated from Onshape CAD.
2. **google-deepmind/mujoco_menagerie `robotstudio_so101`**, derived from (1). Adds primitive collision geoms for the gripper, tuned solver and actuator settings, and a wrist camera mount. **This is the model we use.**
3. **johnsutor/so101-nexus** (Apache-2.0, LeRobot EnvHub package). Builds LeRobot-compatible tabletop tasks (PickLift, PickAndPlace, StackCube, …) around (2), and publishes matching LeRobot datasets on the Hub. **We export its task scene so ROS sim, LeRobot datasets and checkpoints share one scene.**

| Source | Pin | Assets used | License |
|---|---|---|---|
| [google-deepmind/mujoco_menagerie](https://github.com/google-deepmind/mujoco_menagerie) `robotstudio_so101` | `8161bba264d7fa7c99ca301e91e7fb44737676ad` | `so101.xml`, `assets/` (joints: `shoulder_pan, shoulder_lift, elbow_flex, wrist_flex, wrist_roll, gripper`; `wrist_cam`, `gripperframe` site) | Apache-2.0 |
| mujoco_menagerie `franka_emika_panda` | same commit | `panda.xml`, `hand.xml`, `assets/` | Apache-2.0 |
| [TheRobotStudio/SO-ARM100](https://github.com/TheRobotStudio/SO-ARM100) `Simulation/SO101` | `eecbe3e0a9ebb23e25ad7b2759b03884c6660903` | reference only (URDF cross-check in P1-T03) | Apache-2.0 |
| [johnsutor/so101-nexus](https://github.com/johnsutor/so101-nexus) (`pip install so101-nexus`) | `6236b9abf6dcaa37bca7a20b4bd390e40b0fd2bc` / PyPI `0.6.0` | Task scenes (`MuJoCoPickAndPlace-v1`, `MuJoCoStackCube-v1`), exported to MJCF with `mujoco.mj_saveLastXML` at the pinned version; camera poses | Apache-2.0 |

Models are **downloaded by a pinned fetch script** (`cognibot_sim/scripts/fetch_models.sh`) into `cognibot_sim/robots/<robot>/mjcf/`, because MuJoCo needs local asset paths. Every modification (joint renames, added cameras, `<ros2_control>`-related actuator changes) is listed in a `MODIFICATIONS.md` next to the model, with the upstream commit.

## 5. Python packages

| Package | Where | Pin | Purpose |
|---|---|---|---|
| `mujoco` | `core` venv | `3.12.0` (matches `ros-jazzy-mujoco-vendor`) | Python bindings for mink and the safety filter |
| [`mink`](https://github.com/kevinzakka/mink) | `core` venv | `1.3.0` | Differential IK QP with collision avoidance |
| `qpsolvers[daqp]` | `core` venv | `4.13.0` | QP backend for mink |
| [`foam`](https://github.com/CoMMALab/foam) | offline tool (`tools` stage) | `116928f71aaa7c40356d79c84d3c9ff1f4497d90` | URDF mesh → sphere approximation |
| `lerobot[smolvla]` | `vla` venv | **same version as the policy-server image** (**TBD**, P5-T01) | `robot_client`, plugin discovery |
| [`lerobot-robot-ros`](https://github.com/ycheng517/lerobot-ros) | `vla` venv | `dabe6c6c7637c2f139e1c9964864a64921893ba1` | `ROS2Robot` / `ROS2Config` LeRobot plugin over rclpy |
| `openai` | `vlm` venv | **TBD** (P4-T02) | OpenAI-compatible client with tool calling (talks to llama-swap) |
| `nvidia-ml-py` | `core` venv | `13.610.43` | NVML for `gpu_monitor` |
| `numpy` | `core` venv | `1.26.4` (= Ubuntu Noble `python3-numpy`) | Keeps apt ROS extensions (moveit_py) on the numpy ABI they were built with |
| [`so101-nexus`](https://pypi.org/project/so101-nexus/) | `tools` stage (scene export) and `vla-eval` (LeRobot-native eval) | `0.6.0` | SO-101 MuJoCo task scenes + LeRobot EnvHub envs for checkpoint sanity evaluation |
| [`rai`](https://github.com/RobotecAI/rai) (candidate) | `vlm` venv | `6802d4073e8caa2ab72c5509fa1eeeb659663f64` (if adopted by P4-T01) | Agent runtime with ROS 2 connectors/tools (Apache-2.0, Jazzy, py3.12) |

## 6. Models and checkpoints

| Model | Source | Variant | Served by |
|---|---|---|---|
| Qwen3-VL-4B-Instruct | [`Qwen/Qwen3-VL-4B-Instruct-GGUF`](https://huggingface.co/Qwen/Qwen3-VL-4B-Instruct-GGUF) | `Qwen3VL-4B-Instruct-Q4_K_M.gguf` + `mmproj-Qwen3VL-4B-Instruct-Q8_0.gguf` | llama-swap → llama-server |

### 6.1 Policy checkpoints (candidates for P5-T02)

Downloaded with `cognibot_ws/src/cognibot_vla/scripts/download_checkpoints.sh` into the HF cache (`~/.cache/huggingface`, ~4.5 GB), which the `policy-server` service mounts. All take `observation.state` (6) and output a 6-D joint action. Real-arm and Isaac Sim checkpoints are kept as references; a visual domain gap makes them unlikely to succeed in MuJoCo.

| Name | Repo @ revision | Policy | Trained in | Image inputs | License |
|---|---|---|---|---|---|
| `smolvla_base` | [`lerobot/smolvla_base`](https://huggingface.co/lerobot/smolvla_base) @ `c83c3163b8ca9b7e67c509fffd9121e66cb96205` | SmolVLA (bf16) | pretraining on community real-arm data | `camera1..3` 256×256 | Apache-2.0 |
| `smolvla_mujoco_tray` | [`bendca61/smolvla-mujoco-so101-cube_on_tray`](https://huggingface.co/bendca61/smolvla-mujoco-so101-cube_on_tray) @ `d9da3285e866aa6464ea1c6e71363d03d4c85682` | SmolVLA | MuJoCo SO-101 | `realsense`, `wrist_cam` 640×480 | Apache-2.0 |
| `smolvla_isaac_orange` | [`edge-inference/smolvla-so101-pick-orange`](https://huggingface.co/edge-inference/smolvla-so101-pick-orange) @ `71cf4a9d35ce317f6706efe1a9f9d4cbb2b8fb4d` | SmolVLA | Isaac Sim SO-101 (LeIsaac) | `front`, `wrist` 640×480 | Apache-2.0 |
| `act_mujoco_tray` | [`bendca61/act-so101-mujoco-cube_on_tray-v1`](https://huggingface.co/bendca61/act-so101-mujoco-cube_on_tray-v1) @ `676050ad8a25816c238389a31795d1498691ec32` | ACT (chunk 100) | MuJoCo SO-101 | `realsense`, `wrist_cam` 640×480 | Apache-2.0 |
| `act_mujoco_pickplace` | [`szk1ck/so101-pickplace-sim-mujoco`](https://huggingface.co/szk1ck/so101-pickplace-sim-mujoco) @ `3dcc200be7aa0f8b19130586ab7b99d6ff304494` | ACT (chunk 100) | MuJoCo SO-101 | `front`, `wrist` 640×480 | Apache-2.0 |
| `diffusion_real_cube` | [`Chaenn/diffusion_so101_cube_multitask_hil_0729`](https://huggingface.co/Chaenn/diffusion_so101_cube_multitask_hil_0729) @ `1d39f411a36821e4b885f7d7dee1ac51ed0d4fb1` | Diffusion (15 action steps) | real SO-101 (no MuJoCo diffusion checkpoint found on the Hub, 2026-09-13) | `side`, `wrist` 640×480 | Apache-2.0 |

Relevant **datasets** (for camera and scene parity, not training): [`johnsutor/MuJoCoPickAndPlace-v1`](https://huggingface.co/datasets/johnsutor/MuJoCoPickAndPlace-v1), [`johnsutor/MuJoCoPickLift-v1`](https://huggingface.co/datasets/johnsutor/MuJoCoPickLift-v1), [`bendca61/vla-mujoco-so101-cube_on_tray-leader-v1`](https://huggingface.co/datasets/bendca61/vla-mujoco-so101-cube_on_tray-leader-v1). P5-T05 picks the checkpoint whose **camera names, image sizes and scene** are closest to our sim, and configures the `lerobot_robot_cognibot` camera keys to match (e.g. `realsense`, `wrist_cam`).

Pin model revisions by HF commit hash in config once they're chosen.

## 7. Glue we write (and why nothing upstream covers it)

| Glue | Reason |
|---|---|
| `cognibot_sim` robot registry, xacro wrapper with `<ros2_control>`, scene export script | Upstream so101 ROS stack has no MuJoCo support ("planned"); Menagerie and so101-nexus have no ROS wiring |
| `lerobot_robot_cognibot` (LeRobot robot config plugin) | Registers our joint names, topics and cameras on top of `lerobot_robot_ros` |
| `lerobot_camera_ros2` (LeRobot camera plugin) | `lerobot_robot_ros` reads cameras through LeRobot `CameraConfig` (OpenCV/RealSense) and has no ROS image topic camera. Adapt the ROS 2 camera from LeRobot PR [#866](https://github.com/huggingface/lerobot/pull/866) (credited) |
| `mode_manager`, `safety_filter` | Project-specific arbitration and sphere-based filtering of streamed commands |
| `mink_teleop` | Thin ROS wrapper around mink for WASD Cartesian jogging |
| `reach_query` | Runtime query service over a stored REACH study |
| `pick_place_server` | Scripted fetch/place sequences on top of MoveItPy |
| `vlm_agent_node` + tools + grounding | ROS tool bindings and bbox → 3D deprojection. The **agent loop itself comes from RAI** if P4-T01 confirms it works with an OpenAI-compatible local endpoint; otherwise a thin `openai` SDK loop |
| `skill_executor_node` | Exposes LeRobot `robot_client` as a ROS 2 action with VRAM handoff |
| `twin_mirror` | Relays the real arm's joint states into the sim command path |
| Dashboard | Project UI |

## 8. Considered and not used

| Component | Why not |
|---|---|
| Ollama | llama.cpp was the project's preferred runtime; llama-swap gives explicit unload control and direct llama-server flags |
| vLLM | Pre-allocates VRAM; poor fit next to SmolVLA on 6 GB |
| `so101-ros-physical-ai` `so101_inference` | SO-101-specific and pixi-based; the stock LeRobot `robot_client` + `lerobot_robot_ros` stays robot-agnostic (Panda) |
| `ROBOTIS lerobot_robot_ros2_zenoh` | Requires a Zenoh router and unpublished local SDK packages |
| MoveIt Servo for teleop | 5-DOF SO-101 can't track 6-D twists cleanly; mink handles task weighting natively |
| cuRobo | Excellent sphere-based planning, but its VRAM footprint competes with the models |
| ROS 2 Humble | Python 3.10 is incompatible with current LeRobot ([ADR-0001](adr/0001-jazzy-over-humble.md)) |
| [MuRain37/so101-ros2-mujoco](https://github.com/MuRain37/so101-ros2-mujoco) | Jazzy + MuJoCo + SmolVLA, but a custom sim node instead of ros2_control, synchronous inference, 1★, only weeks old. Useful as a reference |
| [nimicurtis/so101_ros2](https://github.com/nimicurtis/so101_ros2) | LeRobot ↔ ROS 2 hardware bridge with Isaac Sim focus; no MuJoCo |
| [adoodevv/so101_ros2](https://github.com/adoodevv/so101_ros2) | Good SO-101 description + MoveIt + Gazebo (BSD-3); overlaps legalaspro's stack, which also brings the Feetech driver we need for the twin |
| [Pavankv92/lerobot_ws](https://github.com/Pavankv92/lerobot_ws) | SO-101 ROS 2 + Gazebo used by lerobot-ros examples; Gazebo-centric, last push 2025-07 |
| [PhysAI-Robot/physai-robot-starter](https://github.com/PhysAI-Robot/physai-robot-starter) | SO-101 in MuJoCo + SmolVLM planner idea, but Phase-1 maturity with a custom bridge |
| [isaka1022/so101-sim2real](https://github.com/isaka1022/so101-sim2real) (`lerobot-env-so101`) | Single pick-cube task with a 4-D Cartesian action space; doesn't match joint-space SmolVLA checkpoints |
| [huggingface/gym-hil](https://github.com/huggingface/gym-hil) | Official LeRobot MuJoCo env, but Panda human-in-the-loop RL, not SO-101 tabletop VLA |
| [nasa-jpl/rosa](https://github.com/nasa-jpl/rosa) | Excellent ROS introspection agent; less suited to manipulation tool-calling than RAI |
| RAI manipulation demo perception (Grounding DINO + SAM 2) | Extra GPU models don't fit the 6 GB budget; Qwen3-VL grounding replaces them |
