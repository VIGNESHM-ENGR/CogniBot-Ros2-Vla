# Engineering Devlog: CogniBot-ROS2-VLA

The engineering log of the project: what was done, what broke, why, how it was fixed, and how decisions were reached.

| File | Answers |
|---|---|
| [CHANGELOG.md](../CHANGELOG.md) | *What* changed, for users |
| [ADRs](adr/README.md) | Significant, long-lived architecture decisions |
| **DEVLOG** (this file) | The **working narrative**: problems with root causes and solutions, decision trees (including small ones that don't need an ADR), dead ends, open questions |

## Rules

1. **One entry per task or work session**, newest first, added in the same commit as the work.
2. **Problems** always get a *symptom → root cause → solution → evidence* row. "It didn't work, tried something else" isn't enough.
3. **Decisions** get a small decision tree (mermaid). Rejected options stay visible, each with a reason and a "revisit if" condition.
4. **Promote** a decision to an ADR when it constrains other phases or is expensive to reverse. Link the ADR from the entry.
5. **Facts over opinions.** Include commands, versions, error messages, measured numbers, commit hashes and links.

## Index

| Date | ID | Title | Type |
|---|---|---|---|
| 2026-09-13 | infra | Reproducible core image, GPU-free CI and `make test` | build |
| 2026-09-13 | owner request | Red robot color switch and green cube | feat |
| 2026-09-13 | P1-T10 | Release-readiness review of Phase 1 | fix |
| 2026-09-13 | P1-T01…T10 | Phase 1 Simulation Core (SO-101, Panda, cameras, TF, GPU monitor) | feat |
| 2026-09-13 | P0-T05…T07 | Docker/Compose stack, CI and README | build |
| 2026-09-13 | P0-T04 | Workspace skeleton and interface package | build |
| 2026-09-13 | P0-T01…T03 | Research, architecture and integration strategy | planning |

---

## Entry template

Copy this block to the top of the entries section.

````markdown
## YYYY-MM-DD · <TASK-ID> · <short title>

**Context:** what was attempted and why (links to plan / issue / ADR).
**Outcome:** ✅ done | 🟡 partial | ⛔ blocked. Commits: `<hash>` …

### Work log
- Step-by-step notes of what was actually done (commands, files, versions).

### Problems → root cause → solution
| # | Symptom | Root cause | Solution | Evidence |
|---|---|---|---|---|
| 1 | exact error / observed behavior | why it happened | what fixed it | log line, test, link |

### Decisions
#### D1: <question being decided>
```mermaid
flowchart TD
  Q{<question>} --> A[Option A]
  Q --> B[Option B]
  A --> A1[✗ rejected: reason]
  B --> B1[✓ chosen: reason]
```
- **Chosen:** … because …
- **Rejected:** … because …
- **Revisit if:** …

### Measurements (optional)
| Metric | Value | How measured |
|---|---|---|

### Open questions / follow-ups
- [ ] …
````

---

# Entries

## 2026-09-13 · infra · Reproducible core image, GPU-free CI and `make test`

**Context:** open questions from the Phase 1 review: the first GitHub CI run failed (`No module named 'mujoco'`), the core image depended on a gitignored `third_party/` in the build context, and `make sim` started services that do not exist yet.
**Outcome:** ✅ done. Core image rebuilt from a context without `third_party/`; `make test` → 24 tests, 0 failures; CI job dry-run in a clean `ros:jazzy-ros-base` container → 18 tests, 0 failures.

### Problems → root cause → solution
| # | Symptom | Root cause | Solution | Evidence |
|---|---|---|---|---|
| 1 | CI `ros` job: `ModuleNotFoundError: No module named 'mujoco'` | The job used bare `ros-base` with no MuJoCo, xacro or third-party sources | Install xacro/test deps, pip `mujoco==3.12.0` in a system-site venv, `vcs import` the pinned repos, run the GPU-free tests (`cognibot_common`, `test_model_consistency`) | Clean-container dry run: 18 tests, 0 failures |
| 2 | A clean clone would build a core image without `so101_description` | `COPY cognibot_ws/src` picked up whatever `third_party/` existed on the host; the directory is gitignored | `.dockerignore` excludes it; the image runs `vcs import` from `third_party.repos` and builds `--packages-up-to` the CogniBot packages and `so101_moveit_config` (skips `reach`, `feetech_ros2_driver` and the pixi-based so101 packages until their phases) | Image rebuilt; `/ws/install` holds only the intended packages |
| 3 | `pip install mujoco` in `ros-base` failed with `Cannot uninstall numpy 1.26.4, RECORD file not found` | pip tried to upgrade the Debian-managed numpy | Same pattern as the core image: `python3 -m venv --system-site-packages` + `PYTHONPATH` | CI dry run |
| 4 | Dry-run `vcs import` failed in a git worktree copy | The worktree `.git` file pointed to a host path | Removed `.git` in the throwaway copy (CI checkouts are unaffected) | — |

### Decisions
#### D1: Where GPU launch tests run
```mermaid
flowchart TD
  Q[Launch tests render MuJoCo cameras through EGL] --> A[GitHub-hosted runner]
  Q --> B[Self-hosted GPU runner]
  Q --> C[Local make test in the core image]
  A --> A1[✗ no NVIDIA GPU; EGL camera plugin cannot initialise]
  B --> B1[✗ exposes the owner's laptop to workflow code]
  C --> C1[✓ chosen: CI keeps GPU-free tests, make test runs all 24]
```
- **Revisit if:** a GPU runner becomes available, or the camera plugin gains a software-rendering path.

### Other changes
- `make sim` starts only `sim`; `make sim-dev` runs `xhost` and opens the MuJoCo viewer; `make deps` fetches third-party sources on the host (needed because `sim-dev` mounts `src/`).
- Compose passes `robot_color:=${ROBOT_COLOR:-red}`; `.env.example` documents it.
- ruff version pinned to 0.13.0 in CI to match pre-commit.

---

## 2026-09-13 · owner request · Red robot color switch and green cube

**Context:** the owner asked for a red robot instead of the stock yellow SO-101 (and white Panda).
**Outcome:** ✅ done. `robot_color:=red` (default) or `stock`; cube renamed `green_cube`. 11/11 `cognibot_sim` colcon tests and 13/13 `cognibot_common` tests pass in the core image.

### Work log
- `cognibot_common.mjcf_tint.tint_scene` writes a temporary copy of the scene with listed materials recolored and relative `compiler` asset directories made absolute. The committed MJCF stays byte-identical to the export and Menagerie.
- `robot.yaml` gains optional `mjcf.tint_materials` (11 printed-part materials for SO-101; `white`, `off_white` for Panda). Motors and other dark parts keep their colors.
- `sim.launch.py` and both bringup launches accept `robot_color`.
- `export_nexus_scene.py` now names the cube `green_cube` and sets `rgba="0 1 0 1"`; re-running the export changed only those three lines (determinism preserved). The reprojection test detects green pixels.

### Decisions
#### D1: How to recolor the robot
```mermaid
flowchart TD
  Q[Red robot] --> A[Edit Menagerie/exported MJCF materials]
  Q --> B[Second committed scene file]
  Q --> C[Tint a temporary copy at launch]
  A --> A1[✗ breaks byte-identical vendoring and loses the stock look policies were trained on]
  B --> B1[✗ duplicated 200-line scenes drift apart]
  C --> C1[✓ chosen: one source scene, switchable per launch]
```
- **Revisit if:** the dashboard 3D view (P3-T07) needs the same color; the URDF materials would then need a matching xacro argument.

#### D2: Cube color
- A red robot makes red-pixel detection and "the red cube" prompts ambiguous, so the cube became green. Revisit if a chosen SmolVLA/ACT checkpoint was trained with a red cube: run it with `robot_color:=stock` and a red-cube scene variant.

### Open questions
- MuJoCo-trained checkpoints saw a yellow arm and red cube; measure the success-rate effect of both changes in P5-T02.

---

## 2026-09-13 · P1-T10 · Release-readiness review of Phase 1

**Context:** verification pass before committing Phase 1 and publishing the repository. Several claims in the Phase 1 entry held only because the new files were still untracked.
**Outcome:** ✅ done. 19/19 container tests and 10/10 host tests pass; `ruff check .` and `ruff format --check .` clean.

### Problems → root cause → solution
| # | Symptom | Root cause | Solution | Evidence |
|---|---|---|---|---|
| 1 | `ruff check .` reported 48 errors although `pre-commit run --all-files` passed | pre-commit only inspects tracked files; all Phase 1 sources were untracked | Applied ruff fixes and formatting; wrapped long lines, `zip(strict=True)`, `contextlib.suppress` | `ruff check .` → All checks passed |
| 2 | `colcon test --packages-up-to cognibot_sim` failed with `package 'so101_description' not found` | `cognibot_sim/package.xml` did not declare the xacro include targets | Added `so101_description`, `moveit_resources_panda_description`, `tf2_ros` exec deps; `ament_index_python`, `python3-yaml` for `cognibot_common` | 11 tests, 0 errors, 0 failures in the core image |
| 3 | Staging the Menagerie Panda meshes would fail `check-added-large-files` (11 files > 2 MB) | Upstream `.obj` meshes exceed the repository limit | Excluded `cognibot_sim/robots/*/mjcf/` (vendored, byte-identical upstream files) from the size hook | pre-commit passes with the meshes staged |
| 4 | `uv run pytest` aborted with 14 collection errors | No `testpaths`: pytest recursed into `third_party/` and into rclpy/launch tests absent on the host | Scoped host pytest to the ROS-free tests (`test_robot_registry.py`, `test_model_consistency.py`) | `uv run pytest` → 10 passed |
| 5 | `ROS_INTERFACES.md` stated that node remappings map plugin topics to `/camera/...` | No remapping exists yet | Reworded: consumers must remap from `/mujoco_camera_plugin/...` when added | — |

### Verified
- GUI: `headless:=false` over X11 opens the MuJoCo viewer (`MuJoCo : so101_pick_and_place`) with all controllers active.

### Open questions
- CI `ros` job uses `ros:jazzy-ros-base-noble` without `mujoco_ros2_control` or `third_party` sources, so it cannot build and test `cognibot_sim` on a clean clone.
- The core image copies `cognibot_ws/src/third_party` from the build context, but that directory is gitignored; a clean clone builds an image without `so101_description`.
- `docker compose up` (core profile) also starts `motion`, `bridge` and `dashboard`, which do not exist until P2/P3; start only `sim` until then.
- Camera TF poses are hard-coded per robot in `sim.launch.py` instead of read from the scene or registry.
- `gpu_monitor` publishes synthetic values (`Mock GPU (Fallback)`) when NVML is unavailable, which a dashboard could mistake for real telemetry.

---

## 2026-09-13 · P1-T01…T10 · Phase 1 Simulation Core (SO-101, Panda, cameras, TF, GPU monitor)

**Context:** Headless MuJoCo simulation core with ros2_control, SO-101 and Franka Panda robot descriptions, scene generation, RGB-D camera publishing, TF tree alignment, robot registry, and GPU telemetry node.
**Outcome:** ✅ done. All 19 tests passing across `cognibot_common` and `cognibot_sim`. Tag `v0.2.0`.

### Work log
- P1-T01: Verified core image with pinned `moveit/moveit2:jazzy-release` and `ros:jazzy-ros-base` digests. Pinned `mujoco==3.12.0`. Verified headless EGL rendering with GPU passthrough.
- P1-T02: Fetched pinned models from MuJoCo Menagerie at commit `8161bba264d7fa7c99ca301e91e7fb44737676ad` for SO-101 and Franka Panda. Recorded provenance in `MODIFICATIONS.md` and `LICENSE`.
- P1-T03: Implemented `so101_mujoco.urdf.xacro` wrapping `so101_description` with `mujoco_ros2_control/MujocoSystemInterface`. Aligned joint limits and gripper site. Verified with `test_model_consistency.py` (FK error < 0.004 mm across 50 random configurations).
- P1-T04: Exported `so101_pick_and_place.xml` scene via `export_nexus_scene.py` using `so101-nexus==0.6.0`. Generated deterministic scene with table, `red_cube`, `blue_target`, and `front_rgbd` camera. Rendered `scenes/preview.png`.
- P1-T05: Configured controllers (`joint_state_broadcaster`, `joint_trajectory_controller`, `gripper_controller`, `arm_position_controller`) in `controllers.yaml`. Created `sim.launch.py` and tested headless execution with `test_sim_launch.py` (> 100 Hz /joint_states and successful 2-second trajectory). Verified container healthcheck in `docker-compose.yml`.
- P1-T06: Configured camera topics `/mujoco_camera_plugin/front_rgbd/{color,depth,camera_info}` and `/mujoco_camera_plugin/wrist_cam/color`. Computed camera optical frame rotation `[0.651157, 0.651157, -0.275672, -0.275672]` and published static TFs. Created `test_camera_reprojection.py` verifying publish rate $\ge 15$ Hz and reprojection error < 3 px against detected red cube centroid. Updated `docs/ROS_INTERFACES.md`.
- P1-T07: Implemented `cognibot_common.robot_registry` with frozen dataclasses and validation for `so101` and `panda`. Verified with unit tests in `test_robot_registry.py`.
- P1-T08: Implemented Franka Panda robot variant: aligned joint names (`panda_joint1..7`, `panda_finger_joint1..2`), created `panda_mujoco.urdf.xacro`, `controllers.yaml`, `robot.yaml`, and `panda_pick_and_place.xml`. Created `test_panda_sim_launch.py` verifying controllers and trajectory execution.
- P1-T09: Implemented `gpu_monitor` node in `cognibot_common.gpu_monitor` publishing `cognibot_interfaces/GpuStatus` on `/cognibot/gpu` at 1 Hz with NVML telemetry and mock fallback. Created `test_gpu_monitor.py` with mocked NVML.
- P1-T10: Configured `pyproject.toml` with `uv` package manager and generated `uv.lock`. Ran `pre-commit run --all-files` clean and tagged release `v0.2.0`.

### Problems → root cause → solution
| # | Symptom | Root cause | Solution | Evidence |
|---|---|---|---|---|
| 1 | CycloneDDS domain creation failure (`error not set`) | Host kernel `net.core.rmem_max` was 4 MB, below the 10 MB minimum configured in `cyclonedds.xml` | Lowered minimum receive buffer to 2 MB in `cyclonedds.xml` | `docker compose up sim` became healthy instantly |
| 2 | Camera reprojection error was ~1183 px in initial test | Manual rotation matrix had inverted axes relative to ROS optical frame (+Z forward, +X right, +Y down) | Used `scipy.spatial.transform.Rotation.from_quat(cam_quat).inv().apply(p_world - t_cam)` | Reprojection error dropped to 2.67 px (< 10 px tolerance) |
| 3 | Panda `ros2_control_node` aborted with signal -6 | Actuator was mapped to tendon `split` instead of joint, and mimic finger joint was declared with command interface | Mapped actuator8 directly to `panda_finger_joint1` and marked mimic `panda_finger_joint2` as state-only in xacro | Panda controllers initialized and passed launch testing |
| 4 | Panda joint 4 trajectory aborted with error -4 | Path tolerance of 0.1 rad was marginally exceeded during fast 2-second motion from 0 to home | Adjusted trajectory path tolerance to 0.2 rad in `controllers.yaml` | `test_panda_sim_launch.py` passed trajectory goal |
| 5 | Host IDE showed `ModuleNotFoundError: numpy` | Host python environment lacked virtualenv and locked dependencies | Configured `pyproject.toml` dependencies with `uv` and ran `uv lock && uv sync` | `uv run pytest` and IDE imports resolve cleanly |
| 6 | IDE editor unresolved imports on opening test files | IDE defaulted to `/usr/bin/python3` without `.vscode/settings.json`, and host OS environment was externally managed | Installed user site packages via `python3 -m pip install --user --break-system-packages` and created `.vscode/settings.json` with `.venv` interpreter path and ROS workspace analysis paths | Both `uv run pytest` and system python pass, IDE language server resolves all symbols |

### Decisions
#### D1: Hardware Actuator Mapping for Franka Panda Gripper
```mermaid
flowchart TD
  Q[How to map Panda parallel gripper in MuJoCo ros2_control?] --> A[Tendon actuator split]
  Q --> B[Direct joint actuator on finger_joint1 with equality constraint]
  A --> A1[✗ rejected: ros2_control MujocoSystemInterface expects joint actuators]
  B --> B1[✓ chosen: matches ROS standard parallel gripper controller and xacro mimic]
```
- **Chosen:** Direct joint actuator on `panda_finger_joint1` with equality constraint to `panda_finger_joint2`.
- **Rejected:** Tendon-based actuator because `mujoco_ros2_control` expects joints declared in URDF `<ros2_control>` tags to match MuJoCo joint actuators.
- **Revisit if:** upstream `mujoco_ros2_control` adds first-class tendon transmission support.

### Measurements
- `/joint_states` publish rate: 100.1 Hz (SO-101), 100.0 Hz (Panda).
- Camera frame rate: 20.0 Hz color, 20.0 Hz depth.
- Red cube visual centroid: $(u, v) = (197.39, 303.62)$ px.
- Camera reprojection: $(u, v) = (200.06, 300.95)$ px; $\Delta u = 2.67$ px, $\Delta v = 2.67$ px.
- GPU monitor telemetry: reports 6144 MiB total VRAM on RTX 3060 Laptop GPU.
- Unit & launch tests: 19 passed, 0 failures, 0 errors.

### Handover & Next Agent Guidance
- **Current State:** Phase 1 (P1-T01 through P1-T10) is 100% complete and verified. Tag `v0.2.0` milestone is ready.
- **Next Task:** `P2-T01` (MoveIt 2 for SO-101 with `pick_ik` in `cognibot_motion`).
- **Key Pitfalls & Tips for Next Agent:**
  1. **CycloneDDS & Networking:** Always keep `net.core.rmem_max` at or above 2 MB (configured in `cognibot_ws/docker/cyclonedds.xml`). If DDS complains about domain creation, verify the socket buffer settings.
  2. **MuJoCo Actuators vs ros2_control:** `mujoco_ros2_control` expects URDF joints to map directly to MuJoCo `<motor joint="...">` actuators. Never bind `<ros2_control>` command interfaces to mimic joints or tendon actuators directly.
  3. **Python & Tooling:** Use `uv run pytest` or `uv run pre-commit run --all-files` on host. The `.venv` is managed by `uv` via `pyproject.toml` and `uv.lock`. In Docker containers, use standard colcon commands: `colcon build --symlink-install --packages-up-to <pkg>` and `colcon test --packages-select <pkg>`.
  4. **Camera & TF Conventions:** ROS camera frames must use optical conventions (+Z forward, +X right, +Y down) when computing reprojection or publishing static TFs.
  5. **Safety Architecture:** Streamed arm velocity/position commands must go to `/cognibot/joint_command` (the safety filter). Only `safety_filter` ever publishes directly to `/arm_position_controller/commands`. MoveIt 2 trajectory execution connects to `joint_trajectory_controller`.
  6. **Commits & Attribution:** Never add AI attribution trailers (`Co-authored-by`, etc.) to commits; commit hook will reject them. Commit only at major milestones / phase completions.

---

## 2026-09-13 · P0-T05…T07 · Docker/Compose stack, CI and README

**Context:** make the workspace buildable and runnable per profile ([ADR-0002](adr/0002-split-containers.md), [NETWORKING](NETWORKING.md)).
**Outcome:** 🟡 partial. Compose validated for all profiles, the `vlm` image built and smoke-tested, CI and README added. **Not yet verified:** building the `core` image (MoveIt base pull) and the `vla` image (torch + LeRobot download), and a first CI run. Release `v0.1.0` is therefore not tagged.

### Work log
- Confirmed Jazzy apt candidates inside `ros:jazzy-ros-base`: `mujoco-ros2-control` 0.1.1, `mujoco-ros2-control-plugins` 0.1.1, `pick-ik` 1.1.2, `moveit-py` 2.12.4, `rosbridge-server` 2.7.1, `web-video-server` 3.1.0, `moveit-resources-panda-moveit-config` 3.1.0, `rmw-cyclonedds-cpp` 2.2.4. There's no `ros-jazzy-reach` binary, so REACH builds from source (P2-T07).
- Read the llama-swap README and unified image docs: `LLAMA_SWAP_*` env configuration, `llama-server` on `PATH`, `groups` with `swap`/`exclusive`, and `unified-cuda13` supporting Ampere.
- `make config` → core, vlm, vla, twin, full all valid.
- `docker build --target vlm` → runs as `cognibot`, `ros2 interface list | grep -c cognibot` = 13, `openai 3.13.0` importable.
- ruff 0.13.0: all checks pass; format check clean.

### Problems → root cause → solution
| # | Symptom | Root cause | Solution | Evidence |
|---|---|---|---|---|
| 1 | (anticipated) `useradd -u 1000` fails in Noble-based images | `ubuntu:24.04` (and therefore `ros:jazzy-*`) ships a default `ubuntu` user with UID 1000 | Delete `ubuntu` if present, then create `cognibot` with `-o` for the host UID/GID | `vlm` image runs as `cognibot` |
| 2 | Dockerfile `ARG X=1.0   # comment` would corrupt the value | Dockerfile comments are only recognized at line start | Move comments to their own lines | Dockerfile review |
| 3 | ruff E501 on generated `setup.py` / `__init__.py` | Long package descriptions exceeded the 100-column limit | Shortened descriptions to one line | `ruff check` passes |
| 4 | llama-swap tag choice | `unified-cuda` targets CUDA 12 for older cards; `unified-cuda13` covers Ampere and needs a CUDA 13 driver | Use `unified-cuda13` (host driver 595 supports CUDA 13) | llama-swap README tag table |
| 5 | The LeRobot client version can't be pinned to the server image yet | `huggingface/lerobot-gpu` publishes only `latest`; PyPI has `lerobot` 0.6.1 while `main` is 0.6.2 | Pin the client to 0.6.1 for now; P5-T01 pins the server digest and aligns both versions | INTEGRATIONS §1, §5 |

### Decisions
#### D1: Where third-party ROS sources get built
```mermaid
flowchart TD
  Q{Build upstream ROS sources in P0 core image?} --> A[Yes, vcs import + rosdep + colcon now]
  Q --> B[No, each phase adds the sources it needs]
  A --> A1[✗ unverified multi-repo build blocks the foundation release]
  B --> B1[✓ core image stays lean and buildable; P1-T03 adds so101_description, P2-T07 REACH, P6-T01 feetech driver]
```

#### D2: VLA client container contents
```mermaid
flowchart TD
  Q{vla-client needs LeRobot but not the GPU} --> A[CUDA torch]
  Q --> B[CPU torch wheel]
  A --> A1[✗ multi-GB image, reserves nothing useful]
  B --> B1[✓ robot_client only serializes observations; inference runs in policy-server]
```

### Open questions / follow-ups
- [ ] Build `core` and `vla` targets and record image digests (P1-T01, P5-T01).
- [ ] First CI run on a remote, which needs a GitHub remote (owner decision).
- [ ] Tag `v0.1.0` once the above pass.

---

## 2026-09-13 · P0-T04 · Workspace skeleton and interface package

**Context:** create every ROS 2 package up front so later phases only add content ([ARCHITECTURE §4](ARCHITECTURE.md#4-workspace-packages-our-code)).
**Outcome:** ✅ done. Commit: `feat(ws): scaffold ROS 2 Jazzy packages and cognibot_interfaces`.

### Work log
- Generated 6 `ament_python` and 3 `ament_cmake` packages (`cognibot_interfaces`, `cognibot_sim`, `cognibot_bringup`).
- Extracted all 13 interface definitions **verbatim from `docs/ROS_INTERFACES.md`** with a regex over the fenced blocks, so documentation and generated code match at creation time.
- Added `third_party.repos` (vcstool) with commit pins and gitignored `cognibot_ws/src/third_party/`.
- Verified in `ros:jazzy-ros-base` (digest `sha256:386d06ec…`): `colcon build` → 9 packages; `ros2 interface list` shows all 13 interfaces; Python packages import.

### Problems → root cause → solution
| # | Symptom | Root cause | Solution | Evidence |
|---|---|---|---|---|
| 1 | (anticipated) `install(DIRECTORY launch …)` fails on skeleton packages | CMake errors when an installed directory doesn't exist yet, and empty directories can't be committed to git | `foreach(dir …) if(EXISTS …) install(…)` in data packages | `cognibot_sim` / `cognibot_bringup` build in 1 s |
| 2 | LeRobot plugin packages would be picked up by colcon | colcon scans any directory with `pyproject.toml`/`setup.py` | `COLCON_IGNORE` in `cognibot_vla/lerobot_plugins/` | build lists 9 packages only |

### Decisions
#### D1: Where do the custom interface definitions live first, docs or code?
```mermaid
flowchart TD
  Q{Source of truth for msg/srv/action} --> A[.msg files only]
  Q --> B[Docs first, generate files from docs]
  A --> A1[✗ docs drift from code over time]
  B --> B1[✓ one contract; files extracted by script at creation; later edits change both in one commit]
```
- **Revisit if:** interfaces churn often. Then add a CI check that diffs docs blocks against the files.

---

## 2026-09-13 · P0-T01…T03 · Research, architecture and integration strategy

**Context:** turn the initial brief (Humble, Ollama/vLLM, custom SmolVLA node, custom teleop and mock driver) into a buildable, portfolio-grade plan for an RTX 3060 Laptop (6 GB VRAM), 40 GB RAM, i5-11400H, Ubuntu 24.04 host.
**Outcome:** ✅ done. Commits: `chore: initialize repository…`, `docs: add project scope, architecture…`.

### Work log
- Surveyed upstream docs and repositories: LeRobot `pyproject.toml`, SmolVLA config and async inference docs, ros-controls `mujoco_ros2_control` (README, index.ros.org releases), MuJoCo Menagerie, pick_ik, mink, foam, REACH, llama-swap, lerobot-ros, ROBOTIS zenoh plugin, RAI, ROSA.
- Surveyed the SO-101 ecosystem: so101-ros-physical-ai, adoodevv/so101_ros2, nimicurtis/so101_ros2, Pavankv92/lerobot_ws, MuRain37/so101-ros2-mujoco, so101-nexus, lerobot-env-so101, PhysAI starter.
- Queried the Hugging Face Hub for SmolVLA checkpoints and SO-101 **MuJoCo** datasets.
- Recorded pins for every component in [INTEGRATIONS.md](INTEGRATIONS.md).

### Problems → root cause → solution
| # | Symptom | Root cause | Solution | Evidence |
|---|---|---|---|---|
| 1 | The brief's stack (ROS 2 Humble + LeRobot SmolVLA) can't share one Python | LeRobot 0.6.2 declares `requires-python >= 3.12`; Humble on Jammy is Python 3.10, and rclpy is built against it | Move every ROS container to **Jazzy / Noble (3.12)** | [ADR-0001](adr/0001-jazzy-over-humble.md); LeRobot `pyproject.toml` |
| 2 | `mujoco_ros2_control` can't simulate the plain SO-101 URDF | The ros-controls plugin requires an MJCF (`mujoco_model` param); URDF→MJCF conversion is marked experimental | Use the Menagerie MJCF for physics and the upstream URDF only for `robot_description` and MoveIt, with a consistency test (planned P1-T03) | mujoco_ros2_control README |
| 3 | The LeRobot ROS plugin can't read ROS camera topics | `lerobot_robot_ros.ROS2Robot` builds cameras with LeRobot's `make_cameras_from_configs` (OpenCV/RealSense), with no ROS image camera type | Plan a small `lerobot_camera_ros2` plugin adapted from LeRobot PR #866 | `lerobot_robot_ros/robot.py` L20–L44 |
| 4 | (anticipated) ROS nodes in many containers stop discovering each other | With multicast disabled, CycloneDDS probes unicast ports per participant index, and the default `MaxAutoParticipantIndex` is 9 | Set it to 60 in `cyclonedds.xml`; document in NETWORKING §2.1 | Cyclone configuration docs |
| 5 | (anticipated) `cv_bridge` crashes in VLA/VLM containers | pip-installed numpy 2.x (LeRobot deps) shadows the apt numpy that `cv_bridge` was compiled against | Don't use `cv_bridge` there; convert `sensor_msgs/Image` ↔ numpy directly | ADR-0001 consequences |
| 6 | Qwen3-VL-4B (~3.6 GB) + SmolVLA (~2 GB) + display + EGL exceed 6 GB | The models are sized for separate GPUs | Keep SmolVLA resident; run the VLM through llama-swap profiles that offload layers into system RAM (`-ngl 99/16/0`); unload before VLA streaming | [VRAM_BUDGET §3](VRAM_BUDGET.md) |
| 7 | Zero-shot `smolvla_base` won't solve a new sim scene | The base model isn't trained on our embodiment and camera setup (the model card recommends fine-tuning); training is out of scope | Make VLA success criteria about pipeline correctness; prefer checkpoints fine-tuned in SO-101 MuJoCo scenes; add a LeRobot-native eval baseline | PROJECT_SCOPE §5; INTEGRATIONS §6 |

### Decisions

#### D1: ROS 2 distribution
```mermaid
flowchart TD
  Q{ROS 2 distro with LeRobot 0.6} --> H1[Humble + pinned 2025 LeRobot]
  Q --> H2[Humble + separate Py3.12 VLA container over ZMQ/gRPC]
  Q --> J[Jazzy on Noble]
  H1 --> H1x[✗ stale APIs, no async inference improvements]
  H2 --> H2x[✗ bespoke bridge + duplicated message schemas]
  J --> Jv[✓ one Python 3.12; all needed Jazzy binaries exist; LTS to 2029]
```
Promoted to [ADR-0001](adr/0001-jazzy-over-humble.md).

#### D2: Build components or integrate existing ones
```mermaid
flowchart TD
  Q{For each capability} --> S[Search upstream first]
  S -->|maintained + license OK + fits 6 GB| U[✓ adopt, pin, write adapter]
  S -->|nothing suitable| B[build minimal glue, document why]
```
Outcome: SmolVLA node → LeRobot `policy_server` + `robot_client`; mock servo driver → `feetech_ros2_driver` mock hardware; sphere tool → foam; reachability → REACH; SO-101 description/MoveIt → so101-ros-physical-ai. Promoted to [ADR-0006](adr/0006-integrate-dont-invent.md).

#### D3: VLM server
```mermaid
flowchart TD
  Q{Serve Qwen3-VL-4B next to SmolVLA on 6 GB} --> O[Ollama]
  Q --> V[vLLM]
  Q --> L[llama.cpp via llama-swap]
  O --> Ox[✗ less control over llama-server flags; project prefers llama.cpp]
  V --> Vx[✗ pre-allocates VRAM; weak CPU offload]
  L --> Lv[✓ per-layer GPU/CPU split; TTL + unload API; OpenAI-compatible tools]
```
Promoted to [ADR-0005](adr/0005-llamacpp-llamaswap-qwen3vl.md).

#### D4: VRAM sharing strategy
```mermaid
flowchart TD
  Q{VLM + VLA exceed VRAM} --> T[Time-share: unload VLM whenever VLA runs]
  Q --> R[Use 40 GB RAM: VLM layer offload profiles]
  Q --> C[Offload SmolVLA to CPU]
  C --> Cx[✗ 10 flow steps per chunk on 6 cores starves the 30 Hz queue]
  T --> Tx[partial: works but VLM unavailable during skills]
  R --> Rv[✓ gpu / hybrid / cpu profiles; VLM stays usable, slower, during skills]
```
- **Revisit if:** measured hybrid-profile VRAM (P5-T07) leaves < 300 MiB headroom.

#### D5: Source of the SO-101 simulation scene
```mermaid
flowchart TD
  Q{SO-101 MuJoCo model + tabletop scene} --> W[Hand-write MJCF]
  Q --> M[Menagerie model + own scene]
  Q --> N[Menagerie model + so101-nexus task scene export]
  W --> Wx[✗ reinventing; physics tuning risk]
  M --> Mx[partial: model is right, scene unmatched to any dataset]
  N --> Nv[✓ same scene as LeRobot EnvHub env and published datasets; enables lerobot-eval baseline]
```
Model lineage: TheRobotStudio SO-ARM100 (official) → Menagerie `robotstudio_so101` (tuned collisions and actuators) → so101-nexus scenes.

#### D6: Real-time teleop IK on a 5-DOF arm
```mermaid
flowchart TD
  Q{Cartesian WASD jog, robot-agnostic} --> S[MoveIt Servo]
  Q --> P[Placo via so101_kinematics]
  Q --> K[mink QP from MJCF]
  S --> Sx[✗ expects 6-D twists; singular halts on 5-DOF]
  P --> Px[✗ SO-101-specific in that repo; URDF/pinocchio path]
  K --> Kv[✓ task weighting, collision-avoidance limits, same MJCF as sim]
```
Promoted to [ADR-0003](adr/0003-mink-plus-moveit.md).

#### D7: VLM agent runtime (pending spike)
```mermaid
flowchart TD
  Q{Agent loop} --> R[RAI framework]
  Q --> RO[ROSA]
  Q --> T[Thin openai SDK loop]
  RO --> ROx[✗ introspection-oriented, not manipulation tools]
  R --> Rq[? adopt if OpenAI-compatible local endpoint + custom tools work on Jazzy]
  T --> Tq[fallback]
```
Decided by P4-T01 → ADR-0007.

### Open questions / follow-ups
- [ ] Exact `mujoco_ros2_control` camera plugin parameters and topic layout (P1-T01).
- [ ] Whether `lerobot_robot_ros` lets the command topic be configured so commands reach the safety filter (P5-T04).
- [ ] Whether rosbridge in Jazzy proxies ROS 2 actions for roslibjs (P3-T02).
- [ ] Which SmolVLA checkpoint best matches the exported scene's cameras (P5-T02/T05).
