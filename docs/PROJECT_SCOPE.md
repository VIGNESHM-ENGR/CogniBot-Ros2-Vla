# Project Scope: CogniBot-ROS2-VLA

> A containerized ROS 2 Jazzy manipulation stack that runs on a consumer laptop. Language goes in: a local vision-language model grounds the request in the camera image and calls robot tools. A LeRobot vision-language-action policy (SmolVLA) and a MoveIt 2 motion stack execute the result on a MuJoCo-simulated LeRobot SO-101 arm (or a Franka Panda). A web dashboard handles operation.

- **Status:** Phase 0 (foundation)
- **Owner:** Vignesh
- **License:** Apache-2.0

---

## 1. Problem statement

Recent VLAs such as SmolVLA and π0 and small VLMs such as Qwen3-VL and SmolVLM are now small enough to run on a single consumer GPU. Integrating them into a real robot software stack is still hard:

- Python version conflicts (ROS 2 Humble has Python 3.10; LeRobot needs Python 3.12 or newer).
- GPU memory contention between the simulator, the VLM and the VLA.
- Arbitration between several "commanders" (teleop, planner, learned policy) that all want the same arm.
- Safety: learned policies emit raw joint targets with no notion of collisions.
- Cross-container ROS 2 networking.

CogniBot shows a clean, reproducible integration of mature open-source components that solves these problems on a 6 GB RTX 3060 laptop.

## 2. Guiding principle: integrate, don't invent

CogniBot is an **integration project**. We use the best maintained community images and packages, pinned by tag, commit or digest, and write code only for the glue between them:

- robot/scene configuration
- control-mode arbitration and safety filtering
- the VLM tool layer
- the dashboard

Every third-party component is listed with its pin in [INTEGRATIONS.md](INTEGRATIONS.md).

## 3. Goals (in scope)

| # | Goal | Phase |
|---|---|---|
| G1 | Headless MuJoCo simulation of SO-101 (default) and Franka Panda through `mujoco_ros2_control`, with RGB-D cameras published as ROS topics (EGL offscreen) | P1 |
| G2 | Robot-agnostic configuration: one `robot:=<name>` argument selects MJCF, URDF, controllers, MoveIt config, IK and safety data | P1 |
| G3 | IK and motion planning: MoveIt 2 + pick_ik (planned fetch/place) and mink (real-time Cartesian teleop), both collision-aware | P2 |
| G4 | Collision-sphere robot model (generated with foam) used by the IK and a streaming **safety filter** | P2 |
| G5 | Reachability study (ros-industrial REACH) plus a fitted **workspace sphere** used to reject unreachable targets | P2 |
| G6 | Control-mode arbitration (IDLE / TELEOP / MOTION / VLA / TWIN) through controller switching; exactly one commander at a time | P2 |
| G7 | Web control dashboard: camera, joint states, WASD / ↑↓ / G teleop pad, mode switch, safety overlays, VRAM gauge | P3 |
| G8 | Local VLM agent: Qwen3-VL-4B (llama.cpp via llama-swap) with tool calling. Grounds "the red cube" to a 3D point via bbox + depth + TF, then calls motion or VLA tools | P4 |
| G9 | VLA inference: stock LeRobot async `policy_server` (GPU) + `robot_client` with the `lerobot_robot_ros` plugin, streaming ~30 Hz joint targets through the safety filter | P5 |
| G10 | VRAM coordination so the VLM and VLA coexist on 6 GB, using 40 GB system RAM as an offload tier (llama.cpp gpu/hybrid/cpu profiles via llama-swap, unload before VLA streaming); a measured budget is published | P5 |
| G11 | Digital-twin mode: a real SO-101 (Feetech STS3215 bus via `feetech_ros2_driver`) mirrored into MuJoCo. Mock hardware now, real arm when available | P6 |
| G12 | Compose profiles: core (sim only), `vlm`, `vla`, `twin`, `full` | P0 |
| G13 | Portfolio-quality docs, CI, reproducible builds and benchmark numbers | P0–P7 |

## 4. Non-goals (out of scope)

- **Training or fine-tuning** any model (SmolVLA, VLM). Training happens separately on cloud GPUs. This project consumes checkpoints only (`lerobot/smolvla_base` or community fine-tuned SO-101 checkpoints).
- Dataset recording pipelines. They already exist upstream (`so101-ros-physical-ai/episode_recorder`, `lerobot-record`); we may link to them but won't build them.
- Real-robot policy deployment and sim-to-real transfer tuning. The twin connector mirrors a real arm into sim; commanding the real arm from a VLA is a future extension.
- Mobile manipulation, multi-arm setups, dexterous hands.
- Cloud or multi-machine deployment (documented as an option in NETWORKING.md, but not supported).
- Gazebo, Isaac Sim or other simulators.
- Authentication or multi-user access control for the dashboard (localhost-only by design).
- Custom CUDA kernels, model quantization pipelines, or writing our own IK solver, planner, inference server or policy runtime.

## 5. Success criteria

| Area | Criterion | How measured |
|---|---|---|
| Build | `make build` produces all images from clean state; `docker compose config` valid for every profile | CI + local |
| Sim | `ros2 control list_controllers` shows active controllers; `/joint_states` ≥ 100 Hz; front RGB-D ≥ 15 Hz headless | `ros2 topic hz` |
| IK / teleop | WASD/↑↓ jog tracks the EE at ≥ 50 Hz with no self or table collision in a scripted 60 s jog stress test | launch_testing |
| Safety | A scripted colliding joint command is clamped or rejected 100% of the time | pytest + launch_testing |
| Reach | `check_reachability` agrees with an actual MoveIt IK attempt on ≥ 95% of 200 random desk targets | eval script |
| Motion | `fetch_object` / `place_object` succeed on ground-truth cube poses in ≥ 90% of 20 trials (SO-101) | eval script |
| VLM | Grounding error ≤ 3 cm (median) against MuJoCo ground truth on the default scene; end-to-end "pick the red cube and place it near the blue cup" succeeds using MoveIt tools | eval script |
| VLA | Stable action stream at 30 Hz ± 10%, observation → action-chunk latency reported, zero safety-filter bypasses. **Task success is not a criterion**: zero-shot `smolvla_base` isn't expected to solve our sim scene | `/cognibot/vla/status` log |
| VRAM | Full profile runs within 6 GB without OOM for a 10-minute scripted session; peak usage documented | `nvidia-smi` log + `/cognibot/gpu` |
| Twin | With mock hardware, the sim mirrors the published joint states with < 50 ms lag | launch_testing |
| Quality | CI green; ruff clean; every package has tests for pure logic; docs match the code | CI |

## 6. Constraints

- **Hardware:** NVIDIA RTX 3060 Laptop GPU, 6 GB VRAM (6144 MiB), driver 595.x; Intel i5-11400H (6C/12T); 40 GB system RAM (used as the VLM offload tier).
- **Host OS:** Ubuntu 24.04 LTS (the original spec said 22.04; everything runs in containers, so the host version only matters for driver and nvidia-container-toolkit).
- **Containers:** Docker Engine 29 and Compose v5, with `nvidia-container-toolkit` for GPU and EGL.
- **ROS:** ROS 2 **Jazzy** (see [ADR-0001](adr/0001-jazzy-over-humble.md)).
- **Python:** 3.12 everywhere (Noble system Python).
- **Network:** single host; ROS discovery restricted to localhost.

## 7. Key risks and mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| VLM + VLA don't fit in 6 GB together | OOM, crashes | llama.cpp partial offload into 40 GB RAM (gpu/hybrid/cpu profiles via llama-swap); unload before VLA streaming; SmolVLA bf16 stays on GPU; measured budget ([VRAM_BUDGET.md](VRAM_BUDGET.md)) |
| `mujoco_ros2_control` camera plugin or EGL misbehaves in Docker on a hybrid-graphics laptop | No images | NVIDIA EGL vendor JSON, `graphics` capability, `MUJOCO_EGL_DEVICE_ID`; an early spike task (P1-T01) |
| Zero-shot SmolVLA produces poor actions in sim | Weak demo | Scope defines VLA success as pipeline correctness; checkpoint is configurable; the safety filter prevents damage |
| Upstream packages change (LeRobot moves fast) | Broken builds | Pin every dependency (commit SHA, image digest, pip version); Renovate-style manual bumps in dedicated commits |
| LeRobot client/server gRPC version mismatch | Async inference fails | Client and server both pinned to the same `lerobot` version (recorded in INTEGRATIONS.md) |
| 5-DOF SO-101 can't reach arbitrary orientations | IK failures | pick_ik position-only goals with soft orientation cost; top-down grasps only; reachability pre-check |
| Joint names and meshes differ between Menagerie MJCF and so101_description URDF | Controller or MoveIt mismatch | Alignment table plus a validation test (P1-T03) that compares joint names and limits |
| Cross-container DDS discovery flakiness | Nodes don't see each other | Host network + IPC, CycloneDDS loopback config, a single `ROS_DOMAIN_ID`, health checks |

## 8. Deliverables

1. Source repository with a colcon workspace, Docker images and Compose profiles.
2. Documentation: this scope, [PROJECT_PLAN.md](PROJECT_PLAN.md), [ARCHITECTURE.md](ARCHITECTURE.md), [NETWORKING.md](NETWORKING.md), [ROS_INTERFACES.md](ROS_INTERFACES.md), [VRAM_BUDGET.md](VRAM_BUDGET.md), [INTEGRATIONS.md](INTEGRATIONS.md), [SETUP.md](SETUP.md), ADRs.
3. [DEVLOG.md](DEVLOG.md): engineering log of work done, problems with root causes and solutions, and decision trees.
4. Web dashboard with its design system (`dashboard/DESIGN.md`).
5. Evaluation scripts and a benchmark report (latency, VRAM, grounding error, reach accuracy).
6. Demo recordings (GIF/MP4) for the README.
