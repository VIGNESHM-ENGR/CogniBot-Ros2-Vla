import { useState } from "react";
import { CUBES, DEMO, MOVEIT, cubeBody, type CubeColor } from "../config";
import type { GroupState } from "../lib/robotModel";

interface Props {
  moveitOnline: boolean;
  gripperOnline: boolean;
  pickPlaceOnline: boolean;
  resetOnline: boolean;
  objectPosition: [number, number, number] | null;
  groupStates: GroupState[];
  enabled: boolean;
  blockedReason: string;
  onNamedPose: (state: GroupState) => void;
  onGripper: (state: GroupState) => void;
  onPoint: (point: { x: number; y: number; z: number }) => void;
  onPickPlace: () => void;
  onReset: () => void;
  cube: CubeColor;
  onCube: (color: CubeColor) => void;
  onSpawn: (x: number, y: number) => void;
}

function Offline({ service, start }: { service: string; start: string }) {
  return (
    <p className="offline">
      <strong>{service} not running</strong>
      Start it with <code>{start}</code>.
    </p>
  );
}

export function MotionView(props: Props) {
  const { moveitOnline, gripperOnline, pickPlaceOnline, resetOnline, groupStates, enabled } = props;
  const [point, setPoint] = useState({ x: 0.3, y: 0.0, z: 0.12 });
  const [spawnAt, setSpawnAt] = useState({ x: 0.27, y: -0.02 });
  const arm = groupStates.filter((s) => s.group === MOVEIT.arm);
  const gripper = groupStates.filter((s) => s.group === MOVEIT.gripper);
  const axes = ["x", "y", "z"] as const;
  const cube = props.objectPosition;

  return (
    <div className="panel">
      {!enabled && (
        <p className="offline">
          <strong>Motion keys dead</strong>
          {props.blockedReason}
        </p>
      )}

      <section>
        <h2 className="legend">IK pick and place</h2>
        {pickPlaceOnline ? (
          <>
            <div className="keygrid">
              <button type="button" className="key" disabled={!enabled} onClick={props.onPickPlace}>
                <span className="key__legend">Pick and place</span>
              </button>
              <button type="button" className="key" disabled={!resetOnline} onClick={props.onReset}>
                <span className="key__legend">Reset cube</span>
              </button>
            </div>
            <p className="note">
              {cubeBody(props.cube)}{" "}
              {cube
                ? `at (${cube.map((v) => v.toFixed(3)).join(", ")}) m`
                : "position unknown (no object poses)"}
              {" → "}
              {DEMO.target}. Scripted top-down IK, no planner.
            </p>
          </>
        ) : (
          <Offline service="pick_place_server" start="make sim" />
        )}
      </section>

      <section>
        <h2 className="legend">Spawn cube</h2>
        {resetOnline ? (
          <form
            onSubmit={(e) => {
              e.preventDefault();
              props.onSpawn(spawnAt.x, spawnAt.y);
            }}
          >
            <div className="swatches" role="radiogroup" aria-label="Cube colour">
              {CUBES.map((color) => (
                <button
                  key={color}
                  type="button"
                  role="radio"
                  aria-checked={props.cube === color}
                  className="swatch"
                  data-color={color}
                  onClick={() => props.onCube(color)}
                >
                  <span className="swatch__chip" />
                  <span className="key__legend">{color}</span>
                </button>
              ))}
            </div>
            <div className="fields">
              {(["x", "y"] as const).map((axis) => (
                <label key={axis} className="field">
                  <span className="legend">{axis} · m</span>
                  <input
                    type="number"
                    step="0.01"
                    value={spawnAt[axis]}
                    onChange={(e) => setSpawnAt((p) => ({ ...p, [axis]: Number(e.target.value) }))}
                  />
                </label>
              ))}
              <span className="field">
                <span className="legend">z · m</span>
                <span className="field__fixed">floor</span>
              </span>
            </div>
            <button type="submit" className="key" style={{ width: "100%" }}>
              <span className="key__legend">Spawn</span>
            </button>
            <p className="note">
              Places the selected cube on the floor at (x, y) in the base frame; the pick above
              picks the selected colour. Reset parks every cube again.
            </p>
          </form>
        ) : (
          <Offline service="simulator" start="make sim" />
        )}
      </section>

      <section>
        <h2 className="legend">Named poses</h2>
        {moveitOnline ? (
          <>
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
          </>
        ) : (
          <Offline service="move_group" start="make sim" />
        )}
      </section>

      {moveitOnline && (
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
      )}

      {moveitOnline && (
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
      )}
    </div>
  );
}
