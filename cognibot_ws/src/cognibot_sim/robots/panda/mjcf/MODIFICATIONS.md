# MuJoCo Menagerie Franka Emika Panda Model Modifications

- **Upstream source:** [google-deepmind/mujoco_menagerie](https://github.com/google-deepmind/mujoco_menagerie)
- **Subdirectory:** `franka_emika_panda`
- **Pinned commit:** `8161bba264d7fa7c99ca301e91e7fb44737676ad`
- **License:** Apache-2.0 (see `LICENSE`)

## Modifications
- Renamed joints `joint1`…`joint7` to `panda_joint1`…`panda_joint7` and `finger_joint1`…`finger_joint2` to `panda_finger_joint1`…`panda_finger_joint2` in `panda.xml` to align with standard ROS panda descriptions (`moveit_resources_panda_description`).
