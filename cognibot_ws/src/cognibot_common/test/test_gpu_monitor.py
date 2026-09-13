"""Unit tests for GpuMonitorNode with mocked NVML and fallback behavior."""

import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import rclpy
from cognibot_common.gpu_monitor import GpuMonitorNode
from cognibot_interfaces.msg import GpuStatus


class TestGpuMonitor(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        rclpy.init()

    @classmethod
    def tearDownClass(cls):
        rclpy.shutdown()

    def test_mocked_nvml_publication(self):
        """Verify GpuMonitorNode correctly maps NVML stats into GpuStatus."""
        mock_pynvml = MagicMock()
        mock_pynvml.nvmlDeviceGetCount.return_value = 1
        mock_handle = MagicMock()
        mock_pynvml.nvmlDeviceGetHandleByIndex.return_value = mock_handle
        mock_pynvml.nvmlDeviceGetName.return_value = b"NVIDIA GeForce RTX 3060"
        mock_pynvml.nvmlDeviceGetMemoryInfo.return_value = SimpleNamespace(
            total=6 * 1024 * 1024 * 1024,
            used=2 * 1024 * 1024 * 1024,
            free=4 * 1024 * 1024 * 1024,
        )
        mock_pynvml.nvmlDeviceGetUtilizationRates.return_value = SimpleNamespace(gpu=42)
        mock_pynvml.nvmlDeviceGetTemperature.return_value = 55
        mock_pynvml.NVML_TEMPERATURE_GPU = 0
        mock_pynvml.nvmlDeviceGetComputeRunningProcesses.return_value = []

        published_msgs = []

        with (
            patch("cognibot_common.gpu_monitor.pynvml", mock_pynvml),
            patch("cognibot_common.gpu_monitor.HAS_PYNVML", True),
        ):
            node = GpuMonitorNode()
            # Capture publisher
            original_publish = node._publisher.publish

            def capture_publish(msg: GpuStatus):
                published_msgs.append(msg)
                original_publish(msg)

            node._publisher.publish = capture_publish
            node._publish_status()

            self.assertEqual(len(published_msgs), 1)
            msg = published_msgs[0]
            self.assertEqual(msg.name, "NVIDIA GeForce RTX 3060")
            self.assertEqual(msg.memory_total_mib, 6144)
            self.assertEqual(msg.memory_used_mib, 2048)
            self.assertEqual(msg.utilization_pct, 42.0)
            self.assertEqual(msg.temperature_c, 55.0)

            node.destroy_node()

    def test_fallback_when_nvml_unavailable(self):
        """Verify fallback values when NVML initialization fails."""
        mock_pynvml = MagicMock()
        mock_pynvml.nvmlInit.side_effect = RuntimeError("NVML Shared Library Not Found")

        published_msgs = []

        with (
            patch("cognibot_common.gpu_monitor.pynvml", mock_pynvml),
            patch("cognibot_common.gpu_monitor.HAS_PYNVML", True),
        ):
            node = GpuMonitorNode()
            node._publisher.publish = lambda msg: published_msgs.append(msg)
            node._publish_status()

            self.assertEqual(len(published_msgs), 1)
            msg = published_msgs[0]
            self.assertEqual(msg.name, "Mock GPU (Fallback)")
            self.assertEqual(msg.memory_total_mib, 6144)
            self.assertGreater(msg.memory_used_mib, 0)
            self.assertGreater(msg.utilization_pct, 0.0)

            node.destroy_node()


if __name__ == "__main__":
    unittest.main()
