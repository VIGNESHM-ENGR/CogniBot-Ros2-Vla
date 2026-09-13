# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

- **Operator (primary):** the project owner, alone at a laptop (1280–1920 px, RTX 3060 Laptop), running the stack locally and driving and debugging a simulated (later real) SO-101 or Panda arm.
- **Watchers (secondary):** people seeing the console in screen recordings, demos and the GitHub README (recruiters, robotics engineers, open-source visitors). The console must read clearly on video without narration.

## Product Purpose

CogniBot-ROS2-VLA is a containerized ROS 2 Jazzy manipulation stack for a consumer laptop: a local vision-language model grounds a request in the camera image and calls robot tools (MoveIt 2 planning, LeRobot SmolVLA policies) on a MuJoCo-simulated arm with sphere-based safety. The operator console is how the stack is operated: a session should need no terminal to watch, drive, demo and instruct the robot.

Success: the operator can see what the robot sees and is doing, command it, stop it instantly, and a watcher understands what happened from the recording alone.

## Positioning

An end-to-end language → vision → action stack integrated from maintained upstream components (MuJoCo Menagerie, mujoco_ros2_control, MoveIt 2 + pick_ik, mink, LeRobot, llama.cpp) and running on 6 GB of VRAM, with explicit control-mode arbitration (exactly one commander at a time) and a safety filter between learned policies and the arm.

## Operating Context

- Localhost only: the browser talks to rosbridge (`127.0.0.1:9090`) and MJPEG streams (`127.0.0.1:8080`); served on `:8000`. No authentication by design.
- Runs beside the MuJoCo viewer and RViz on the same screen during development; alone during demos.
- Control modes: IDLE, TELEOP, MOTION, VLA, TWIN. Only one commander drives the arm at a time.
- Phases arrive incrementally: sim + cameras + MoveIt exist now; teleop/safety (P2), VLM agent (P4), VLA (P5) and digital twin (P6) come later. Panels for unfinished phases must show an honest "not running" state, never fake data.

## Capabilities and Constraints

Jobs the console must support without a terminal:

1. **Watch:** live front (RGB-D) and wrist cameras, joint positions, controller and mode status, GPU utilization and VRAM.
2. **Drive:** keyboard teleop (`W/S` ±X, `A/D` ±Y, `↑/↓` ±Z, `G` gripper, 300 ms dead-man), named poses, move-to-point through MoveIt, gripper open/close.
3. **Demo:** start, watch and cancel pick-and-place (scripted now, planned `FetchObject`/`PlaceObject` later).
4. **Instruct:** natural-language tasks to the VLM agent with a visible tool-call trace; start/cancel VLA skills with rate, queue and latency (P4–P5).

Constraints:
- Stack (fixed by the repository plan): Vite + React + TypeScript (strict), roslibjs over rosbridge, ESLint + Prettier, served by nginx.
- ROS 2 actions work through rosbridge (verified P3-T02): goals, feedback, cancel.
- Robot specifics come from the robot registry; the console must work for both `so101` and `panda`.
- Camera topics in simulation are `/mujoco_camera_plugin/{front_rgbd,wrist_cam}/{color,depth,camera_info}`.

## Brand Commitments

- Name: **CogniBot** (repository `CogniBot-ROS2-VLA`). No logo exists.
- Simulation look chosen by the owner: red robot arm, green cube, blue target disc.

## Evidence on Hand

- Scene preview: `cognibot_ws/src/cognibot_sim/scenes/preview.png`; live camera streams from `make sim`.
- Measured numbers in `docs/DEVLOG.md` (IK error 0.31 mm, GPU/VRAM per configuration, rosbridge action latency).
- No users, testimonials or benchmark report exist; do not fabricate them.

## Product Principles

1. **Stop is always one keystroke away.** A persistent emergency stop is visible in every state and reachable from the keyboard.
2. **Truth over polish.** Every number and state shown comes from a live topic; missing services show as missing.
3. **One commander, visibly.** The active control mode and who holds the arm are always obvious.
4. **Readable on a recording.** State changes are legible to someone watching a video, not only to the operator.
5. **Keyboard-first.** Everything, not only teleop, works without the mouse.

## Accessibility & Inclusion

- Keyboard-first operation with visible focus for every control.
- Emergency stop: large, persistent, keyboard-reachable.
