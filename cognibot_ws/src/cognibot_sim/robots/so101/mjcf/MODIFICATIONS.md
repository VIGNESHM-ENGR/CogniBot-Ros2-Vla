# MuJoCo Menagerie SO-101 Model Modifications

- **Upstream source:** [google-deepmind/mujoco_menagerie](https://github.com/google-deepmind/mujoco_menagerie)
- **Subdirectory:** `robotstudio_so101`
- **Pinned commit:** `8161bba264d7fa7c99ca301e91e7fb44737676ad`
- **License:** Apache-2.0 (see `LICENSE`)

## Modifications
- Aligned `wrist_roll` joint `range` to `[-2.74385, 2.84121]` (previously `[-2.7438473, 2.7438473]`) to match its actuator `ctrlrange` and the physical servo limits from `so101_description`.
- Aligned `gripperframe` site `pos` to `[-0.0079, -0.000218, -0.098127]` (previously `[0.012, -0.000218, -0.098127]`) to match the URDF `gripper_frame_link` position at the grasp center.
