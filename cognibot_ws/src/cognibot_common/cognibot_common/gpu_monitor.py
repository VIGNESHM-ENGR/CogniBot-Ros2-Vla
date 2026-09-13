"""GPU status monitor node for CogniBot.

Publishes GPU memory, temperature, and utilization to /cognibot/gpu via NVML.
Gracefully falls back to mock/synthetic telemetry when NVML or GPU is unavailable.
"""

import contextlib
from typing import Any

import rclpy
from cognibot_interfaces.msg import GpuStatus
from rclpy.node import Node

try:
    import pynvml

    HAS_PYNVML = True
except ImportError:
    try:
        import nvidia_smi as pynvml  # type: ignore[no-redef]

        HAS_PYNVML = True
    except ImportError:
        pynvml = None
        HAS_PYNVML = False


class GpuMonitorNode(Node):
    """ROS 2 Node monitoring GPU telemetry."""

    def __init__(self) -> None:
        super().__init__("gpu_monitor")

        self.declare_parameter("publish_rate_hz", 1.0)
        self.declare_parameter("device_index", 0)
        self.declare_parameter("fallback_memory_total_mib", 6144)

        self._publish_rate = float(self.get_parameter("publish_rate_hz").value)
        self._device_index = int(self.get_parameter("device_index").value)
        self._fallback_total_mib = int(self.get_parameter("fallback_memory_total_mib").value)

        self._publisher = self.create_publisher(GpuStatus, "/cognibot/gpu", 10)

        self._nvml_initialized = False
        self._device_handle: Any = None

        self._init_nvml()

        timer_period = 1.0 / self._publish_rate if self._publish_rate > 0 else 1.0
        self._timer = self.create_timer(timer_period, self._publish_status)
        self.get_logger().info(
            f"GPU monitor node started (rate: {self._publish_rate} Hz, "
            f"device: {self._device_index}, NVML: {self._nvml_initialized})"
        )

    def _init_nvml(self) -> None:
        """Initialize NVML library and acquire device handle."""
        if not HAS_PYNVML or pynvml is None:
            self.get_logger().warn("pynvml library not found. Falling back to synthetic telemetry.")
            return

        try:
            pynvml.nvmlInit()
            device_count = pynvml.nvmlDeviceGetCount()
            if self._device_index >= device_count:
                self.get_logger().warn(
                    f"Requested device index {self._device_index} but only {device_count} "
                    "GPUs detected. Using fallback."
                )
                return
            self._device_handle = pynvml.nvmlDeviceGetHandleByIndex(self._device_index)
            self._nvml_initialized = True
            name = pynvml.nvmlDeviceGetName(self._device_handle)
            if isinstance(name, bytes):
                name = name.decode("utf-8")
            self.get_logger().info(f"Initialized NVML for GPU {self._device_index}: {name}")
        except Exception as e:
            self.get_logger().warn(
                f"Failed to initialize NVML ({e}). Falling back to synthetic telemetry."
            )
            self._nvml_initialized = False

    def _publish_status(self) -> None:
        """Read and publish GPU status."""
        msg = GpuStatus()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = "gpu"

        if self._nvml_initialized and self._device_handle is not None and pynvml is not None:
            try:
                name = pynvml.nvmlDeviceGetName(self._device_handle)
                if isinstance(name, bytes):
                    name = name.decode("utf-8")
                msg.name = str(name)

                mem_info = pynvml.nvmlDeviceGetMemoryInfo(self._device_handle)
                msg.memory_total_mib = int(mem_info.total // (1024 * 1024))
                msg.memory_used_mib = int(mem_info.used // (1024 * 1024))

                util = pynvml.nvmlDeviceGetUtilizationRates(self._device_handle)
                msg.utilization_pct = float(util.gpu)

                try:
                    temp = pynvml.nvmlDeviceGetTemperature(
                        self._device_handle, pynvml.NVML_TEMPERATURE_GPU
                    )
                    msg.temperature_c = float(temp)
                except Exception:
                    msg.temperature_c = 0.0

                process_names = []
                process_memories = []
                try:
                    procs = pynvml.nvmlDeviceGetComputeRunningProcesses(self._device_handle)
                    for p in procs:
                        try:
                            p_name = pynvml.nvmlSystemGetProcessName(p.pid)
                            if isinstance(p_name, bytes):
                                p_name = p_name.decode("utf-8")
                        except Exception:
                            p_name = f"PID:{p.pid}"
                        process_names.append(str(p_name))
                        process_memories.append(int(p.usedGpuMemory // (1024 * 1024)))
                except Exception:
                    pass

                msg.process_names = process_names
                msg.process_memory_mib = process_memories
            except Exception as e:
                self.get_logger().warn(f"Error querying NVML ({e}). Using fallback values.")
                self._populate_fallback(msg)
        else:
            self._populate_fallback(msg)

        self._publisher.publish(msg)

    def _populate_fallback(self, msg: GpuStatus) -> None:
        """Fill message with synthetic/fallback data."""
        msg.name = "Mock GPU (Fallback)"
        msg.memory_total_mib = self._fallback_total_mib
        msg.memory_used_mib = int(self._fallback_total_mib * 0.25)
        msg.utilization_pct = 15.0
        msg.temperature_c = 45.0
        msg.process_names = ["cognibot_sim"]
        msg.process_memory_mib = [msg.memory_used_mib]

    def destroy_node(self) -> bool:
        if self._nvml_initialized and pynvml is not None:
            with contextlib.suppress(Exception):
                pynvml.nvmlShutdown()
        return super().destroy_node()


def main(args: Any = None) -> None:
    rclpy.init(args=args)
    node = GpuMonitorNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
