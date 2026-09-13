# Changelog

All notable changes to this project are documented here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses [Semantic Versioning](https://semver.org/).

The engineering narrative (problems, root causes, decision trees) lives in [docs/DEVLOG.md](docs/DEVLOG.md). This file lists user-visible changes only.

## [Unreleased]

### Added
- ROS 2 Jazzy workspace skeleton: `cognibot_interfaces`, `cognibot_common`, `cognibot_sim`, `cognibot_motion`, `cognibot_teleop`, `cognibot_vlm`, `cognibot_vla`, `cognibot_twin`, `cognibot_bringup`.
- `cognibot_interfaces`: 5 messages, 3 services and 5 actions generated from `docs/ROS_INTERFACES.md`.
- `cognibot_ws/third_party.repos` pinning so101-ros-physical-ai, feetech_ros2_driver, REACH and reach_ros2.
- Project documentation: scope, plan, architecture, networking, ROS interfaces, VRAM budget, integrations, setup, ADR-0001…0006, third-party notices.
- Repository foundation: Apache-2.0 license, ignore/attribute/editor configs, `commit-msg` hook enforcing Conventional Commits and single authorship.
