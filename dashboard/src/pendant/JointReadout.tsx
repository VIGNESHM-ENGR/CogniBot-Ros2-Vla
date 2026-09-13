import { limitState, rangeFraction, type JointLimit } from "../lib/robotModel";
import type { JointState } from "../ros/messages";

const DEG = 180 / Math.PI;

/** Joint positions against their URDF limits, flagged near and at a limit. */
export function JointReadout({
  limits,
  state,
}: {
  limits: JointLimit[];
  state: JointState | null;
}) {
  if (!state || limits.length === 0) {
    return (
      <p className="offline">
        <strong>No joint data</strong>
        Waiting for /joint_states and /robot_description.
      </p>
    );
  }
  const position = new Map(state.name.map((n, i) => [n, state.position[i] ?? 0]));
  return (
    <>
      {limits.map((limit) => {
        const value = position.get(limit.name);
        if (value === undefined) return null;
        const status = limitState(value, limit);
        const zero = rangeFraction(0, limit);
        return (
          <div className="joint" key={limit.name}>
            <div className="joint__row">
              <span className="joint__name">{limit.name}</span>
              <span>
                {status !== "nominal" && (
                  <span className="joint__flag" data-state={status}>
                    {status === "at" ? "AT LIMIT " : "NEAR LIMIT "}
                  </span>
                )}
                <span className="joint__value">{(value * DEG).toFixed(1)}°</span>
              </span>
            </div>
            <div className="bar" aria-hidden="true">
              <span className="bar__zero" style={{ left: `${zero * 100}%` }} />
              <span
                className="bar__marker"
                data-state={status}
                style={{ left: `${rangeFraction(value, limit) * 100}%` }}
              />
            </div>
          </div>
        );
      })}
    </>
  );
}
