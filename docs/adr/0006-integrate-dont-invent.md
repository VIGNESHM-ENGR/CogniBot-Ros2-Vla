# ADR-0006: Integrate maintained components; write only glue

- **Status:** Accepted
- **Date:** 2026-09-13

## Context

The brief initially read as "write a SmolVLA inference node, a mock servo driver, IK tooling, …". Mature open-source implementations of most of these already exist. You asked explicitly to act as an integrator and not invent what isn't necessary.

## Decision

Before writing any component, search for a maintained upstream implementation. If one exists, is license-compatible and fits the constraints, **use it pinned** and write only the adapter. Current mapping (the full list is in [INTEGRATIONS.md](../INTEGRATIONS.md)):

| Capability | Upstream |
|---|---|
| Robot model | TheRobotStudio SO-ARM100 → MuJoCo Menagerie `robotstudio_so101` (downloaded, pinned) |
| Tabletop scene | so101-nexus `MuJoCoPickAndPlace-v1` (exported to MJCF) |
| Sim ↔ ros2_control | mujoco_ros2_control |
| SO-101 description, MoveIt config, servo driver | so101-ros-physical-ai, feetech_ros2_driver |
| IK / planning | MoveIt 2, pick_ik, mink |
| Collision spheres | foam |
| Reachability | REACH + reach_ros2 |
| VLM serving | llama.cpp + llama-swap |
| Agent runtime | RAI (pending P4-T01 compatibility spike) |
| Checkpoint sanity eval | `lerobot-eval` + so101-nexus EnvHub env |
| VLA serving and action streaming | LeRobot policy_server + robot_client + lerobot_robot_ros |
| Web bridge | rosbridge_suite, web_video_server |

## Consequences

- Much less code to maintain. The portfolio story becomes system integration, safety and architecture.
- Upstream churn risk, mitigated by pinning every component (SHA, digest, version) and bumping pins in dedicated commits.
- Every task in TASKS.md starts with a "check upstream first" step and records any new dependency in INTEGRATIONS.md.

## Alternatives considered

- **Build bespoke components.** More control, but it duplicates solved problems and adds maintenance and bug surface.
