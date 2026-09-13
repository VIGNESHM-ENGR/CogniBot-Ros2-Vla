"""FetchObject / PlaceObject action server using scripted top-down IK (interim planner).

Targets are `geometry_msgs/PointStamped`: an empty, `world` or base frame means the point is in
the robot base frame (the simulated base sits at the world origin); any other frame names a
MuJoCo body, resolved to its live pose for free bodies (from the simulator's free-joint topic)
or its model position for static ones, with `point` added as an offset.

Arm waypoints go to joint_trajectory_controller and the gripper to gripper_controller through
their action interfaces. P2-T09 replaces the IK script with MoveItPy planning behind the same
actions.
"""

from __future__ import annotations

import threading

import mujoco
import numpy as np
import rclpy
from builtin_interfaces.msg import Duration
from cognibot_common.robot_registry import load_robot
from cognibot_interfaces.action import FetchObject, PlaceObject
from control_msgs.action import FollowJointTrajectory, ParallelGripperCommand
from geometry_msgs.msg import Point
from mujoco_ros2_control_msgs.msg import FreeJointState, FreeJointStateArray
from mujoco_ros2_control_msgs.srv import SetFreeJointState
from rcl_interfaces.msg import ParameterDescriptor
from rclpy.action import ActionClient, ActionServer, CancelResponse, GoalResponse
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import JointState
from std_srvs.srv import Trigger
from trajectory_msgs.msg import JointTrajectoryPoint

from cognibot_motion.pick_place_ik import (
    Waypoint,
    fetch_waypoints,
    place_waypoints,
    solve_from_seeds,
)

WORLD_FRAMES = {"", "world"}


class Canceled(Exception):
    """The action goal was canceled while a sub-goal was running."""


class PickPlaceServer(Node):
    def __init__(self) -> None:
        super().__init__("pick_place_server")
        self.declare_parameter("robot", "so101", descriptor_text("Robot registry name"))
        self.declare_parameter(
            "object_poses_topic",
            "/object_poses/free_joint_states",
            descriptor_text("FreeJointStateArray topic with live object poses"),
        )
        self.declare_parameter(
            "set_free_joint_state_service",
            "/mujoco_ros2_control_node/set_free_joint_state",
            descriptor_text("mujoco_ros2_control service used to reset objects"),
        )

        self.cfg = load_robot(self.get_parameter("robot").value)
        self.model = mujoco.MjModel.from_xml_path(str(self.cfg.mjcf.scene))
        self.arm_joints = list(self.cfg.arm_joints)
        self._lock = threading.Lock()
        self._joints: dict[str, float] = {}
        self._objects: dict[str, np.ndarray] = {}
        self._busy = False

        group = ReentrantCallbackGroup()
        self.create_subscription(
            JointState,
            "/joint_states",
            self._on_joints,
            qos_profile_sensor_data,
            callback_group=group,
        )
        self.create_subscription(
            FreeJointStateArray,
            self.get_parameter("object_poses_topic").value,
            self._on_objects,
            qos_profile_sensor_data,
            callback_group=group,
        )
        self._arm = ActionClient(
            self,
            FollowJointTrajectory,
            "/joint_trajectory_controller/follow_joint_trajectory",
            callback_group=group,
        )
        self._gripper = ActionClient(
            self, ParallelGripperCommand, "/gripper_controller/gripper_cmd", callback_group=group
        )
        self._set_free = self.create_client(
            SetFreeJointState,
            self.get_parameter("set_free_joint_state_service").value,
            callback_group=group,
        )
        for name, action, run in (
            ("/cognibot/fetch_object", FetchObject, self._fetch),
            ("/cognibot/place_object", PlaceObject, self._place),
        ):
            ActionServer(
                self,
                action,
                name,
                execute_callback=run,
                goal_callback=self._accept_goal,
                cancel_callback=lambda _goal: CancelResponse.ACCEPT,
                callback_group=group,
            )
        self.create_service(
            Trigger, "/cognibot/sim/reset_objects", self._reset_objects, callback_group=group
        )
        self.get_logger().info(f"pick_place_server ready for {self.cfg.name} (scripted IK)")

    # ───────────── state ─────────────

    def _on_joints(self, msg: JointState) -> None:
        with self._lock:
            self._joints.update(zip(msg.name, msg.position, strict=False))

    def _on_objects(self, msg: FreeJointStateArray) -> None:
        with self._lock:
            for entry in msg.free_joints:
                p = entry.pose.pose.position
                self._objects[entry.name] = np.array([p.x, p.y, p.z])

    def _current_arm(self) -> np.ndarray:
        with self._lock:
            return np.array([self._joints.get(j, 0.0) for j in self.arm_joints])

    def resolve(self, frame_id: str, point: Point) -> np.ndarray:
        offset = np.array([point.x, point.y, point.z])
        if frame_id in WORLD_FRAMES or frame_id == self.cfg.base_frame:
            return offset
        with self._lock:
            live = self._objects.get(frame_id)
        if live is not None:
            return live + offset
        body = mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_BODY, frame_id)
        if body < 0:
            raise ValueError(f"unknown frame '{frame_id}'")
        if self.model.body_jntnum[body] > 0:
            raise ValueError(f"no live pose for moving body '{frame_id}' yet")
        return self.model.body_pos[body].copy() + offset

    # ───────────── actions ─────────────

    def _accept_goal(self, _goal) -> GoalResponse:
        return GoalResponse.REJECT if self._busy else GoalResponse.ACCEPT

    def _fetch(self, handle):
        return self._run(handle, FetchObject, lambda xyz: fetch_waypoints(xyz), "fetched")

    def _place(self, handle):
        return self._run(handle, PlaceObject, lambda xyz: place_waypoints(xyz), "placed")

    def _run(self, handle, action, plan, verb: str):
        result = action.Result()
        self._busy = True
        try:
            target = self.resolve(
                handle.request.target.header.frame_id, handle.request.target.point
            )
            waypoints = plan(target)
            self._execute(handle, action, waypoints)
            result.success = True
            result.message = f"{verb} at {np.round(target, 3).tolist()}"
            handle.succeed()
        except Canceled:
            result.message = "canceled"
            handle.canceled()
        except (ValueError, RuntimeError) as exc:
            result.message = str(exc)
            self.get_logger().warn(f"{action.__name__} failed: {exc}")
            handle.abort()
        finally:
            self._busy = False
        return result

    def _execute(self, handle, action, waypoints: list[Waypoint]) -> None:
        if not self._arm.wait_for_server(timeout_sec=5.0):
            raise RuntimeError("joint_trajectory_controller action server not available")
        q = self._current_arm()
        feedback = action.Feedback()
        for index, waypoint in enumerate(waypoints):
            if handle.is_cancel_requested:
                raise Canceled
            feedback.stage = waypoint.stage
            feedback.progress = index / len(waypoints)
            handle.publish_feedback(feedback)
            if waypoint.kind == "gripper":
                self._send_gripper(handle, waypoint.gripper)
                continue
            q, err = solve_from_seeds(
                self.model,
                self.arm_joints,
                self.cfg.ee_site,
                np.array(waypoint.xyz),
                [q, np.array(self.cfg.home_pose)],
            )
            if err > 0.03:
                raise RuntimeError(f"target {np.round(waypoint.xyz, 3).tolist()} out of reach")
            self._send_arm(handle, q, waypoint.seconds)
        feedback.progress = 1.0
        handle.publish_feedback(feedback)

    def _send_arm(self, handle, q: np.ndarray, seconds: float) -> None:
        goal = FollowJointTrajectory.Goal()
        goal.trajectory.joint_names = self.arm_joints
        point = JointTrajectoryPoint(positions=q.tolist())
        point.time_from_start = Duration(sec=int(seconds), nanosec=int(seconds % 1 * 1e9))
        goal.trajectory.points = [point]
        self._await(handle, self._arm, goal)

    def _send_gripper(self, handle, position: float) -> None:
        if not self._gripper.wait_for_server(timeout_sec=5.0):
            raise RuntimeError("gripper_controller action server not available")
        goal = ParallelGripperCommand.Goal()
        goal.command.name = [self.cfg.gripper.joint]
        goal.command.position = [position]
        goal.command.effort = [5.0]
        self._await(handle, self._gripper, goal)

    def _await(self, handle, client: ActionClient, goal) -> None:
        """Send a sub-goal and block this worker thread until it ends or the goal is canceled."""
        sent = client.send_goal_async(goal)
        if not wait(sent, handle):
            raise Canceled
        sub = sent.result()
        if not sub.accepted:
            raise RuntimeError("controller rejected the goal")
        done = sub.get_result_async()
        if not wait(done, handle):
            sub.cancel_goal_async()
            raise Canceled

    # ───────────── reset ─────────────

    def _reset_objects(self, _request, response):
        if not self._set_free.wait_for_service(timeout_sec=2.0):
            response.success = False
            response.message = "set_free_joint_state service not available"
            return response
        request = SetFreeJointState.Request()
        for body in range(self.model.nbody):
            if self.model.body_jntnum[body] == 0:
                continue
            joint = self.model.body_jntadr[body]
            if self.model.jnt_type[joint] != mujoco.mjtJoint.mjJNT_FREE:
                continue
            entry = FreeJointState()
            entry.name = mujoco.mj_id2name(self.model, mujoco.mjtObj.mjOBJ_BODY, body)
            px, py, pz = self.model.body_pos[body]
            qw, qx, qy, qz = self.model.body_quat[body]
            entry.pose.pose.position.x, entry.pose.pose.position.y = float(px), float(py)
            entry.pose.pose.position.z = float(pz)
            entry.pose.pose.orientation.w, entry.pose.pose.orientation.x = float(qw), float(qx)
            entry.pose.pose.orientation.y, entry.pose.pose.orientation.z = float(qy), float(qz)
            request.free_joints.append(entry)
        done = threading.Event()
        future = self._set_free.call_async(request)
        future.add_done_callback(lambda _f: done.set())
        if not done.wait(5.0) or future.result() is None:
            response.success = False
            response.message = "set_free_joint_state timed out"
            return response
        response.success = future.result().success
        response.message = future.result().message or f"reset {len(request.free_joints)} objects"
        return response


def wait(future, handle, poll: float = 0.05) -> bool:
    """Wait for a future from a worker thread; False if the action goal was canceled first."""
    event = threading.Event()
    future.add_done_callback(lambda _f: event.set())
    while not event.wait(poll):
        if handle.is_cancel_requested:
            return False
    return True


def descriptor_text(text: str) -> ParameterDescriptor:
    return ParameterDescriptor(description=text)


def main() -> None:
    rclpy.init()
    node = PickPlaceServer()
    executor = MultiThreadedExecutor(num_threads=4)
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
