import { RotateCcw } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { SCENE_URL, TOPICS } from "../config";
import { SceneMirror, type ObjectPose } from "../lib/sceneMirror";
import { StampBuffer, lerp, nlerpQuat } from "../lib/stampSync";
import { useTopicCallback } from "../ros/hooks";
import type { FreeJointStateArray, JointState } from "../ros/messages";

type Status = "loading" | "ready" | "error";

/** Render period. Both streams are sampled at the same sim instant on every tick. */
const TICK_MS = 100;

/** Orbitable 3D mirror of the simulation: drag to orbit, right-drag to pan, scroll to zoom. */
export function FreeLook({ compact = false }: { compact?: boolean }) {
  const host = useRef<HTMLDivElement>(null);
  const mirror = useRef<SceneMirror | null>(null);
  const [status, setStatus] = useState<Status>("loading");
  const [error, setError] = useState("");
  const [hasJoints, setHasJoints] = useState(false);

  // Arm and objects arrive on separate rosbridge queues with their own delays. Each stream is
  // buffered at full rate and, on every tick, both are interpolated at the newest instant they
  // both cover, so the cube can never be drawn from a different moment than the gripper.
  const jointBuffer = useRef(new StampBuffer<JointState>());
  const objectBuffer = useRef(new StampBuffer<FreeJointStateArray>());
  useTopicCallback<JointState>(
    TOPICS.jointStates,
    "sensor_msgs/msg/JointState",
    useCallback((m: JointState) => {
      jointBuffer.current.push(m);
      setHasJoints(true);
    }, []),
  );
  useTopicCallback<FreeJointStateArray>(
    TOPICS.objectPoses,
    "mujoco_ros2_control_msgs/msg/FreeJointStateArray",
    useCallback((m: FreeJointStateArray) => objectBuffer.current.push(m), []),
  );

  useEffect(() => {
    if (!host.current) return;
    const instance = new SceneMirror(host.current);
    mirror.current = instance;
    instance.load(SCENE_URL).then(
      () => setStatus("ready"),
      (e: unknown) => {
        setError(e instanceof Error ? e.message : String(e));
        setStatus("error");
      },
    );
    return () => {
      mirror.current = null;
      instance.dispose();
    };
  }, []);

  useEffect(() => {
    if (status !== "ready") return;
    const tick = () => {
      const joints = jointBuffer.current;
      const objects = objectBuffer.current;
      if (!joints.latest) return;
      const t = objects.latest
        ? Math.min(joints.latestStamp, objects.latestStamp)
        : joints.latestStamp;
      const j = joints.bracket(t);
      if (!j) return;
      const positions = j.before.position.map((p, i) => lerp(p, j.after.position[i] ?? p, j.alpha));
      const o = objects.bracket(t);
      const poses: ObjectPose[] = o
        ? o.before.free_joints.map((entry, i) => {
            const a = entry.pose.pose;
            const b = o.after.free_joints[i]?.pose.pose ?? a;
            return {
              name: entry.name,
              position: [
                lerp(a.position.x, b.position.x, o.alpha),
                lerp(a.position.y, b.position.y, o.alpha),
                lerp(a.position.z, b.position.z, o.alpha),
              ],
              quaternion: nlerpQuat(
                [a.orientation.w, a.orientation.x, a.orientation.y, a.orientation.z],
                [b.orientation.w, b.orientation.x, b.orientation.y, b.orientation.z],
                o.alpha,
              ),
            };
          })
        : [];
      mirror.current?.setState(j.before.name, positions, poses);
    };
    const timer = setInterval(tick, TICK_MS);
    return () => clearInterval(timer);
  }, [status]);

  return (
    <div className="camera freelook">
      <div ref={host} className="freelook__canvas" />
      {status !== "ready" && (
        <div className="nosignal" role="status">
          <span className="nosignal__title">
            {status === "loading" ? "Loading scene" : "Scene unavailable"}
          </span>
          {!compact && status === "error" && <span className="mono">{error}</span>}
        </div>
      )}
      {status === "ready" && !hasJoints && !compact && (
        <span className="freelook__note">Model at rest: no /joint_states yet</span>
      )}
      <span className="camera__tag legend">Free look</span>
      {!compact && status === "ready" && (
        <button
          type="button"
          className="key freelook__reset"
          onClick={() => mirror.current?.resetView()}
          aria-label="Reset free-look view"
        >
          <RotateCcw size={14} aria-hidden="true" />
          <span className="key__legend">View</span>
        </button>
      )}
    </div>
  );
}
