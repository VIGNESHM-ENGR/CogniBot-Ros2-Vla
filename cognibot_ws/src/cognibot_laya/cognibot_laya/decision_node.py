"""RunDecisionTask action server: the RLCD decision layer with its two tracks (ADR-0008).

Track A asks which skill and which object, then runs the scripted action for it. Track B asks for
one motion primitive at a time and jogs the arm through the mink teleop integrator, so the model
never produces a joint angle and `safety_filter` stays the only publisher of controller commands.

The decision model itself is `cognibot_laya.model.LayaModel`; everything the loops do with its
answers lives in the pure modules (`state`, `questions`, `decide`), which are tested without torch.
"""

from __future__ import annotations

import json
import os
import threading
import time
import urllib.request
from typing import Any

import rclpy
from builtin_interfaces.msg import Duration
from cognibot_common.robot_registry import load_robot
from cognibot_interfaces.action import (
    ExecuteSkill,
    FetchObject,
    PlaceObject,
    RunDecisionTask,
)
from cognibot_interfaces.msg import AgentEvent, ControlMode, Decision, ModelStatus, TeleopCommand
from cognibot_interfaces.srv import Decide, SetControlMode
from control_msgs.action import FollowJointTrajectory, ParallelGripperCommand
from geometry_msgs.msg import PointStamped
from mujoco_ros2_control_msgs.msg import FreeJointStateArray
from rcl_interfaces.msg import ParameterDescriptor
from rclpy.action import ActionClient, ActionServer, CancelResponse, GoalResponse
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy, qos_profile_sensor_data
from std_srvs.srv import Trigger
from tf2_ros import Buffer, TransformListener
from trajectory_msgs.msg import JointTrajectoryPoint

from cognibot_laya.decide import (
    Answer,
    Escalate,
    PrimitiveAction,
    SkillAction,
    guard_verdict,
    primitive_action,
    read_answers,
    routed_model,
    skill_action,
)
from cognibot_laya.pickplace import (
    IN_GRIPPER,
    Area,
    Geometry,
    jog_distance,
    plan_stage,
    stage_state,
    within,
)
from cognibot_laya.questions import (
    guard_questions,
    legal_motions,
    motions_toward,
    primitive_questions,
    skill_questions,
)
from cognibot_laya.state import (
    Pose,
    SceneObject,
    guard_state,
    labels_in_task,
    skill_state,
)

MODE_NAMES = {
    ControlMode.IDLE: "IDLE",
    ControlMode.TELEOP: "TELEOP",
    ControlMode.MOTION: "MOTION",
    ControlMode.VLA: "VLA",
}
# Primitive → unit vector in the base frame (forward, left, up), as TeleopCommand expects it.
PRIMITIVE_AXES: dict[str, tuple[float, float, float]] = {
    "forward": (1.0, 0.0, 0.0),
    "back": (-1.0, 0.0, 0.0),
    "left": (0.0, 1.0, 0.0),
    "right": (0.0, -1.0, 0.0),
    "up": (0.0, 0.0, 1.0),
    "down": (0.0, 0.0, -1.0),
}


class Canceled(Exception):
    """The goal was canceled while a loop was waiting."""


class DecisionNode(Node):
    def __init__(self) -> None:
        super().__init__("laya_decision")
        d = lambda text: ParameterDescriptor(description=text)  # noqa: E731
        self.declare_parameter("robot", "so101", d("registry name"))
        self.declare_parameter("registry_dir", "", d("cognibot_sim share dir; empty = ament index"))
        self.declare_parameter(
            "model", "auto", d("auto | english | multilingual | typed-decisions")
        )
        self.declare_parameter("device", "cuda", d("cuda | cpu"))
        self.declare_parameter("preload", True, d("load the English checkpoint at start-up"))
        self.declare_parameter("max_loaded", 1, d("checkpoints kept in memory"))
        self.declare_parameter(
            "snapshot_dir", "", d("local checkpoint snapshot; empty = download from the hub")
        )
        self.declare_parameter("min_confidence", 0.35, d("skills: below it a decision escalates"))
        self.declare_parameter(
            "primitive_min_confidence",
            0.0,
            d("primitives: gate; the stall watchdog guards instead"),
        )
        self.declare_parameter(
            "max_stall_steps", 4, d("primitives without 1 cm of progress before stopping")
        )
        self.declare_parameter("guard_enabled", True, d("run the guard questions before a task"))
        self.declare_parameter("guard_threshold", 0.6, d("P(flag) that blocks a task"))
        self.declare_parameter("max_steps", 12, d("skill decisions per task (track A)"))
        self.declare_parameter(
            "max_repeats", 1, d("identical actions on an unchanged scene before stopping")
        )
        self.declare_parameter("max_primitive_steps", 60, d("primitive decisions per task"))
        self.declare_parameter("max_duration_s", 180.0, d("wall-clock limit per task"))
        self.declare_parameter("step_m", 0.025, d("longest single motion primitive, m"))
        self.declare_parameter("teleop_speed", 0.1, d("= mink_teleop max_linear_speed, m/s"))
        self.declare_parameter("hover_m", 0.06, d("approach and lift height above the cube, m"))
        self.declare_parameter(
            "grasp_offset_m", 0.02, d("grasp point toward the base; = pick_place_ik.GRASP_OFFSET")
        )
        self.declare_parameter("min_jog_m", 0.005, d("a jog moving less than this is blocked"))
        self.declare_parameter(
            "target_half_extents", [0.080, 0.056], d("target area half size x, y, m")
        )
        self.declare_parameter(
            "ready_pose", [0.0, 0.29, -0.36, 1.64, 0.0], d("tool-down pose before jogging, rad")
        )
        self.declare_parameter("object_topic", "/object_poses/free_joint_states", d("sim poses"))
        self.declare_parameter("cube_half_height", 0.0125, d("m, for placing on top of a cube"))
        self.declare_parameter("min_object_x", 0.0, d("m, ignore bodies parked behind the base"))
        self.declare_parameter(
            "static_objects",
            ["target|black rectangle|0.307|0.197|0.002"],
            d("body|label|x|y|z for scene objects without a free joint"),
        )
        p = lambda n: self.get_parameter(n).value  # noqa: E731

        self.cfg = load_robot(str(p("robot")), sim_share_dir=str(p("registry_dir")) or None)
        self.base_frame = self.cfg.base_frame
        self.ee_frame = self.cfg.ee_frame
        self.statics = self._parse_statics(list(p("static_objects")))

        self._lock = threading.Lock()
        self._objects: dict[str, tuple[float, float, float]] = {}
        self._mode = ControlMode.IDLE
        self._busy = False
        self._task_id = ""
        self._step = 0
        self._held: str | None = None
        self._gripper_open = True

        group = ReentrantCallbackGroup()
        self.create_subscription(
            FreeJointStateArray,
            str(p("object_topic")),
            self._on_objects,
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

        self.decisions_pub = self.create_publisher(Decision, "/cognibot/rlcd/decisions", 50)
        self.events_pub = self.create_publisher(AgentEvent, "/cognibot/agent/events", 50)
        self.teleop_pub = self.create_publisher(TeleopCommand, "/cognibot/teleop/cmd", 10)
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
        self.create_service(Decide, "/cognibot/rlcd/decide", self._on_decide, callback_group=group)
        self.models_pub = self.create_publisher(
            ModelStatus,
            "/cognibot/models",
            QoSProfile(
                depth=1,
                reliability=ReliabilityPolicy.RELIABLE,
                durability=DurabilityPolicy.TRANSIENT_LOCAL,
            ),
        )
        # Three nodes latch on this topic; a depth-1 late subscriber (rosbridge) keeps only one of
        # their samples, so each also repeats its status to reach every new dashboard.
        self._model_msg: ModelStatus | None = None
        self.create_timer(2.0, self._repeat_model)
        self.create_service(Trigger, "/cognibot/rlcd/unload", self._on_unload, callback_group=group)
        self._model_lock = threading.Lock()
        ActionServer(
            self,
            RunDecisionTask,
            "/cognibot/rlcd/run_task",
            execute_callback=self._execute,
            goal_callback=lambda _g: GoalResponse.REJECT if self._busy else GoalResponse.ACCEPT,
            cancel_callback=lambda _g: CancelResponse.ACCEPT,
            callback_group=group,
        )

        self.model: Any = None
        self._model_error = ""
        threading.Thread(target=self._load_model, daemon=True).start()
        self.get_logger().info("laya_decision starting; loading the decision model in background")

    # ───────────── model ─────────────

    def _publish_model(self, state: int, detail: str) -> None:
        msg = ModelStatus()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.name, msg.model = "rlcd", f"Laya ({self.get_parameter('model').value})"
        msg.state, msg.detail = state, detail
        self._model_msg = msg
        self.models_pub.publish(msg)

    def _repeat_model(self) -> None:
        if self._model_msg is not None:
            self.models_pub.publish(self._model_msg)

    def _load_model(self) -> None:
        from cognibot_laya.model import LayaModel

        self._publish_model(ModelStatus.LOADING, "starting up")
        started = time.perf_counter()
        try:
            model = LayaModel(
                model=str(self.get_parameter("model").value),
                device=str(self.get_parameter("device").value),
                preload=bool(self.get_parameter("preload").value),
                max_loaded=int(self.get_parameter("max_loaded").value),
                snapshot_dir=str(self.get_parameter("snapshot_dir").value),
            )
        except Exception as exc:  # no weights, no torch, wrong revision: stay up and say so
            self._model_error = str(exc)
            self.get_logger().error(f"decision model unavailable: {exc}")
            return
        self.model = model
        self._publish_model(ModelStatus.LOADED, f"ready in {time.perf_counter() - started:.0f} s")
        self.get_logger().info(
            f"decision model ready in {time.perf_counter() - started:.1f} s "
            f"on {self.get_parameter('device').value}"
        )

    def _on_unload(self, _request, response):
        """Free the GPU for the VLM or a VLA policy; the next RLCD goal loads Laya again."""
        with self._model_lock:
            if self.model is None or not self.model.loaded:
                response.success, response.message = True, "already unloaded"
                return response
            if self._busy:
                response.success, response.message = False, "a decision run is in progress"
                return response
            self._publish_model(ModelStatus.UNLOADING, "freeing the GPU for another model")
            self.model.unload()
            self._publish_model(ModelStatus.UNLOADED, "freed for another model")
        response.success, response.message = True, "unloaded"
        return response

    def _ensure_loaded(self, handle) -> None:
        """Before a run: free the VLM (llama-swap); reload Laya if another model evicted it."""
        base = os.environ.get("LLM_BASE_URL", "")
        if base:
            try:
                url = base.rstrip("/").removesuffix("/v1") + "/api/models/unload"
                urllib.request.urlopen(urllib.request.Request(url, method="POST"), timeout=5)
            except OSError as exc:  # llm not running: nothing to free
                self.get_logger().debug(f"VLM unload skipped: {exc}")
        with self._model_lock:
            if self.model is not None and not self.model.loaded:
                self._event(
                    handle, AgentEvent.INFO, "loading the decision model onto the GPU", "laya"
                )
                self._publish_model(ModelStatus.LOADING, "reloading for an RLCD run")
                started = time.perf_counter()
                self.model.reload()
                self._publish_model(
                    ModelStatus.LOADED, f"reloaded in {time.perf_counter() - started:.0f} s"
                )

    def _predict(self, state: dict, questions: dict, route_text: str = "") -> dict:
        if self.model is None:
            raise RuntimeError(self._model_error or "the decision model is still loading")
        return self.model.predict(state, questions, route_text)

    # ───────────── inputs ─────────────

    def _on_objects(self, msg: FreeJointStateArray) -> None:
        with self._lock:
            for entry in msg.free_joints:
                p = entry.pose.pose.position
                self._objects[entry.name] = (p.x, p.y, p.z)

    def _on_mode(self, msg: ControlMode) -> None:
        self._mode = msg.mode

    @staticmethod
    def _parse_statics(entries: list[str]) -> dict[str, SceneObject]:
        out: dict[str, SceneObject] = {}
        for entry in entries:
            body, label, x, y, z = entry.split("|")
            out[label] = SceneObject(label, float(x), float(y), float(z), float(z), movable=False)
        return out

    def scene(self) -> list[SceneObject]:
        """Objects the arm could act on, in the robot base frame (which is the world origin).

        Free bodies come from the simulator's pose publisher; bodies parked behind the base (the
        cube spawner keeps them at x = −0.55) are not in the scene.
        """
        half = float(self.get_parameter("cube_half_height").value)
        min_x = float(self.get_parameter("min_object_x").value)
        with self._lock:
            live = dict(self._objects)
        objects: list[SceneObject] = []
        for body, (x, y, z) in sorted(live.items()):
            if x < min_x:
                continue
            label = body.replace("_", " ")
            objects.append(SceneObject(label, x, y, z, z + half))
        objects.extend(self.statics.values())
        return objects

    def gripper_pose(self) -> Pose | None:
        try:
            tf = self.tf_buffer.lookup_transform(self.base_frame, self.ee_frame, rclpy.time.Time())
        except Exception:
            return None
        t = tf.transform.translation
        return Pose(t.x, t.y, t.z)

    # ───────────── publishing ─────────────

    def _publish_decision(self, answer: Answer, model: str, latency_ms: float) -> Decision:
        msg = Decision()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.task_id = self._task_id
        msg.step = self._step
        msg.question_id = answer.question_id
        msg.options = list(answer.options)
        msg.probabilities = [float(v) for v in answer.probabilities]
        msg.choice = answer.choice
        msg.confidence = float(answer.confidence)
        msg.act_probability = float(answer.act_probability)
        msg.model = model
        msg.latency_ms = float(latency_ms)
        self.decisions_pub.publish(msg)
        return msg

    def _event(
        self, handle, kind: int, content: str, tool: str = "", duration: float = 0.0
    ) -> None:
        msg = AgentEvent()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.task_id = self._task_id
        msg.step = self._step
        msg.type = kind
        msg.tool_name = tool
        msg.content = content
        msg.duration_s = float(duration)
        self.events_pub.publish(msg)
        if handle is not None:
            feedback = RunDecisionTask.Feedback()
            feedback.step = self._step
            handle.publish_feedback(feedback)

    def _decide(
        self, handle, state: dict, questions: dict, route_text: str = ""
    ) -> tuple[dict, float]:
        """One forward pass, published decision by decision."""
        started = time.perf_counter()
        payload = self._predict(state, questions, route_text)
        latency = getattr(self.model, "last_latency_ms", (time.perf_counter() - started) * 1000.0)
        model = routed_model(payload) or str(self.get_parameter("model").value)
        for answer in read_answers(payload).values():
            decision = self._publish_decision(answer, model, latency)
            if handle is not None:
                feedback = RunDecisionTask.Feedback()
                feedback.step = self._step
                feedback.decision = decision
                handle.publish_feedback(feedback)
        return payload, latency

    # ───────────── robot ─────────────

    def _call(self, client, request, timeout: float = 10.0):
        done = threading.Event()
        future = client.call_async(request)
        future.add_done_callback(lambda _f: done.set())
        if not done.wait(timeout) or future.result() is None:
            raise RuntimeError(f"{client.srv_name} timed out")
        return future.result()

    def ensure_mode(self, mode: int) -> None:
        """Enter `mode`, going through IDLE when the direct transition is not allowed."""
        if self._mode == mode:
            return
        if not self._set_mode.wait_for_service(timeout_sec=2.0):
            raise RuntimeError("mode_manager not available")
        for target in (mode, ControlMode.IDLE, mode):
            request = SetControlMode.Request()
            request.mode, request.requester = target, "laya_decision"
            request.reason = "decision loop"
            reply = self._call(self._set_mode, request)
            if reply.success and target == mode:
                return
            if not reply.success and "not allowed" not in reply.message:
                raise RuntimeError(reply.message)
        raise RuntimeError(f"could not enter {MODE_NAMES.get(mode, mode)}")

    def run_action(self, client: ActionClient, goal, timeout: float, label: str, handle=None):
        if not client.wait_for_server(timeout_sec=3.0):
            raise RuntimeError(f"{label} action server not available")
        sent = client.send_goal_async(goal)
        done = threading.Event()
        sent.add_done_callback(lambda _f: done.set())
        if not done.wait(5.0):
            raise RuntimeError(f"{label}: no response to the goal")
        goal_handle = sent.result()
        if not goal_handle.accepted:
            raise RuntimeError(f"{label}: goal rejected (another goal running?)")
        finished = threading.Event()
        result_future = goal_handle.get_result_async()
        result_future.add_done_callback(lambda _f: finished.set())
        deadline = time.monotonic() + timeout
        while not finished.wait(0.2):
            if handle is not None and handle.is_cancel_requested:
                goal_handle.cancel_goal_async()
                raise Canceled
            if time.monotonic() > deadline:
                goal_handle.cancel_goal_async()
                raise RuntimeError(f"{label}: timed out after {timeout:.0f} s")
        return result_future.result().result

    def _point_goal(self, goal, x: float, y: float, z: float):
        goal.target = PointStamped()
        goal.target.header.frame_id = self.base_frame
        goal.target.point.x, goal.target.point.y, goal.target.point.z = float(x), float(y), float(z)
        return goal

    def go_home(self, handle) -> str:
        self.ensure_mode(ControlMode.MOTION)
        goal = FollowJointTrajectory.Goal()
        goal.trajectory.joint_names = list(self.cfg.arm_joints)
        point = JointTrajectoryPoint(positions=list(self.cfg.home_pose))
        point.time_from_start = Duration(sec=3)
        goal.trajectory.points = [point]
        self.run_action(self._trajectory, goal, 20.0, "home", handle)
        return "at home"

    # ───────────── track A ─────────────

    def _run_skills(
        self, handle, task: str, min_confidence: float, deadline: float
    ) -> tuple[bool, str, int]:
        decisions = 0
        last_result = ""
        max_repeats = int(self.get_parameter("max_repeats").value)
        previous: tuple = ()
        repeats = 0
        for step in range(int(self.get_parameter("max_steps").value)):
            self._step = step
            if handle.is_cancel_requested:
                raise Canceled
            if time.monotonic() > deadline:
                return False, "out of time", decisions
            objects = self.scene()
            if not objects:
                return False, "no objects in the scene yet", decisions
            holding = self._held is not None
            # Only what this gripper state can act on: movable objects to fetch, or destinations
            # for the held one. Offered everything, the model placed from an empty gripper.
            candidates = [o for o in objects if (o.label != self._held if holding else o.movable)]
            labels = [o.label for o in candidates]
            bound = self._bind_object(task, holding, labels)
            state = skill_state(
                task,
                candidates,
                gripper=self.gripper_pose(),
                held=self._held,
                gripper_open=self._gripper_open,
                last_result=last_result,
            )
            questions = skill_questions(labels, holding)
            if bound:
                del questions["object"]
                self._event(handle, AgentEvent.INFO, f"object: {bound} (named in the task)", "laya")
            payload, latency = self._decide(handle, state, questions, task)
            decisions += 1
            action, _answers = skill_action(payload, labels, min_confidence, bound)
            self._event(handle, AgentEvent.TOOL_CALL, action.describe(), "laya", latency / 1000.0)
            if isinstance(action, Escalate):
                return False, action.reason, decisions
            assert isinstance(action, SkillAction)
            if action.skill == "done":
                return True, "the model reports the task is done", decisions
            # A fixed point: the same action on an unchanged scene decides the same way forever
            # (twelve identical steps on the live arm). Allow a retry, then stop and say why.
            signature = (action.skill, action.label, self._held, self._scene_signature(objects))
            repeats = repeats + 1 if signature == previous else 0
            previous = signature
            if repeats > max_repeats:
                return (
                    False,
                    f"no progress: {action.describe()} repeated on an unchanged scene",
                    (decisions),
                )
            last_result = self._run_skill(handle, action, task, objects)
            self._event(handle, AgentEvent.TOOL_RESULT, last_result, action.skill)
        return False, "out of steps", decisions

    @staticmethod
    def _bind_object(task: str, holding: bool, labels: list[str]) -> str:
        """The object the task names for this step, or "" when the model has to choose.

        Fetch takes the first candidate the sentence names ("put the *green cube* on …"); place
        takes the last ("… on the *black rectangle*"), since the source is named before the goal.
        """
        named = labels_in_task(task, labels)
        if not named:
            return ""
        return named[-1] if holding else named[0]

    @staticmethod
    def _scene_signature(objects: list[SceneObject]) -> tuple:
        return tuple((o.label, round(o.x, 2), round(o.y, 2), round(o.z, 2)) for o in objects)

    def _run_skill(self, handle, action: SkillAction, task: str, objects: list[SceneObject]) -> str:
        found = next((o for o in objects if o.label == action.label), None)
        if action.skill == "fetch":
            if found is None:
                return f"error: '{action.label}' is no longer in the scene"
            self.ensure_mode(ControlMode.MOTION)
            goal = self._point_goal(FetchObject.Goal(), found.x, found.y, found.z)
            result = self.run_action(self._fetch, goal, 90.0, "fetch", handle)
            if result.success:
                self._held, self._gripper_open = action.label, False
            return result.message if result.success else f"error: {result.message}"
        if action.skill == "place":
            if found is None:
                return f"error: '{action.label}' is no longer in the scene"
            self.ensure_mode(ControlMode.MOTION)
            goal = self._point_goal(PlaceObject.Goal(), found.x, found.y, found.top)
            result = self.run_action(self._place, goal, 90.0, "place", handle)
            if result.success:
                self._held, self._gripper_open = None, True
            return result.message if result.success else f"error: {result.message}"
        if action.skill == "home":
            return self.go_home(handle)
        if action.skill == "vla_skill":
            goal = ExecuteSkill.Goal()
            goal.instruction = task
            goal.max_duration_s = 60.0
            result = self.run_action(self._skill, goal, 150.0, "vla_skill", handle)
            return result.message if result.success else f"error: {result.message}"
        return f"error: skill '{action.skill}' is not bound"

    # ───────────── track B ─────────────

    def _pick_target(self, handle, task: str, min_confidence: float) -> SceneObject:
        """The object the primitives move toward: the one the task names, else the model's pick."""
        objects = [o for o in self.scene() if o.movable]
        if not objects:
            raise RuntimeError("no movable objects in the scene yet")
        labels = [o.label for o in objects]
        named = labels_in_task(task, labels)
        if named:
            label, source = named[0], "named in the task"
        else:
            state = skill_state(task, objects, gripper=self.gripper_pose(), held=self._held)
            payload, _latency = self._decide(handle, state, skill_questions(labels), task)
            chosen = read_answers(payload).get("object")
            label, source = (chosen.choice if chosen is not None else ""), "model"
        found = next((o for o in objects if o.label == label), None)
        if found is None:
            raise RuntimeError(f"no target for '{task}' (got '{label}')")
        self._event(handle, AgentEvent.INFO, f"target: {found.label} ({source})", "laya")
        return found

    def _target_area(self, task: str, moving: str = "") -> Area:
        """Where the cube goes: the last thing the task names that isn't the cube being moved.

        A fixed feature (the black rectangle) is a flat area; another cube is a stack, and its
        top face is the surface to release onto. With nothing named, the first fixed feature.
        """
        objects = self.scene()
        for label in reversed(labels_in_task(task, [o.label for o in objects])):
            if label == moving:
                continue
            found = next(o for o in objects if o.label == label)
            return self._area_of(found)
        statics = list(self.statics.values())
        if not statics:
            raise RuntimeError("no target area configured (static_objects)")
        return self._area_of(statics[0])

    def _area_of(self, obj: SceneObject) -> Area:
        """A destination's surface and half extents: a cube's top face, or the marked area."""
        if obj.movable:
            half = float(self.get_parameter("cube_half_height").value)
            return Area(obj.label, obj.x, obj.y, obj.top, half, half)
        hx, hy = (float(v) for v in self.get_parameter("target_half_extents").value)
        return Area(obj.label, obj.x, obj.y, obj.z, hx, hy)

    def _jog(self, primitive: str, distance: float = 0.0) -> None:
        """Publish one primitive as teleop commands; mink integrates them into joint targets."""
        msg = TeleopCommand()
        msg.header.frame_id = self.base_frame
        seconds = distance / float(self.get_parameter("teleop_speed").value)
        if primitive in PRIMITIVE_AXES:
            x, y, z = PRIMITIVE_AXES[primitive]
            msg.linear.x, msg.linear.y, msg.linear.z = x, y, z
        elif primitive == "grasp":
            msg.gripper = TeleopCommand.GRIPPER_CLOSE
            self._gripper_open = False
        elif primitive == "release":
            msg.gripper = TeleopCommand.GRIPPER_OPEN
            self._gripper_open = True
        deadline = time.monotonic() + seconds
        while True:  # 30 Hz, the rate the dashboard jog keys use
            msg.header.stamp = self.get_clock().now().to_msg()
            self.teleop_pub.publish(msg)
            time.sleep(1 / 30)
            if msg.gripper or time.monotonic() >= deadline:  # a gripper command is one message
                break
        if primitive in PRIMITIVE_AXES:
            # Stop explicitly: mink_teleop keeps integrating the last velocity until its 300 ms
            # dead-man expires, which made a 1.85 cm jog travel 4.8 cm on the live arm.
            stop = TeleopCommand()
            stop.header.frame_id = self.base_frame
            stop.header.stamp = self.get_clock().now().to_msg()
            self.teleop_pub.publish(stop)

    def _go_ready(self, handle) -> None:
        """Park the tool pointing down before jogging.

        mink_teleop holds the tool orientation it engages with. At the zero and home poses the
        tool points forward (90° from vertical), so a top-down grasp is impossible from there; from
        this pose the unchanged teleop IK follows a whole pick-and-place within 0.2 cm at the cube
        and 1.8 cm at the target area (offline replay of its costs and limits).
        """
        self.ensure_mode(ControlMode.MOTION)
        goal = FollowJointTrajectory.Goal()
        goal.trajectory.joint_names = list(self.cfg.arm_joints)
        point = JointTrajectoryPoint(
            positions=[float(v) for v in self.get_parameter("ready_pose").value]
        )
        point.time_from_start = Duration(sec=3)
        goal.trajectory.points = [point]
        self.run_action(self._trajectory, goal, 20.0, "ready pose", handle)
        # Open the gripper here, in MOTION, through its controller. mink_teleop adopts the
        # measured gripper position when it engages, so a teleop "release" sent before that is
        # dropped: on the live arm a gripper left closed by a previous run then landed on the
        # cube's top face (blocked at z = 0.025, the cube top) instead of straddling it.
        opening = ParallelGripperCommand.Goal()
        opening.command.name = [self.cfg.gripper.joint]
        opening.command.position = [float(self.cfg.gripper.open)]
        opening.command.effort = [5.0]
        self.run_action(self._gripper, opening, 10.0, "open gripper", handle)
        self._gripper_open = True

    def _run_primitives(
        self, handle, task: str, min_confidence: float, deadline: float
    ) -> tuple[bool, str, int]:
        target = self._pick_target(handle, task, min_confidence)
        area = self._target_area(task, moving=target.label)
        stacking = area.label not in self.statics
        where = f"on top of the {area.label}" if stacking else f"the {area.label}"
        self._event(handle, AgentEvent.INFO, f"destination: {where}", "laya")
        self._go_ready(handle)
        # mink_teleop requests TELEOP on its first command, but modes.yaml refuses MOTION → TELEOP,
        # and a refused request drops every jog silently. Enter TELEOP here, through IDLE.
        self.ensure_mode(ControlMode.TELEOP)
        g = Geometry(
            grasp_offset=float(self.get_parameter("grasp_offset_m").value),
            hover=float(self.get_parameter("hover_m").value),
            # release with the cube's centre just above the table: half the cube plus 2 mm
            drop_clearance=float(self.get_parameter("cube_half_height").value) + 0.002,
        )
        step_m = float(self.get_parameter("step_m").value)
        max_stall = int(self.get_parameter("max_stall_steps").value)
        min_jog = float(self.get_parameter("min_jog_m").value)
        best_gap, stalled = float("inf"), 0
        blocked: set[str] = set()
        previous, last_cube_state, was_held = "", "", False
        decisions = 1
        for step in range(int(self.get_parameter("max_primitive_steps").value)):
            self._step = step
            if handle.is_cancel_requested:
                raise Canceled
            if time.monotonic() > deadline:
                return False, "out of time", decisions
            objects = self.scene()
            gripper = self.gripper_pose()
            cube = next((o for o in objects if o.label == target.label), None)
            if gripper is None or cube is None:
                return False, "lost the gripper transform or the cube pose", decisions
            if stacking:
                # A cube destination can itself be moved (or knocked over) mid-run: read its top
                # face again every step, the same way the stage is read from the poses.
                destination = next((o for o in objects if o.label == area.label), None)
                if destination is None:
                    return False, f"lost the {area.label}", decisions
                area = self._area_of(destination)
            stage = plan_stage(cube, gripper, self._gripper_open, was_held, area, previous, g)
            if stage.cube_state == IN_GRIPPER:
                was_held = True
            if stage.cube_state != last_cube_state:
                self._event(handle, AgentEvent.INFO, f"{cube.label}: {stage.cube_state}", "laya")
                last_cube_state = stage.cube_state
            if stage.name != previous:
                self._event(handle, AgentEvent.INFO, f"stage: {stage.name}", "laya")
                best_gap, stalled, previous = float("inf"), 0, stage.name

            if within(stage, gripper) and stage.action:
                # The stage's point is reached: its one action is the only legal primitive (a
                # motion there is a no-op or moves away), so it runs without asking the model.
                self._event(
                    handle, AgentEvent.TOOL_CALL, f"{stage.action} (only legal move)", "laya"
                )
                if stage.action == "done":
                    placed = area.contains(cube)
                    return (
                        placed,
                        (
                            f"{cube.label} placed on the {area.label} at "
                            f"({cube.x:.3f}, {cube.y:.3f}, {cube.z:.3f})"
                            if placed
                            else f"{cube.label} is outside the {area.label}"
                        ),
                        decisions,
                    )
                self._jog(stage.action)
                time.sleep(1.0)  # let the jaws close or open before the next pose reading
                if stage.action == "release":
                    was_held = False
                continue

            # Stall watchdog: progress toward this stage's aim, reset whenever the stage changes.
            gap = gripper.distance_to(stage.aim)
            if gap < best_gap - 0.01:
                best_gap, stalled = gap, 0
            else:
                stalled += 1
            if stalled > max_stall:
                why = f"; the arm could not move {', '.join(sorted(blocked))}" if blocked else ""
                return (
                    False,
                    f"no progress on '{stage.name}': {gap * 100:.1f} cm off for {stalled} steps"
                    f"{why}",
                    decisions,
                )
            # Only motions that shorten this gap are offered: one away from the aim travels a
            # full step and undoes the last one, which the model then repeats (DEVLOG 2026-09-23).
            toward = motions_toward(
                (stage.aim.x - gripper.x, stage.aim.y - gripper.y, stage.aim.z - gripper.z)
            )
            state = stage_state(task, stage, cube, gripper, self._gripper_open, area)
            payload, latency = self._decide(
                handle,
                state,
                primitive_questions(legal_motions(frozenset(blocked), toward)),
                task,
            )
            decisions += 1
            action, _answers = primitive_action(payload, min_confidence)
            self._event(
                handle,
                AgentEvent.TOOL_CALL,
                f"{action.describe()} · go to {state['go_to']}",
                "laya",
                latency / 1000.0,
            )
            if isinstance(action, Escalate):
                return False, action.reason, decisions
            assert isinstance(action, PrimitiveAction)
            self._jog(action.primitive, jog_distance(action.primitive, gripper, stage.aim, step_m))
            time.sleep(0.3)  # let the arm follow the integrated target before measuring
            moved = self.gripper_pose()
            if moved is not None and moved.distance_to(gripper) < min_jog:
                blocked.add(action.primitive)
                self._event(handle, AgentEvent.INFO, f"{action.primitive} blocked", "laya")
            else:
                blocked.clear()
        return False, "out of steps", decisions

    # ───────────── task ─────────────

    def _execute(self, handle):
        goal: RunDecisionTask.Goal = handle.request
        result = RunDecisionTask.Result()
        self._busy = True
        self._task_id = f"rlcd-{int(time.time())}"
        self._step = 0
        primitives = goal.track == RunDecisionTask.Goal.TRACK_PRIMITIVES
        # Per-track gate. Measured on 24 random offsets, Track B's right moves have confidence
        # median 0.38 but down to 0.06, and 23/24 of its moves close the gap: a 0.35 gate blocks
        # about half the good moves. Track A's wrong `done` answers sit low, so its gate stays.
        gate = "primitive_min_confidence" if primitives else "min_confidence"
        min_confidence = goal.min_confidence or float(self.get_parameter(gate).value)
        limit = goal.max_duration_s or float(self.get_parameter("max_duration_s").value)
        deadline = time.monotonic() + limit
        track = "primitives" if goal.track == RunDecisionTask.Goal.TRACK_PRIMITIVES else "skills"
        try:
            self._event(handle, AgentEvent.INFO, f"track {track}: {goal.task}", "laya")
            self._ensure_loaded(handle)
            allowed, reason = self._guard(handle, goal.task)
            if not allowed:
                self._event(handle, AgentEvent.ERROR, reason, "guard")
                result.success, result.summary = False, reason
                handle.abort()
                return result
            if goal.track == RunDecisionTask.Goal.TRACK_PRIMITIVES:
                success, summary, decisions = self._run_primitives(
                    handle, goal.task, min_confidence, deadline
                )
            else:
                success, summary, decisions = self._run_skills(
                    handle, goal.task, min_confidence, deadline
                )
            result.success, result.summary, result.decisions = success, summary, decisions
            self._event(handle, AgentEvent.DONE if success else AgentEvent.ERROR, summary, "laya")
            handle.succeed() if success else handle.abort()
            return result
        except Canceled:
            result.summary = "canceled"
            self._event(handle, AgentEvent.INFO, "canceled", "laya")
            handle.canceled()
            return result
        except Exception as exc:
            self.get_logger().error(f"decision task failed: {exc}")
            self._event(handle, AgentEvent.ERROR, str(exc), "laya")
            result.summary = str(exc)
            handle.abort()
            return result
        finally:
            self._busy = False

    def _guard(self, handle, task: str) -> tuple[bool, str]:
        if not bool(self.get_parameter("guard_enabled").value):
            return True, ""
        payload, _latency = self._decide(
            handle,
            guard_state(task, MODE_NAMES.get(self._mode, "?"), self.scene()),
            guard_questions(),
            task,
        )
        return guard_verdict(payload, float(self.get_parameter("guard_threshold").value))

    def _on_decide(self, request, response):
        """One-shot access to the model, for evaluation scripts and the dashboard's debug pane."""
        try:
            state = json.loads(request.state_json)
            questions = json.loads(request.questions_json)
            payload = self._predict(state, questions)
            response.success = True
            response.answers_json = json.dumps(payload)
            response.latency_ms = float(getattr(self.model, "last_latency_ms", 0.0))
        except Exception as exc:
            response.success = False
            response.message = str(exc)
        return response


def main() -> None:
    rclpy.init()
    node = DecisionNode()
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
