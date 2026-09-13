# Third-Party Notices

CogniBot-ROS2-VLA is licensed under Apache-2.0. It integrates, downloads or derives from the third-party works below. Pins and usage details are in [docs/INTEGRATIONS.md](docs/INTEGRATIONS.md).

Only works that are **copied into or derived within this repository** (models, meshes, adapted code) need their license text reproduced next to the copy. Container images and packages installed at build time keep their own licenses.

| Work | Copyright / Maintainer | License | How used |
|---|---|---|---|
| MuJoCo Menagerie: `robotstudio_so101`, `franka_emika_panda` | Google DeepMind; The Robot Studio; Franka Robotics | Apache-2.0 | Downloaded at a pinned commit, modified (see `MODIFICATIONS.md` per model) |
| SO-ARM100 / SO-101 | The Robot Studio | Apache-2.0 | Reference URDF/MJCF for cross-checks |
| so101-nexus | John Sutor | Apache-2.0 | Task scenes exported to MJCF; LeRobot EnvHub environments for evaluation |
| so101-ros-physical-ai (`so101_description`, `so101_moveit_config`) | legalaspro | Apache-2.0 | Built from source at a pinned commit |
| feetech_ros2_driver | legalaspro | BSD-3-Clause | Built from source at a pinned commit |
| mujoco_ros2_control | ros-controls contributors | Apache-2.0 | apt binary |
| MoveIt 2, pick_ik | PickNik Robotics and contributors | BSD-3-Clause | Base image / apt binary |
| REACH, reach_ros2 | ROS-Industrial / Southwest Research Institute | Apache-2.0 | Built from source at a pinned commit |
| rosbridge_suite, web_video_server | RobotWebTools | BSD-3-Clause | apt binary |
| mink | Kevin Zakka | Apache-2.0 | pip package |
| foam | CoMMA Lab, Purdue | MIT | Offline tool (outputs committed) |
| LeRobot (incl. async inference, SmolVLA code) | Hugging Face | Apache-2.0 | Container image + pip package |
| lerobot-ros (`lerobot_robot_ros`) | Yifei Cheng | Apache-2.0 | Reference for the plugin pattern; not installed (see INTEGRATIONS §8) |
| RAI (if adopted) | Robotec.AI | Apache-2.0 | pip package from a pinned commit |
| llama.cpp | ggml-org | MIT | Container image (via llama-swap) |
| llama-swap | Benson Wong (mostlygeek) | MIT | Container image |
| Qwen3-VL-4B-Instruct (GGUF) | Alibaba Qwen team | Apache-2.0 | Model weights downloaded at runtime |
| SmolVLA base and community checkpoints | Hugging Face / checkpoint authors | Apache-2.0 (verify per checkpoint) | Model weights downloaded at runtime |
| CycloneDDS | Eclipse Foundation | EPL-2.0 / EDL-1.0 | apt binary |
| MuJoCo JavaScript bindings (`@mujoco/mujoco`) | Google DeepMind | Apache-2.0 | npm package bundled into the dashboard (free-look view) |
| three.js | three.js authors | MIT | npm package bundled into the dashboard |
| roslib (roslibjs) | RobotWebTools | BSD-2-Clause | npm package bundled into the dashboard |
| React, Vite | Meta Platforms; VoidZero and Vite contributors | MIT | npm packages (dashboard build and runtime) |
| Lucide icons (`lucide-react`) | Lucide contributors | ISC | npm package bundled into the dashboard |
| Barlow, Barlow Condensed (`@fontsource/*`) | Jeremy Tribby | OFL-1.1 | Fonts bundled into the dashboard |

If you add a component, add a row here and in `docs/INTEGRATIONS.md` in the same commit.
