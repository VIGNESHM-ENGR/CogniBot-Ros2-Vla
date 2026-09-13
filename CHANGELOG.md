# Changelog

All notable changes to this project are documented here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses [Semantic Versioning](https://semver.org/).

The engineering narrative (problems, root causes, decision trees) lives in [docs/DEVLOG.md](docs/DEVLOG.md). This file lists user-visible changes only.

## [Unreleased]

### Added
- `robot_color` launch argument (`red` default, `stock`) that recolors the robot via `cognibot_common.mjcf_tint` and `mjcf.tint_materials` in the robot registry.
- `make test` (all workspace tests, including GPU launch tests, in the core image) and `make deps` (fetch pinned third-party sources on the host).
- `cognibot_vla/scripts/download_checkpoints.sh`: pinned download of SmolVLA base, two SmolVLA fine-tunes, two MuJoCo ACT policies and one Diffusion policy for SO-101.
- `make demo`: opens the MuJoCo viewer and runs a scripted SO-101 pick-and-place (`cognibot_motion/scripts/demo_pick_place.py`).
- MoveIt 2 for SO-101 with position-only pick_ik: `cognibot_motion` `move_group.launch.py` (`rviz:=true`), `move_to_point` command and launch test.
- `make moveit`: MuJoCo viewer plus RViz MotionPlanning for interactive IK goals.
- `bridge` service: rosbridge WebSocket (:9090) and MJPEG camera streams (:8080) on loopback; `make sim` starts it with the simulation.
- Operator pendant dashboard (Vite + React + roslib): live front/wrist cameras, joint readouts against URDF limits, VRAM gauge, controller list, MoveIt named poses, gripper and move-to-point, latching STOP on Esc; `make dashboard`.
- `make sim` also starts MoveIt (`motion` service) and the GPU monitor.
- Dashboard free-look 3D view (MuJoCo WASM + three.js on the simulator's own scene, live joints and cube), switchable with the front and wrist cameras (`V`).
- `pick_place_server` with `FetchObject`/`PlaceObject` (scripted IK) and `/cognibot/sim/reset_objects`; dashboard Motion view gets Pick and place and Reset cube.
- Live object poses on `/object_poses/free_joint_states` from mujoco_ros2_control's free-joint publisher plugin.
- `mode_manager`: `/cognibot/set_mode` switches ros2_control controllers per `modes.yaml` and publishes `/cognibot/mode`; the dashboard mode key and STOP drive it.
- `cognibot_common.qos` presets (sensor data, reliable command, transient local).
- `safety_filter`: sole publisher of `/arm_position_controller/commands`; enforces joint ranges, `max_joint_velocity` and a 300 ms dead-man, forwards only in TELEOP/VLA/TWIN, publishes `/cognibot/safety/status` (collision check follows with P2-T03).
- `mink_teleop`: Cartesian jogging from `TeleopCommand` through mink IK to the safety filter, with workspace and dead-man limits (collision avoidance follows P2-T03).
- Dashboard jog keys (W/S, A/D, ↑/↓, G) publish at 30 Hz while held and move the simulated arm in TELEOP.
- VLA inference path: pinned LeRobot `policy-server` image, `lerobot_robot_cognibot` plugin (ROS 2 joint states and cameras in, `/cognibot/joint_command` out), `run_robot_client.sh`, `make vla` and `make skill`; verified live with ACT and SmolVLA checkpoints.
- `download_checkpoints.sh` fetches the SmolVLM2 backbone and writes uncompiled SmolVLA variants under `$HF_HOME/cognibot/`.

### Changed
- The scene manipuland is now `green_cube` (was `red_cube`) in both SO-101 and Panda scenes, so red is reserved for the robot.
- The core image fetches third-party ROS sources from `third_party.repos` instead of the build context; `.dockerignore` added.
- `make sim-dev` starts only the `sim` service with the viewer; `ROBOT_COLOR` is passed through compose.
- `policy-server` mounts the host Hugging Face cache (`HF_CACHE_DIR`, default `~/.cache/huggingface`) instead of a named volume.
- SO-101 `wrist_cam` renders at 640×480 instead of 1920×1080 (headless GPU 40% → 26%, VRAM 587 → 385 MiB).
- The dashboard image builds from the repository root so it can bundle the simulator scene.

### Fixed
- CI `ros` job now installs MuJoCo and third-party sources and runs the GPU-free tests.
- Core venv pins numpy 1.26.4 so apt ROS extensions (moveit_py) no longer segfault against numpy 2.
- GUI containers render through NVIDIA PRIME offload instead of software GL on hybrid-graphics laptops.
- MoveIt goals no longer fail after a motion parks a joint on its limit: the dashboard eases it back inside first, and the pick-and-place IK stays 0.01 rad inside limits.
- Dashboard motion keys are disabled while a program runs and `move_group` respawns, so a second goal can no longer crash MoveIt.
- Free-look view draws the arm and objects from the same sim instant; the carried cube no longer stutters.

## [0.2.0] - 2026-09-13

### Added
- Headless MuJoCo simulation core with `mujoco_ros2_control` in `cognibot_sim`.
- Pinned MuJoCo Menagerie models for SO-101 and Franka Panda robots at commit `8161bba`.
- Exported deterministic `so101_pick_and_place.xml` scene from `so101-nexus==0.6.0` with table, manipuland, target, and cameras.
- SO-101 and Franka Panda URDF/xacro descriptions integrating `<ros2_control>` hardware interface.
- Controller configurations: `joint_state_broadcaster`, `joint_trajectory_controller`, `gripper_controller`, and inactive `arm_position_controller` running at 100 Hz.
- Camera publishing on `/mujoco_camera_plugin/...` at 20 Hz with optical frame static TF publishers and reprojection verified (< 3 px error).
- Robot registry schema and loader in `cognibot_common.robot_registry` with support for `so101` and `panda`.
- `gpu_monitor` node in `cognibot_common` publishing `GpuStatus` messages on `/cognibot/gpu` with NVML monitoring and mock fallback.
- Python dependency management with `uv` and locked dependencies in `uv.lock`.

### Fixed
- Lowered CycloneDDS minimum receive buffer in `cyclonedds.xml` to 2 MB to fit default Linux kernel `rmem_max`.
- Resolved camera optical axis frame transformation from MuJoCo camera coordinates to ROS convention (+Z forward, +X right, +Y down).
- Aligned Franka Panda finger actuator to direct joint control for compatibility with `mujoco_ros2_control`.
- Fixed XML declaration leading spaces across workspace `package.xml` files.
- Declared missing `so101_description`, `moveit_resources_panda_description`, `tf2_ros` and Python dependencies in package manifests.
- Scoped host `pytest` to ROS-free tests and cleaned all ruff lint and format findings.

## [0.1.0] - 2026-09-13

### Added
- README with architecture overview, profiles, quick start and roadmap.
- CI workflow (ruff, commit-message policy on PRs, compose validation for all profiles, colcon build/test on Jazzy), pre-commit hooks and ruff configuration.
- Multi-stage Dockerfile (`interfaces`, `core` on `moveit/moveit2:jazzy-release`, `tools`, `vlm`, `vla`), Compose stack with `vlm` / `vla` / `twin` / `full` profiles, dev X11 override, CycloneDDS loopback profile, llama-swap config with GPU/hybrid/CPU Qwen3-VL-4B profiles, and a `Makefile`.
- Engineering devlog (`docs/DEVLOG.md`) recording work, problems with root causes and solutions, and decision trees; backfilled for planning and scaffolding.
- ROS 2 Jazzy workspace skeleton: `cognibot_interfaces`, `cognibot_common`, `cognibot_sim`, `cognibot_motion`, `cognibot_teleop`, `cognibot_vlm`, `cognibot_vla`, `cognibot_twin`, `cognibot_bringup`.
- `cognibot_interfaces`: 5 messages, 3 services and 5 actions generated from `docs/ROS_INTERFACES.md`.
- `cognibot_ws/third_party.repos` pinning so101-ros-physical-ai, feetech_ros2_driver, REACH and reach_ros2.
- Project documentation: scope, plan, architecture, networking, ROS interfaces, VRAM budget, integrations, setup, ADR-0001…0006, third-party notices.
- Repository foundation: Apache-2.0 license, ignore/attribute/editor configs, `commit-msg` hook enforcing Conventional Commits and single authorship.
