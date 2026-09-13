# ADR-0003: Two-tier motion: mink for teleop, MoveIt 2 + pick_ik for planning

- **Status:** Accepted
- **Date:** 2026-09-13

## Context

We need (a) real-time Cartesian jogging from a keyboard and (b) collision-free planned motions for fetch/place, on both a 5-DOF SO-101 and a 7-DOF Panda. A 5-DOF arm can't follow arbitrary 6-D end-effector twists or poses.

## Decision

- **MoveIt 2** with **pick_ik** (position-only goals plus a soft orientation cost) and OMPL for planned motions. It runs as `move_group`, and our `pick_place_server` drives it through MoveItPy.
- **mink** (differential IK as a QP, built from the MJCF) for 100 Hz teleop. It uses `FrameTask` with a small orientation weight, `ConfigurationLimit`, `VelocityLimit`, and `CollisionAvoidanceLimit` over the foam collision-sphere geoms.
- Both are robot-agnostic: MoveIt through each robot's MoveIt config, mink through each robot's MJCF IK model.

## Consequences

- Teleop degrades gracefully on 5-DOF: the QP trades orientation error for position tracking, with no singular pseudo-inverse blow-ups.
- Two kinematic models (URDF for MoveIt, MJCF for mink) must agree. P1-T03 adds a consistency test (joint names, limits, forward kinematics at random configurations within 5 mm).

## Alternatives considered

- **MoveIt Servo for teleop.** Designed for 6-D twists; on 5-DOF it needs custom masking and still hits singularity halts.
- **Placo (used by so101_kinematics).** Capable, but URDF/pinocchio-based and SO-101-specific in that repo. mink reuses the MJCF we already maintain.
- **cuRobo.** GPU memory cost competes with the models on 6 GB.
