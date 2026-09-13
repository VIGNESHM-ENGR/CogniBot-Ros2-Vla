# Host Setup

These steps prepare an Ubuntu 24.04 host (the reference machine is an RTX 3060 Laptop with 6 GB VRAM and 40 GB RAM) to run CogniBot. Everything else runs in containers.

## 1. Prerequisites

| Component | Minimum | Check |
|---|---|---|
| NVIDIA driver | 570+ (reference: 595) | `nvidia-smi` |
| Docker Engine | 27+ (reference: 29) | `docker --version` |
| Docker Compose plugin | v2.24+ (reference: v5) | `docker compose version` |
| NVIDIA Container Toolkit | 1.17+ | `nvidia-ctk --version` |
| Free disk | ~40 GB (images ~20 GB, models ~6 GB, HF cache) | `df -h` |
| git, make, (optional) vcstool | – | – |

## 2. NVIDIA Container Toolkit

```bash
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey \
  | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list \
  | sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' \
  | sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list
sudo apt-get update && sudo apt-get install -y nvidia-container-toolkit
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker

# verify: GPU visible, including the graphics capability needed for EGL
docker run --rm --gpus all -e NVIDIA_DRIVER_CAPABILITIES=all ubuntu:24.04 nvidia-smi
```

## 3. Headless EGL on a hybrid-graphics laptop

MuJoCo renders camera images offscreen through EGL on the NVIDIA GPU. Inside the container this needs:

- `NVIDIA_DRIVER_CAPABILITIES` to include `graphics` (the compose `x-gpu` anchor sets `compute,utility,graphics`)
- the GLVND vendor file `/usr/share/glvnd/egl_vendor.d/10_nvidia.json` (created in the `core` image)
- `MUJOCO_GL=egl`, and `MUJOCO_EGL_DEVICE_ID=0` if several EGL devices exist

Smoke test (after `make build`):

```bash
make shell-sim
python3 - <<'EOF'
import mujoco
m = mujoco.MjModel.from_xml_string('<mujoco><worldbody><light pos="0 0 1"/><geom type="sphere" size=".1"/></worldbody></mujoco>')
d = mujoco.MjData(m)
with mujoco.Renderer(m, 240, 320) as r:
    mujoco.mj_forward(m, d); r.update_scene(d); img = r.render()
print("EGL render OK", img.shape, img.mean())
EOF
```

## 4. Kernel network buffers (for camera topics over DDS)

```bash
sudo tee /etc/sysctl.d/60-cognibot-dds.conf >/dev/null <<'EOF'
net.core.rmem_max=2147483647
net.core.wmem_max=2147483647
net.ipv4.ipfrag_high_thresh=134217728
net.ipv4.ipfrag_time=3
EOF
sudo sysctl --system
```

The reasoning is in [NETWORKING.md §2.2](NETWORKING.md#22-host-sysctl-documented-in-setupmd).

## 5. Clone and configure

```bash
git clone <your-remote>/CogniBot-Ros2-Vla.git && cd CogniBot-Ros2-Vla
git config core.hooksPath .githooks          # enables commit-message checks
cp cognibot_ws/docker/.env.example cognibot_ws/docker/.env
# edit .env: HOST_UID/HOST_GID (id -u / id -g), ROBOT, ROS_DOMAIN_ID, optional HF_TOKEN
```

## 6. Build and run

```bash
make build            # core, vlm and vla images (the first build takes a while)
make sim              # core profile: sim + motion + bridge + dashboard → http://localhost:8000
make vlm              # core + llm + vlm-agent
make vla              # core + policy-server + vla-client
make full             # everything
make twin             # core + twin connector (mock hardware by default)
make down             # stop everything
```

## 7. Optional: GUI for development

The MuJoCo Simulate viewer and RViz use X11 forwarding through `compose.dev.yaml`:

```bash
xhost +si:localuser:$(whoami)
make sim-dev          # adds DISPLAY, /tmp/.X11-unix, and disables headless mode
```

## 8. Serial device for the digital twin (future)

```bash
# Feetech/Waveshare USB bus adapters usually show up as /dev/ttyACM* or /dev/ttyUSB*
sudo usermod -aG dialout $USER     # log out and back in
ls -l /dev/serial/by-id/
```

Set `TWIN_SERIAL_DEVICE` in `.env` and uncomment the `devices:` entry of the `twin` service.

## 9. Troubleshooting

| Problem | Fix |
|---|---|
| `could not select device driver "nvidia"` | Toolkit not configured: rerun `nvidia-ctk runtime configure` and restart Docker |
| `mujoco.FatalError: gladLoadGL error` / EGL init fails | Missing `graphics` capability or vendor JSON; check `ls /usr/share/glvnd/egl_vendor.d/` in the container |
| Camera topics are silent, but joint states flow | Apply the §4 sysctls; see [NETWORKING.md §9](NETWORKING.md#9-troubleshooting) |
| Files created in bind mounts are owned by root | Set `HOST_UID`/`HOST_GID` in `.env` and rebuild |
| Out of VRAM | See [VRAM_BUDGET.md](VRAM_BUDGET.md); use the `qwen3-vl-4b-hybrid` or `-cpu` profile |
