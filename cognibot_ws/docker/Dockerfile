# syntax=docker/dockerfile:1.7
# CogniBot-ROS2-VLA multi-stage images. Build context: repository root.
#   interfaces → shared underlay (cognibot_interfaces + cognibot_common)
#   core       → sim / motion / bridge / twin   (FROM official MoveIt 2 image)
#   tools      → offline asset tooling (scene export; foam added in P2-T03)
#   vlm        → VLM agent node (CPU; talks to llama-swap)
#   vla        → LeRobot robot_client + ROS plugins (CPU; talks to policy_server)
# Pins: docs/INTEGRATIONS.md. Digests are resolved in P1-T01.

ARG ROS_BASE_IMAGE=ros:jazzy-ros-base-noble
ARG MOVEIT_IMAGE=moveit/moveit2:jazzy-release

# ───────────────────────────── interfaces ─────────────────────────────
FROM ${ROS_BASE_IMAGE} AS interfaces
SHELL ["/bin/bash", "-o", "pipefail", "-c"]
WORKDIR /tmp/underlay
COPY cognibot_ws/src/cognibot_interfaces src/cognibot_interfaces
COPY cognibot_ws/src/cognibot_common src/cognibot_common
RUN source /opt/ros/jazzy/setup.bash \
 && colcon build --merge-install --install-base /opt/cognibot/underlay \
      --cmake-args -DCMAKE_BUILD_TYPE=Release \
 && rm -rf /tmp/underlay

# ───────────────────────────── core ───────────────────────────────────
FROM ${MOVEIT_IMAGE} AS core
SHELL ["/bin/bash", "-o", "pipefail", "-c"]
ARG HOST_UID=1000
ARG HOST_GID=1000
# Placeholder: must equal the MuJoCo version bundled by mujoco_vendor (resolved in P1-T01).
ARG MUJOCO_PY_VERSION=3.3.7
ARG MINK_VERSION=1.3.0
ARG QPSOLVERS_VERSION=4.13.0
ARG NVML_VERSION=13.610.43
ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
      ros-jazzy-mujoco-ros2-control \
      ros-jazzy-mujoco-ros2-control-plugins \
      ros-jazzy-ros2-control \
      ros-jazzy-ros2-controllers \
      ros-jazzy-pick-ik \
      ros-jazzy-moveit-py \
      ros-jazzy-moveit-resources-panda-moveit-config \
      ros-jazzy-rosbridge-server \
      ros-jazzy-web-video-server \
      ros-jazzy-rmw-cyclonedds-cpp \
      ros-jazzy-xacro \
      ros-jazzy-robot-state-publisher \
      python3-venv python3-vcstool python3-colcon-common-extensions \
      libegl1 libgles2 libglvnd0 libgl1 curl \
 && rm -rf /var/lib/apt/lists/*

# Headless MuJoCo rendering through the NVIDIA EGL driver (graphics capability required).
RUN mkdir -p /usr/share/glvnd/egl_vendor.d \
 && printf '{"file_format_version":"1.0.0","ICD":{"library_path":"libEGL_nvidia.so.0"}}\n' \
      > /usr/share/glvnd/egl_vendor.d/10_nvidia.json
ENV MUJOCO_GL=egl \
    PYOPENGL_PLATFORM=egl \
    NVIDIA_DRIVER_CAPABILITIES=compute,utility,graphics

# PEP 668 on Noble: pip packages live in a venv that can still import apt ROS packages.
RUN python3 -m venv --system-site-packages /opt/venv \
 && /opt/venv/bin/pip install --no-cache-dir \
      "mujoco==${MUJOCO_PY_VERSION}" \
      "mink==${MINK_VERSION}" \
      "qpsolvers[daqp]==${QPSOLVERS_VERSION}" \
      "nvidia-ml-py==${NVML_VERSION}"

COPY --from=interfaces /opt/cognibot/underlay /opt/cognibot/underlay
COPY cognibot_ws/docker/entrypoint.sh /entrypoint.sh
COPY cognibot_ws/docker/cyclonedds.xml /etc/cognibot/cyclonedds.xml

# Non-root user matching the host UID/GID (the base image ships 'ubuntu' as 1000).
RUN (id -u ubuntu >/dev/null 2>&1 && userdel -r ubuntu || true) \
 && groupadd -o -g "${HOST_GID}" cognibot \
 && useradd -m -o -u "${HOST_UID}" -g "${HOST_GID}" -s /bin/bash cognibot \
 && mkdir -p /ws && chown cognibot:cognibot /ws

# Workspace packages (overlay). Third-party sources are added by the phase that needs them.
COPY --chown=cognibot:cognibot cognibot_ws/src /ws/src
RUN source /opt/ros/jazzy/setup.bash && source /opt/cognibot/underlay/setup.bash \
 && cd /ws && colcon build --symlink-install \
      --packages-skip cognibot_interfaces cognibot_common \
 && chown -R cognibot:cognibot /ws

USER cognibot
WORKDIR /ws
ENTRYPOINT ["/entrypoint.sh"]
CMD ["bash"]

# ───────────────────────────── tools ──────────────────────────────────
FROM core AS tools
ARG SO101_NEXUS_VERSION=0.6.0
USER root
RUN /opt/venv/bin/pip install --no-cache-dir "so101-nexus==${SO101_NEXUS_VERSION}"
USER cognibot

# ───────────────────────────── vlm ────────────────────────────────────
FROM ${ROS_BASE_IMAGE} AS vlm
SHELL ["/bin/bash", "-o", "pipefail", "-c"]
ARG HOST_UID=1000
ARG HOST_GID=1000
ARG OPENAI_VERSION=3.13.0
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
      ros-jazzy-rmw-cyclonedds-cpp ros-jazzy-tf2-ros python3-venv curl \
 && rm -rf /var/lib/apt/lists/* \
 && python3 -m venv --system-site-packages /opt/venv \
 && /opt/venv/bin/pip install --no-cache-dir "openai==${OPENAI_VERSION}"
COPY --from=interfaces /opt/cognibot/underlay /opt/cognibot/underlay
COPY cognibot_ws/docker/entrypoint.sh /entrypoint.sh
COPY cognibot_ws/docker/cyclonedds.xml /etc/cognibot/cyclonedds.xml
RUN (id -u ubuntu >/dev/null 2>&1 && userdel -r ubuntu || true) \
 && groupadd -o -g "${HOST_GID}" cognibot \
 && useradd -m -o -u "${HOST_UID}" -g "${HOST_GID}" -s /bin/bash cognibot \
 && mkdir -p /ws && chown cognibot:cognibot /ws
COPY --chown=cognibot:cognibot cognibot_ws/src/cognibot_vlm /ws/src/cognibot_vlm
RUN source /opt/ros/jazzy/setup.bash && source /opt/cognibot/underlay/setup.bash \
 && cd /ws && colcon build --symlink-install && chown -R cognibot:cognibot /ws
USER cognibot
WORKDIR /ws
ENTRYPOINT ["/entrypoint.sh"]
CMD ["bash"]

# ───────────────────────────── vla ────────────────────────────────────
FROM ${ROS_BASE_IMAGE} AS vla
SHELL ["/bin/bash", "-o", "pipefail", "-c"]
ARG HOST_UID=1000
ARG HOST_GID=1000
# Client and policy-server MUST run the same LeRobot version (P5-T01 aligns it with the server image).
ARG LEROBOT_VERSION=0.6.1
ARG TORCH_INDEX=https://download.pytorch.org/whl/cpu
ARG LEROBOT_ROS_COMMIT=dabe6c6c7637c2f139e1c9964864a64921893ba1
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
      ros-jazzy-rmw-cyclonedds-cpp python3-venv git curl \
 && rm -rf /var/lib/apt/lists/* \
 && python3 -m venv --system-site-packages /opt/venv \
 && /opt/venv/bin/pip install --no-cache-dir torch torchvision --index-url "${TORCH_INDEX}" \
 && /opt/venv/bin/pip install --no-cache-dir \
      "lerobot[smolvla]==${LEROBOT_VERSION}" \
      "lerobot-robot-ros @ git+https://github.com/ycheng517/lerobot-ros@${LEROBOT_ROS_COMMIT}#subdirectory=lerobot_robot_ros"
COPY --from=interfaces /opt/cognibot/underlay /opt/cognibot/underlay
COPY cognibot_ws/docker/entrypoint.sh /entrypoint.sh
COPY cognibot_ws/docker/cyclonedds.xml /etc/cognibot/cyclonedds.xml
RUN (id -u ubuntu >/dev/null 2>&1 && userdel -r ubuntu || true) \
 && groupadd -o -g "${HOST_GID}" cognibot \
 && useradd -m -o -u "${HOST_UID}" -g "${HOST_GID}" -s /bin/bash cognibot \
 && mkdir -p /ws && chown cognibot:cognibot /ws
COPY --chown=cognibot:cognibot cognibot_ws/src/cognibot_vla /ws/src/cognibot_vla
RUN source /opt/ros/jazzy/setup.bash && source /opt/cognibot/underlay/setup.bash \
 && cd /ws && colcon build --symlink-install && chown -R cognibot:cognibot /ws
USER cognibot
WORKDIR /ws
ENTRYPOINT ["/entrypoint.sh"]
CMD ["bash"]
