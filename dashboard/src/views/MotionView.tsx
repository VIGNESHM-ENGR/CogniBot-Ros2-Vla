import { useState } from "react";
import { MOVEIT, TOPICS } from "../config";
import type { GroupState } from "../lib/robotModel";
import { CameraFeed } from "./CameraFeed";
import { NotRunning } from "./NotRunning";

interface Props {
  moveitOnline: boolean;
  gripperOnline: boolean;
  groupStates: GroupState[];
  enabled: boolean;
  blockedReason: string;
  onNamedPose: (state: GroupState) => void;
  onGripper: (state: GroupState) => void;
  onPoint: (point: { x: number; y: number; z: number }) => void;
}

export function MotionView(props: Props) {
  const { moveitOnline, gripperOnline, groupStates, enabled, blockedReason } = props;
  const [point, setPoint] = useState({ x: 0.3, y: 0.0, z: 0.12 });

  if (!moveitOnline) {
    return (
      <NotRunning title="MoveIt 2 planning" missing="move_group" start="make moveit">
        Named poses, gripper commands and move-to-point plan through move_group with pick_ik. The
        simulation is up, but no /move_action server answers yet.
      </NotRunning>
    );
  }

  const arm = groupStates.filter((s) => s.group === MOVEIT.arm);
  const gripper = groupStates.filter((s) => s.group === MOVEIT.gripper);
  const axes = ["x", "y", "z"] as const;

  return (
    <div className="split">
      <div className="panel">
        {!enabled && (
          <p className="offline">
            <strong>Motion keys dead</strong>
            {blockedReason}
          </p>
        )}
        <section>
          <h2 className="legend">Named poses</h2>
          <div className="keygrid">
            {arm.map((s) => (
              <button
                key={s.name}
                type="button"
                className="key"
                disabled={!enabled}
                onClick={() => props.onNamedPose(s)}
              >
                <span className="key__legend">{s.name}</span>
              </button>
            ))}
          </div>
          <p className="note">Planned by MoveIt; poses come from the robot's SRDF.</p>
        </section>
        <section>
          <h2 className="legend">Gripper</h2>
          <div className="keygrid">
            {gripper.map((s) => (
              <button
                key={s.name}
                type="button"
                className="key"
                disabled={!enabled || !gripperOnline}
                onClick={() => props.onGripper(s)}
              >
                <span className="key__legend">{s.name}</span>
              </button>
            ))}
          </div>
        </section>
        <section>
          <h2 className="legend">Move to point</h2>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              props.onPoint(point);
            }}
          >
            <div className="fields">
              {axes.map((axis) => (
                <label key={axis} className="field">
                  <span className="legend">{axis} · m</span>
                  <input
                    type="number"
                    step="0.01"
                    value={point[axis]}
                    onChange={(e) => setPoint((p) => ({ ...p, [axis]: Number(e.target.value) }))}
                  />
                </label>
              ))}
            </div>
            <button type="submit" className="key" disabled={!enabled} style={{ width: "100%" }}>
              <span className="key__legend">Plan and move</span>
              <span className="key__cap">Enter</span>
            </button>
          </form>
          <p className="note">
            Gripper centre in {MOVEIT.base}; orientation is left free (position-only IK).
          </p>
        </section>
      </div>
      <CameraFeed topic={TOPICS.frontCamera} label="Front RGB-D" />
    </div>
  );
}
