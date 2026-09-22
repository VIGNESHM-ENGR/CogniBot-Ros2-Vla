"""RunDecisionTask action server: the RLCD decision layer with its two tracks (ADR-0008).

Track A asks which skill and which object, then runs the scripted action for it. Track B asks for
one motion primitive at a time and jogs the arm through the mink teleop integrator, so the model
never produces a joint angle and `safety_filter` stays the only publisher of controller commands.

The decision model itself is `cognibot_laya.model.LayaModel`; everything the loops do with its
answers lives in the pure modules (`state`, `questions`, `decide`), which are tested without torch.
"""

from __future__ import annotations

import json
import threading
import time
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
from cognibot_interfaces.msg import AgentEvent, ControlMode, Decision, TeleopCommand
from cognibot_interfaces.srv import Decide, SetControlMode
from control_msgs.action import FollowJointTrajectory
from geometry_msgs.msg import PointStamped
from mujoco_ros2_control_msgs.msg import FreeJointStateArray
from rcl_interfaces.msg import ParameterDescriptor
from rclpy.action import ActionClient, ActionServer, CancelResponse, GoalResponse
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy, qos_profile_sensor_data
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
from cognibot_laya.questions import (
    guard_questions,
    legal_primitives,
    primitive_questions,
    skill_questions,
)
from cognibot_laya.state import (
    Pose,
    SceneObject,
    grasp_point,
    guard_state,
    labels_in_task,
    primitive_state,
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
        self.declare_parameter("device", "cpu", d("cpu | cuda"))
        self.declare_parameter("preload", True, d("load the checkpoints at start-up"))
        self.declare_parameter("max_loaded", 2, d("checkpoints kept in memory"))
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
        self.declare_parameter("step_duration_s", 0.25, d("how long one primitive jogs"))
        self.declare_parameter("tolerance_m", 0.03, d("distance that counts as arrived (track B)"))
        self.declare_parameter(
            "grasp_offset_m", 0.02, d("grasp point toward the base; = pick_place_ik.GRASP_OFFSET")
        )
        self.declare_parameter("min_jog_m", 0.005, d("a jog moving less than this is blocked"))
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
        self.create_service(Decide, "/cognibot/rlcd/decide", self._on_decide, callback_group=group)
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

    def _load_model(self) -> None:
        from cognibot_laya.model import LayaModel

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
        self.get_logger().info(
            f"decision model ready in {time.perf_counter() - started:.1f} s "
            f"on {self.get_parameter('device').value}"
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

    def _jog(self, primitive: str) -> None:
        """Publish one primitive as teleop commands; mink integrates them into joint targets."""
        seconds = float(self.get_parameter("step_duration_s").value)
        msg = TeleopCommand()
        msg.header.frame_id = self.base_frame
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
        while time.monotonic() < deadline:  # 30 Hz, the rate the dashboard jog keys use
            msg.header.stamp = self.get_clock().now().to_msg()
            self.teleop_pub.publish(msg)
            time.sleep(1 / 30)
            if msg.gripper:  # edge-triggered: one message is the command
                break

    def _run_primitives(
        self, handle, task: str, min_confidence: float, deadline: float
    ) -> tuple[bool, str, int]:
        target = self._pick_target(handle, task, min_confidence)
        # mink_teleop requests TELEOP on its first command, but modes.yaml refuses MOTION → TELEOP
        # (a Track A run leaves the arm in MOTION), and a refused request drops every jog silently.
        # Enter TELEOP here, through IDLE when needed, before the first primitive.
        self.ensure_mode(ControlMode.TELEOP)
        tolerance = float(self.get_parameter("tolerance_m").value)
        max_stall = int(self.get_parameter("max_stall_steps").value)
        offset = float(self.get_parameter("grasp_offset_m").value)
        min_jog = float(self.get_parameter("min_jog_m").value)
        best_gap, stalled = float("inf"), 0
        blocked: set[str] = set()
        aim = grasp_point(target, offset)
        decisions = 1
        for step in range(int(self.get_parameter("max_primitive_steps").value)):
            self._step = step
            if handle.is_cancel_requested:
                raise Canceled
            if time.monotonic() > deadline:
                return False, "out of time", decisions
            gripper = self.gripper_pose()
            if gripper is None:
                return False, "no gripper transform yet", decisions
            state = primitive_state(
                task,
                gripper,
                aim,
                gripper_open=self._gripper_open,
                held=self._held,
                tolerance_m=tolerance,
            )
            if state["within_reach"] and not self._gripper_open:
                return True, f"grasped at {target.label}", decisions
            # Stall watchdog: the guard for this track instead of a confidence gate.
            gap = gripper.distance_to(Pose(aim.x, aim.y, aim.z))
            if gap < best_gap - 0.01:
                best_gap, stalled = gap, 0
            else:
                stalled += 1
            if stalled > max_stall:
                why = f"; the arm could not move {', '.join(sorted(blocked))}" if blocked else ""
                return (
                    False,
                    f"no progress: {gap * 100:.1f} cm from {target.label} for {stalled} steps{why}",
                    decisions,
                )
            self._event(handle, AgentEvent.INFO, f"target is {state['target_is']}", "laya")
            options = legal_primitives(
                state["within_reach"], self._gripper_open, frozenset(blocked)
            )
            payload, latency = self._decide(handle, state, primitive_questions(options), task)
            decisions += 1
            action, _answers = primitive_action(payload, min_confidence)
            self._event(handle, AgentEvent.TOOL_CALL, action.describe(), "laya", latency / 1000.0)
            if isinstance(action, Escalate):
                return False, action.reason, decisions
            assert isinstance(action, PrimitiveAction)
            if action.primitive == "done":
                gap_cm = gripper.distance_to(Pose(target.x, target.y, target.z)) * 100
                return (
                    gap_cm <= tolerance * 100,
                    f"the model stopped {gap_cm:.1f} cm from {target.label}",
                    decisions,
                )
            self._jog(action.primitive)
            if action.primitive in PRIMITIVE_AXES:
                time.sleep(0.3)  # let the arm follow the integrated target before measuring
                moved = self.gripper_pose()
                if moved is not None and moved.distance_to(gripper) < min_jog:
                    blocked.add(action.primitive)
                    self._event(handle, AgentEvent.INFO, f"{action.primitive} blocked", "laya")
                else:
                    blocked.clear()
            # The target may have moved (a grasp drags it); refresh it from the scene.
            target = next((o for o in self.scene() if o.label == target.label), target)
            aim = grasp_point(target, offset)
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
