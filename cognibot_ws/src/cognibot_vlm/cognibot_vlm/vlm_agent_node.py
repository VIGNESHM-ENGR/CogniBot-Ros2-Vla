"""RunAgentTask action server: Qwen3-VL (via llama-swap) plans with tools over the front camera.

The loop itself is `agent_loop.run_task`; this node supplies the chat client (OpenAI SDK against
`LLM_BASE_URL`), the tool bindings over rclpy, the camera frame as JPEG, grounding with depth and
TF, and publishes every step as `AgentEvent`.
"""

from __future__ import annotations

import base64
import io
import json
import os
import threading
import time
import urllib.request
from pathlib import Path
from typing import Any

import numpy as np
import rclpy
from builtin_interfaces.msg import Duration
from cognibot_common.robot_registry import load_robot
from cognibot_interfaces.action import ExecuteSkill, FetchObject, PlaceObject, RunAgentTask
from cognibot_interfaces.msg import AgentEvent, ControlMode, ModelStatus, ObjectDetection
from cognibot_interfaces.srv import GetObjectCoordinates, SetControlMode
from control_msgs.action import FollowJointTrajectory, ParallelGripperCommand
from geometry_msgs.msg import PointStamped
from openai import OpenAI
from PIL import Image as PilImage
from rcl_interfaces.msg import ParameterDescriptor
from rclpy.action import ActionClient, ActionServer, CancelResponse, GoalResponse
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node
from rclpy.qos import (
    DurabilityPolicy,
    QoSProfile,
    ReliabilityPolicy,
    qos_profile_sensor_data,
)
from sensor_msgs.msg import CameraInfo, Image, JointState
from std_srvs.srv import Trigger
from tf2_ros import Buffer, TransformListener
from trajectory_msgs.msg import JointTrajectoryPoint

from cognibot_vlm.agent_loop import AssistantTurn, Event, ToolCall, run_task
from cognibot_vlm.grounding import ground_top_face, parse_boxes
from cognibot_vlm.models import vlm_state

EVENT_TYPES = {
    "thought": AgentEvent.THOUGHT,
    "tool_call": AgentEvent.TOOL_CALL,
    "tool_result": AgentEvent.TOOL_RESULT,
    "info": AgentEvent.INFO,
    "error": AgentEvent.ERROR,
    "done": AgentEvent.DONE,
}
MODE_NAMES = {ControlMode.IDLE: "IDLE", ControlMode.MOTION: "MOTION", ControlMode.VLA: "VLA"}


def image_to_numpy(msg: Image) -> np.ndarray:
    """sensor_msgs/Image rgb8/bgr8 → (H, W, 3) uint8 RGB; 32FC1 → (H, W) float32."""
    if msg.encoding == "32FC1":
        return np.frombuffer(msg.data, dtype=np.float32).reshape(msg.height, msg.width)
    array = np.frombuffer(msg.data, dtype=np.uint8).reshape(msg.height, msg.step // 3, 3)
    array = array[:, : msg.width]
    if msg.encoding == "bgr8":
        array = array[:, :, ::-1]
    elif msg.encoding != "rgb8":
        raise ValueError(f"unsupported image encoding '{msg.encoding}'")
    return np.ascontiguousarray(array)


def jpeg_base64(rgb: np.ndarray, quality: int, max_side: int = 640) -> str:
    image = PilImage.fromarray(rgb)
    if max(image.size) > max_side:
        image.thumbnail((max_side, max_side))
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=quality)
    return base64.b64encode(buffer.getvalue()).decode()


def transform_matrix(transform) -> np.ndarray:
    """geometry_msgs/TransformStamped → 4×4 matrix."""
    q = transform.transform.rotation
    t = transform.transform.translation
    x, y, z, w = q.x, q.y, q.z, q.w
    m = np.eye(4)
    m[:3, :3] = [
        [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
        [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
        [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)],
    ]
    m[:3, 3] = [t.x, t.y, t.z]
    return m


class OpenAIChat:
    """agent_loop.ChatClient over llama-swap's OpenAI-compatible endpoint."""

    def __init__(self, client: OpenAI, model: str, temperature: float, max_tokens: int) -> None:
        self.client, self.model = client, model
        self.temperature, self.max_tokens = temperature, max_tokens

    def complete(self, messages: list[dict[str, Any]], tools: list[dict]) -> AssistantTurn:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            tools=tools or None,
            tool_choice="auto" if tools else None,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )
        message = response.choices[0].message
        calls = tuple(
            ToolCall(c.id, c.function.name, c.function.arguments or "{}")
            for c in (message.tool_calls or [])
            if getattr(c, "function", None) is not None
        )
        return AssistantTurn(message.content or "", calls)


class VlmAgent(Node):
    def __init__(self) -> None:
        super().__init__("vlm_agent")
        d = lambda text: ParameterDescriptor(description=text)  # noqa: E731
        self.declare_parameter("robot", "so101", d("registry name"))
        self.declare_parameter("model_gpu", "qwen3-vl-4b-gpu", d("llama-swap profile"))
        self.declare_parameter("model_hybrid", "qwen3-vl-4b-hybrid", d("profile while VLA runs"))
        self.declare_parameter("max_steps", 12, d("tool-call steps per task"))
        self.declare_parameter("temperature", 0.1, d("sampling temperature"))
        self.declare_parameter("max_tokens", 512, d("completion tokens per turn"))
        self.declare_parameter("color_topic", "/mujoco_camera_plugin/front_rgbd/color", d("rgb8"))
        self.declare_parameter("depth_topic", "/mujoco_camera_plugin/front_rgbd/depth", d("32FC1"))
        self.declare_parameter(
            "camera_info_topic", "/mujoco_camera_plugin/front_rgbd/camera_info", d("intrinsics")
        )
        self.declare_parameter("camera_frame", "front_camera_optical_frame", d("optical frame"))
        self.declare_parameter("base_frame", "base_link", d("frame of tool coordinates"))
        self.declare_parameter("jpeg_quality", 85, d("JPEG quality sent to the model"))
        self.declare_parameter("prompt_dir", "", d("directory with system.md and grounding.md"))
        self.declare_parameter(
            "registry_dir", "", d("cognibot_sim share/source dir; empty = ament index lookup")
        )
        p = lambda n: self.get_parameter(n).value  # noqa: E731

        self.cfg = load_robot(p("robot"), sim_share_dir=p("registry_dir") or None)
        prompt_dir = Path(p("prompt_dir") or Path(__file__).resolve().parent.parent / "prompts")
        self.system_prompt = (prompt_dir / "system.md").read_text()
        self.grounding_prompt = (prompt_dir / "grounding.md").read_text()
        self.client = OpenAI(
            base_url=os.environ.get("LLM_BASE_URL", "http://127.0.0.1:8082/v1"),
            api_key=os.environ.get("LLM_API_KEY", "none"),
            timeout=180.0,
            max_retries=1,
        )
        self.base_frame = str(p("base_frame"))
        self.camera_frame = str(p("camera_frame"))
        self.jpeg_quality = int(p("jpeg_quality"))

        self._lock = threading.Lock()
        self._color: Image | None = None
        self._depth: Image | None = None
        self._info: CameraInfo | None = None
        self._joints: JointState | None = None
        self._mode = ControlMode.IDLE
        self._busy = False
        self._task_id = ""
        group = ReentrantCallbackGroup()
        self.create_subscription(
            Image, p("color_topic"), self._on_color, qos_profile_sensor_data, callback_group=group
        )
        self.create_subscription(
            Image, p("depth_topic"), self._on_depth, qos_profile_sensor_data, callback_group=group
        )
        self.create_subscription(
            CameraInfo,
            p("camera_info_topic"),
            self._on_info,
            qos_profile_sensor_data,
            callback_group=group,
        )
        self.create_subscription(
            JointState,
            "/joint_states",
            self._on_joints,
            qos_profile_sensor_data,
            callback_group=group,
        )
        self.create_subscription(
            ControlMode,
            "/cognibot/mode",
            self._on_mode,
            QoSProfile(
                depth=1,
                reliability=ReliabilityPolicy.RELIABLE,
                durability=DurabilityPolicy.TRANSIENT_LOCAL,
            ),
            callback_group=group,
        )
        self.tf_buffer = Buffer()
        self.tf_listener = TransformListener(self.tf_buffer, self, spin_thread=False)
        self.events_pub = self.create_publisher(AgentEvent, "/cognibot/agent/events", 50)
        self.detections_pub = self.create_publisher(
            ObjectDetection, "/cognibot/agent/detections", 10
        )
        self._set_mode = self.create_client(
            SetControlMode, "/cognibot/set_mode", callback_group=group
        )
        self._fetch = ActionClient(
            self, FetchObject, "/cognibot/fetch_object", callback_group=group
        )
        self._place = ActionClient(
            self, PlaceObject, "/cognibot/place_object", callback_group=group
        )
        self._skill = ActionClient(
            self, ExecuteSkill, "/cognibot/vla/execute_skill", callback_group=group
        )
        self._trajectory = ActionClient(
            self,
            FollowJointTrajectory,
            "/joint_trajectory_controller/follow_joint_trajectory",
            callback_group=group,
        )
        self._gripper = ActionClient(
            self, ParallelGripperCommand, "/gripper_controller/gripper_cmd", callback_group=group
        )
        self.create_service(
            GetObjectCoordinates,
            "/cognibot/vlm/get_object_coordinates",
            self._on_get_coordinates,
            callback_group=group,
        )
        self.models_pub = self.create_publisher(
            ModelStatus,
            "/cognibot/models",
            QoSProfile(
                depth=1,
                reliability=ReliabilityPolicy.RELIABLE,
                durability=DurabilityPolicy.TRANSIENT_LOCAL,
            ),
        )
        self._unload_rlcd = self.create_client(
            Trigger, "/cognibot/rlcd/unload", callback_group=group
        )
        self._vlm_state: tuple[int, str] | None = None
        self.create_timer(1.0, self._poll_vlm, callback_group=group)
        ActionServer(
            self,
            RunAgentTask,
            "/cognibot/agent/run_task",
            execute_callback=self._execute,
            goal_callback=lambda _g: GoalResponse.REJECT if self._busy else GoalResponse.ACCEPT,
            cancel_callback=lambda _g: CancelResponse.ACCEPT,
            callback_group=group,
        )
        self.get_logger().info(
            f"vlm_agent ready: {self.client.base_url} models {p('model_gpu')}/{p('model_hybrid')}"
        )

    # ───────────── GPU residency ─────────────

    def _poll_vlm(self) -> None:
        """Publish what llama-swap has loaded whenever it changes (dashboard GPU gauge)."""
        url = str(self.client.base_url).rstrip("/").removesuffix("/v1") + "/running"
        try:
            with urllib.request.urlopen(url, timeout=0.8) as reply:
                state = vlm_state(json.loads(reply.read()))
        except (OSError, ValueError):
            return
        if state == self._vlm_state:
            return
        self._vlm_state = state
        msg = ModelStatus()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.name, msg.state = "vlm", state[0]
        msg.model = state[1] or "Qwen3-VL-4B"
        msg.detail = "llama-swap"
        self.models_pub.publish(msg)

    def _free_rlcd(self) -> None:
        """Ask the RLCD node to drop Laya (~1.8 GB) before the VLM loads; best effort."""
        if not self._unload_rlcd.wait_for_service(timeout_sec=0.5):
            return
        done = threading.Event()
        future = self._unload_rlcd.call_async(Trigger.Request())
        future.add_done_callback(lambda _f: done.set())
        done.wait(10.0)

    # ───────────── inputs ─────────────

    def _on_color(self, msg: Image) -> None:
        with self._lock:
            self._color = msg

    def _on_depth(self, msg: Image) -> None:
        with self._lock:
            self._depth = msg

    def _on_info(self, msg: CameraInfo) -> None:
        with self._lock:
            self._info = msg

    def _on_joints(self, msg: JointState) -> None:
        with self._lock:
            self._joints = msg

    def _on_mode(self, msg: ControlMode) -> None:
        self._mode = msg.mode

    def _frame(self) -> tuple[np.ndarray, str]:
        with self._lock:
            color = self._color
        if color is None:
            raise RuntimeError("no camera image received yet")
        rgb = image_to_numpy(color)
        return rgb, jpeg_base64(rgb, self.jpeg_quality)

    def _chat(self) -> OpenAIChat:
        profile = "model_hybrid" if self._mode == ControlMode.VLA else "model_gpu"
        return OpenAIChat(
            self.client,
            str(self.get_parameter(profile).value),
            float(self.get_parameter("temperature").value),
            int(self.get_parameter("max_tokens").value),
        )

    # ───────────── task ─────────────

    def _execute(self, handle):
        goal: RunAgentTask.Goal = handle.request
        result = RunAgentTask.Result()
        self._busy = True
        self._task_id = f"task-{int(time.time())}"
        self._free_rlcd()
        try:
            try:
                _rgb, image_b64 = self._frame()
            except RuntimeError as exc:
                self._publish_event(handle, Event(0, "error", str(exc)))
                result.summary = str(exc)
                handle.abort()
                return result
            outcome = run_task(
                self._chat(),
                _Tools(self),
                self.system_prompt,
                goal.query,
                image_b64,
                on_event=lambda e: self._publish_event(handle, e),
                is_canceled=lambda: bool(handle.is_cancel_requested),
                max_steps=int(self.get_parameter("max_steps").value),
            )
            result.success = outcome.success
            result.summary = outcome.summary
            if outcome.summary == "canceled":
                handle.canceled()
            elif outcome.success:
                handle.succeed()
            else:
                handle.abort()
            return result
        except Exception as exc:  # the model endpoint or a client raised: report, don't crash
            self.get_logger().error(f"agent task failed: {exc}")
            self._publish_event(handle, Event(0, "error", str(exc)))
            result.summary = str(exc)
            handle.abort()
            return result
        finally:
            self._busy = False

    def _publish_event(self, handle, event: Event) -> None:
        msg = AgentEvent()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.task_id = self._task_id
        msg.step = int(event.step)
        msg.type = EVENT_TYPES[event.type]
        msg.tool_name = event.tool_name
        msg.content = event.content
        msg.duration_s = float(event.duration_s)
        self.events_pub.publish(msg)
        feedback = RunAgentTask.Feedback()
        feedback.event = msg
        handle.publish_feedback(feedback)

    # ───────────── grounding ─────────────

    def locate(self, label: str) -> dict[str, Any]:
        """Ask the model for boxes, ground the best one with depth + TF, publish the detection."""
        rgb, image_b64 = self._frame()
        with self._lock:
            depth_msg, info = self._depth, self._info
        if depth_msg is None or info is None:
            raise RuntimeError("no depth image or camera info yet")
        transform = self.tf_buffer.lookup_transform(
            self.base_frame, self.camera_frame, rclpy.time.Time()
        )
        chat = self._chat()
        prompt = self.grounding_prompt.replace("{label}", label)
        turn = chat.complete(
            [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"},
                        },
                    ],
                }
            ],
            [],
        )
        boxes = parse_boxes(turn.content)
        box = max(boxes, key=lambda b: b.confidence)
        depth = image_to_numpy(depth_msg)
        point, bbox_px = ground_top_face(box, depth, np.array(info.k), transform_matrix(transform))
        # The camera sees the top face; FetchObject wants the centre. Objects rest on the table
        # (z = 0), so the centre sits halfway between the table and the visible top.
        top = max(float(point[2]), 0.0)
        point[2] = top / 2.0
        detection = ObjectDetection()
        detection.header.stamp = self.get_clock().now().to_msg()
        detection.header.frame_id = self.camera_frame
        detection.label = box.label or label
        detection.confidence = float(box.confidence)
        detection.bbox_xyxy = list(bbox_px)
        detection.position.header.frame_id = self.base_frame
        detection.position.point.x, detection.position.point.y, detection.position.point.z = (
            float(point[0]),
            float(point[1]),
            float(point[2]),
        )
        detection.has_position = True
        self.detections_pub.publish(detection)
        return {
            "x": round(float(point[0]), 3),
            "y": round(float(point[1]), 3),
            "z": round(float(point[2]), 3),
            "top": round(top, 3),
            "bbox_xyxy": list(bbox_px),
            "label": detection.label,
            "image_size": [int(rgb.shape[1]), int(rgb.shape[0])],
        }

    def _on_get_coordinates(self, request, response):
        try:
            found = self.locate(request.label)
        except Exception as exc:  # model, TF or depth problems all become a failed reply
            response.success = False
            response.message = str(exc)
            return response
        response.success = True
        response.message = f"{found['label']} at {found['x'], found['y'], found['z']}"
        response.detection.label = found["label"]
        response.detection.bbox_xyxy = found["bbox_xyxy"]
        response.detection.has_position = True
        response.detection.position.header.frame_id = self.base_frame
        response.detection.position.point.x = found["x"]
        response.detection.position.point.y = found["y"]
        response.detection.position.point.z = found["z"]
        return response

    # ───────────── robot actions ─────────────

    def ensure_mode(self, mode: int) -> None:
        if self._mode == mode:
            return
        if not self._set_mode.wait_for_service(timeout_sec=2.0):
            raise RuntimeError("mode_manager not available")
        for target in (mode, ControlMode.IDLE, mode):
            request = SetControlMode.Request()
            request.mode, request.requester = target, "vlm_agent"
            request.reason = "agent tool"
            reply = self._call(self._set_mode, request)
            if reply.success and target == mode:
                return
            if not reply.success and "not allowed" not in reply.message:
                raise RuntimeError(reply.message)
        raise RuntimeError(f"could not enter {MODE_NAMES.get(mode, mode)}")

    def _call(self, client, request, timeout: float = 10.0):
        done = threading.Event()
        future = client.call_async(request)
        future.add_done_callback(lambda _f: done.set())
        if not done.wait(timeout) or future.result() is None:
            raise RuntimeError(f"{client.srv_name} timed out")
        return future.result()

    def run_action(self, client: ActionClient, goal, timeout: float, label: str):
        """Send a goal and wait for its result; raises on rejection or timeout."""
        if not client.wait_for_server(timeout_sec=3.0):
            raise RuntimeError(f"{label} action server not available")
        sent = client.send_goal_async(goal)
        done = threading.Event()
        sent.add_done_callback(lambda _f: done.set())
        if not done.wait(5.0):
            raise RuntimeError(f"{label}: no response to the goal")
        handle = sent.result()
        if not handle.accepted:
            raise RuntimeError(f"{label}: goal rejected (another goal running?)")
        finished = threading.Event()
        result_future = handle.get_result_async()
        result_future.add_done_callback(lambda _f: finished.set())
        if not finished.wait(timeout):
            handle.cancel_goal_async()
            raise RuntimeError(f"{label}: timed out after {timeout:.0f} s")
        return result_future.result().result

    def point_goal(self, goal, x: float, y: float, z: float):
        goal.target = PointStamped()
        goal.target.header.frame_id = self.base_frame
        goal.target.point.x, goal.target.point.y, goal.target.point.z = x, y, z
        return goal

    def clear_view(self) -> None:
        """Park the arm at home before grounding: after a fetch it hovers over the workspace and
        the held object becomes the highest surface in any nearby box."""
        with self._lock:
            joints = (
                dict(zip(self._joints.name, self._joints.position, strict=False))
                if self._joints
                else {}
            )
        current = np.array([joints.get(j, 0.0) for j in self.cfg.arm_joints])
        if np.max(np.abs(current - np.array(self.cfg.home_pose))) < 0.15:
            return
        self.ensure_mode(ControlMode.MOTION)
        goal = FollowJointTrajectory.Goal()
        goal.trajectory.joint_names = list(self.cfg.arm_joints)
        point = JointTrajectoryPoint(positions=list(self.cfg.home_pose))
        point.time_from_start = Duration(sec=3)
        goal.trajectory.points = [point]
        self.run_action(self._trajectory, goal, 20.0, "clear view")
        time.sleep(0.5)  # let the camera publish a frame without the arm

    def reachable(self, x: float, y: float, z: float) -> tuple[bool, str]:
        ws = self.cfg.reach.workspace_sphere
        r = float(np.linalg.norm(np.array([x, y, z]) - np.array(ws.center)))
        ok = ws.r_min <= r <= ws.r_max and z >= 0.0
        return ok, f"distance {r:.3f} m from the workspace centre (allowed {ws.r_min}–{ws.r_max})"


class _Tools:
    """agent_loop.ToolRunner bound to a VlmAgent node."""

    def __init__(self, node: VlmAgent) -> None:
        self.node = node

    def run(self, name: str, arguments: dict[str, Any]) -> str:
        n = self.node
        if name == "get_object_coordinates":
            n.clear_view()
            return json.dumps(n.locate(arguments["label"]))
        if name == "check_reachability":
            ok, why = n.reachable(arguments["x"], arguments["y"], arguments["z"])
            return json.dumps({"reachable": ok, "detail": why})
        if name in ("fetch_object", "place_object"):
            # Ground the label now, with the arm out of the view: coordinates never pass
            # through the model, so nothing can go stale between steps.
            n.clear_view()
            found = n.locate(arguments["label"])
            n.ensure_mode(ControlMode.MOTION)
            if name == "fetch_object":
                goal = n.point_goal(FetchObject.Goal(), found["x"], found["y"], found["z"])
                result = n.run_action(n._fetch, goal, 90.0, name)
            else:
                goal = n.point_goal(PlaceObject.Goal(), found["x"], found["y"], found["top"])
                result = n.run_action(n._place, goal, 90.0, name)
            if not result.success:
                return f"error: {result.message}"
            where = f"{found['label']} at x={found['x']:.3f} y={found['y']:.3f}"
            return f"{result.message} ({where}, top {found['top']:.3f})"
        if name == "move_home":
            n.clear_view()
            return "at home"
        if name == "set_gripper":
            n.ensure_mode(ControlMode.MOTION)
            goal = ParallelGripperCommand.Goal()
            goal.command.name = [n.cfg.gripper.joint]
            goal.command.position = [
                n.cfg.gripper.open if arguments["state"] == "open" else n.cfg.gripper.closed
            ]
            goal.command.effort = [5.0]
            result = n.run_action(n._gripper, goal, 15.0, name)
            return f"gripper {arguments['state']}" if result.reached_goal else "gripper stalled"
        if name == "run_vla_skill":
            goal = ExecuteSkill.Goal()
            goal.instruction = arguments["instruction"]
            goal.max_duration_s = float(arguments.get("max_duration_s", 60.0))
            result = n.run_action(n._skill, goal, goal.max_duration_s + 90.0, name)
            return result.message if result.success else f"error: {result.message}"
        raise RuntimeError(f"tool {name} is not bound")


def main() -> None:
    rclpy.init()
    node = VlmAgent()
    executor = MultiThreadedExecutor(num_threads=6)
    executor.add_node(node)
    try:
        executor.spin()
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
