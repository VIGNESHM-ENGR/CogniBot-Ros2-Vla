import { RotateCcw } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { SCENE_URL, TOPICS } from "../config";
import { SceneMirror } from "../lib/sceneMirror";
import { useTopic } from "../ros/hooks";
import type { FreeJointStateArray, JointState } from "../ros/messages";

type Status = "loading" | "ready" | "error";

/** Orbitable 3D mirror of the simulation: drag to orbit, right-drag to pan, scroll to zoom. */
export function FreeLook({ compact = false }: { compact?: boolean }) {
  const host = useRef<HTMLDivElement>(null);
  const mirror = useRef<SceneMirror | null>(null);
  const [status, setStatus] = useState<Status>("loading");
  const [error, setError] = useState("");
  const joints = useTopic<JointState>(TOPICS.jointStates, "sensor_msgs/msg/JointState", 50);
  const objects = useTopic<FreeJointStateArray>(
    TOPICS.objectPoses,
    "mujoco_ros2_control_msgs/msg/FreeJointStateArray",
    100,
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
    if (status === "ready" && joints) mirror.current?.setJoints(joints.name, joints.position);
  }, [status, joints]);

  useEffect(() => {
    if (status !== "ready" || !objects) return;
    mirror.current?.setObjects(
      objects.free_joints.map((o) => {
        const { position: p, orientation: q } = o.pose.pose;
        return { name: o.name, position: [p.x, p.y, p.z], quaternion: [q.w, q.x, q.y, q.z] };
      }),
    );
  }, [status, objects]);

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
      {status === "ready" && !joints && !compact && (
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
