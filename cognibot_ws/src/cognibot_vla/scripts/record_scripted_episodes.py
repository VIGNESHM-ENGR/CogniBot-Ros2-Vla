#!/usr/bin/env python3
"""Record LeRobot episodes of the scripted pick-and-place in the CogniBot scene.

Runs in the `vla` image beside `make sim` (which provides pick_place_server and the cameras):
each episode moves the arm home, spawns the cube at a random position, runs FetchObject then
PlaceObject through pick_place_server and records front/wrist images, joint positions
(radians) and the action (next commanded joint positions) at `fps`. Episodes whose cube does
not end on the target are discarded.

    python3 record_scripted_episodes.py --episodes 50 --root /datasets/cognibot_pick_place
"""

from __future__ import annotations

import argparse
import random
import threading
import time
from pathlib import Path

import numpy as np
import rclpy
from builtin_interfaces.msg import Duration
from cognibot_interfaces.action import FetchObject, PlaceObject
from cognibot_interfaces.msg import ControlMode
from cognibot_interfaces.srv import SetControlMode
from control_msgs.action import FollowJointTrajectory
from geometry_msgs.msg import Point
from lerobot.datasets.lerobot_dataset import LeRobotDataset
from lerobot_robot_cognibot.ros_bridge import RosBridge, image_to_numpy
from mujoco_ros2_control_msgs.msg import FreeJointState, FreeJointStateArray
from mujoco_ros2_control_msgs.srv import SetFreeJointState
from rclpy.action import ActionClient
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import Image
from trajectory_msgs.msg import JointTrajectoryPoint

JOINTS = ["shoulder_pan", "shoulder_lift", "elbow_flex", "wrist_flex", "wrist_roll", "gripper"]
ARM = JOINTS[:-1]
HOME = [0.0, -1.57, 1.57, 0.0, 0.0]
CAMERAS = {
    "front": "/mujoco_camera_plugin/front_rgbd/color",
    "wrist": "/mujoco_camera_plugin/wrist_cam/color",
}
CUBE, TARGET = "green_cube", "target"
CUBE_SPAWN = np.array([0.0974, -0.1839, 0.01495])
TARGET_POS = np.array([0.2425, 0.0, 0.001])
TASK = "pick up the green cube and place it on the blue target"


class Recorder:
    def __init__(self, fps: int) -> None:
        self.fps = fps
        self.bridge = RosBridge("episode_recorder", "/joint_states", "/cognibot/joint_command", {})
        node = self.bridge.node
        self._lock = threading.Lock()
        self._images: dict[str, np.ndarray] = {}
        self._cube: np.ndarray | None = None
        for key, topic in CAMERAS.items():
            node.create_subscription(
                Image, topic, lambda m, k=key: self._on_image(k, m), qos_profile_sensor_data
            )
        node.create_subscription(
            FreeJointStateArray,
            "/object_poses/free_joint_states",
            self._on_objects,
            qos_profile_sensor_data,
        )
        self.fetch = ActionClient(node, FetchObject, "/cognibot/fetch_object")
        self.place = ActionClient(node, PlaceObject, "/cognibot/place_object")
        self.traj = ActionClient(
            node, FollowJointTrajectory, "/joint_trajectory_controller/follow_joint_trajectory"
        )
        for client, name in ((self.fetch, "fetch"), (self.place, "place"), (self.traj, "jtc")):
            if not client.wait_for_server(timeout_sec=30.0):
                raise RuntimeError(f"{name} action server not available")
        if not self.bridge.wait_ready([], JOINTS, 20.0):
            raise RuntimeError("no joint states")
        while True:
            with self._lock:
                if len(self._images) == len(CAMERAS) and self._cube is not None:
                    break
            time.sleep(0.1)

    def _on_image(self, key: str, msg: Image) -> None:
        image = image_to_numpy(msg)
        with self._lock:
            self._images[key] = image

    def _on_objects(self, msg: FreeJointStateArray) -> None:
        for entry in msg.free_joints:
            if entry.name == CUBE:
                p = entry.pose.pose.position
                with self._lock:
                    self._cube = np.array([p.x, p.y, p.z])

    # ── helpers ──

    def _wait_goal(self, client: ActionClient, goal) -> bool:
        """Send a goal from the main thread; the bridge executor spins callbacks."""
        done = threading.Event()
        result: dict = {}

        def on_accepted(future):
            handle = future.result()
            if not handle.accepted:
                result["ok"] = False
                done.set()
                return
            handle.get_result_async().add_done_callback(
                lambda f: (result.__setitem__("ok", f.result().status == 4), done.set())
            )

        client.send_goal_async(goal).add_done_callback(on_accepted)
        done.wait(90.0)
        return bool(result.get("ok"))

    def set_mode(self, mode: int) -> None:
        req = SetControlMode.Request()
        req.mode, req.requester, req.reason = mode, "episode_recorder", "recording"
        self.bridge.call_service(SetControlMode, "/cognibot/set_mode", req)

    def go_home(self) -> bool:
        goal = FollowJointTrajectory.Goal()
        goal.trajectory.joint_names = ARM
        point = JointTrajectoryPoint(positions=HOME)
        point.time_from_start = Duration(sec=2)
        goal.trajectory.points = [point]
        return self._wait_goal(self.traj, goal)

    def spawn_cube(self, jitter: float) -> np.ndarray:
        pos = CUBE_SPAWN + np.array(
            [random.uniform(-jitter, jitter), random.uniform(-jitter, jitter), 0.0]
        )
        entry = FreeJointState()
        entry.name = CUBE
        entry.pose.pose.position.x, entry.pose.pose.position.y = float(pos[0]), float(pos[1])
        entry.pose.pose.position.z = float(pos[2])
        entry.pose.pose.orientation.w = 1.0
        req = SetFreeJointState.Request()
        req.free_joints = [entry]
        res = self.bridge.call_service(
            SetFreeJointState, "/mujoco_ros2_control_node/set_free_joint_state", req
        )
        if res is None or not res.success:
            raise RuntimeError("set_free_joint_state failed")
        time.sleep(0.5)
        return pos

    def frame(self) -> dict:
        with self._lock:
            images = {k: v.copy() for k, v in self._images.items()}
        joints = self.bridge.joints(JOINTS)
        return {"images": images, "state": np.array(joints, dtype=np.float32)}

    def cube_position(self) -> np.ndarray:
        with self._lock:
            assert self._cube is not None
            return self._cube.copy()

    def record_episode(self, dataset: LeRobotDataset, jitter: float) -> bool:
        self.set_mode(ControlMode.IDLE)
        if not self.go_home():
            return False
        self.spawn_cube(jitter)
        time.sleep(0.3)

        frames: list[dict] = []
        stop = threading.Event()

        def sample():
            period = 1.0 / self.fps
            next_t = time.monotonic()
            while not stop.is_set():
                frames.append(self.frame())
                next_t += period
                time.sleep(max(0.0, next_t - time.monotonic()))

        sampler = threading.Thread(target=sample, daemon=True)
        sampler.start()
        ok = self._wait_goal(self.fetch, self._goal(FetchObject.Goal(), CUBE))
        ok = ok and self._wait_goal(self.place, self._goal(PlaceObject.Goal(), TARGET))
        time.sleep(0.5)
        stop.set()
        sampler.join()

        final = self.cube_position()
        on_target = np.linalg.norm(final[:2] - TARGET_POS[:2]) < 0.05
        if not ok or not on_target or len(frames) < 2 * self.fps:
            print(f"  discarded (ok={ok}, on_target={on_target}, frames={len(frames)})")
            return False
        # action = next commanded state (scripted demonstrations follow the controller closely)
        for i, f in enumerate(frames[:-1]):
            dataset.add_frame(
                {
                    "observation.state": f["state"],
                    "action": frames[i + 1]["state"],
                    "observation.images.front": f["images"]["front"],
                    "observation.images.wrist": f["images"]["wrist"],
                    "task": TASK,
                }
            )
        dataset.save_episode()
        print(f"  saved {len(frames) - 1} frames, cube {np.round(final, 3).tolist()}")
        return True

    @staticmethod
    def _goal(goal, body: str):
        goal.target.header.frame_id = body
        goal.target.point = Point()
        return goal


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--episodes", type=int, default=50)
    parser.add_argument("--fps", type=int, default=30)
    parser.add_argument("--jitter", type=float, default=0.03, help="cube spawn jitter, m")
    parser.add_argument("--root", type=Path, default=Path("/datasets/cognibot_pick_place"))
    parser.add_argument("--repo-id", default="cognibot/so101_pick_place_sim")
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()
    random.seed(args.seed)

    features = {
        "observation.state": {"dtype": "float32", "shape": (6,), "names": JOINTS},
        "action": {"dtype": "float32", "shape": (6,), "names": JOINTS},
        "observation.images.front": {
            "dtype": "video",
            "shape": (480, 640, 3),
            "names": ["height", "width", "channels"],
        },
        "observation.images.wrist": {
            "dtype": "video",
            "shape": (480, 640, 3),
            "names": ["height", "width", "channels"],
        },
    }
    dataset = LeRobotDataset.create(
        args.repo_id,
        args.fps,
        features,
        root=args.root,
        robot_type="cognibot_so101",
        use_videos=True,
        image_writer_threads=4,
    )
    recorder = Recorder(args.fps)
    saved = 0
    attempts = 0
    while saved < args.episodes and attempts < 2 * args.episodes:
        attempts += 1
        print(f"episode {saved + 1}/{args.episodes} (attempt {attempts})")
        if recorder.record_episode(dataset, args.jitter):
            saved += 1
    dataset.finalize()
    recorder.set_mode(ControlMode.IDLE)
    recorder.bridge.close()
    print(f"done: {saved} episodes at {args.root}")
    if rclpy.ok():
        rclpy.shutdown()


if __name__ == "__main__":
    main()
