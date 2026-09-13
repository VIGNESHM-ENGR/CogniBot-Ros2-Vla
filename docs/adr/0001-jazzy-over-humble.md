# ADR-0001: ROS 2 Jazzy instead of Humble

- **Status:** Accepted
- **Date:** 2026-09-13

## Context

The original brief targeted ROS 2 Humble on Ubuntu 22.04. The VLA side depends on LeRobot, and LeRobot 0.6.x declares `requires-python >= 3.12`. Humble on Jammy ships Python 3.10, and rclpy is compiled against the system interpreter. Humble reaches end-of-life in May 2027. The development host already runs Ubuntu 24.04.

## Decision

Use **ROS 2 Jazzy Jalisco on Ubuntu 24.04 (Noble, Python 3.12)** in every ROS container.

## Consequences

- LeRobot, rclpy and `lerobot_robot_ros` share one interpreter, so no cross-Python bridge is needed.
- Every required binary exists for Jazzy: `mujoco_ros2_control` 0.1.2, `pick_ik` 1.1.3, MoveIt 2, rosbridge, `web_video_server`.
- LTS support until May 2029.
- Noble enforces PEP 668, so pip packages go into a venv created with `--system-site-packages`, which keeps apt-installed ROS Python packages importable.
- pip-installed numpy 2.x can shadow the apt numpy that `cv_bridge` was built against. VLA/VLM code converts `sensor_msgs/Image` to numpy directly instead of using `cv_bridge`.

## Alternatives considered

- **Humble + separate Python 3.12 container talking over ZMQ/gRPC.** Adds a bespoke bridge and duplicates message definitions.
- **Humble + pinned 2025 LeRobot release that supports Python 3.10.** Stale APIs, and no async inference improvements.
