import type { ControlModeMsg, JointState } from "../ros/messages";

interface Props {
  /** True while mode_manager has granted VLA to a policy client. */
  active: boolean;
  modeMsg: ControlModeMsg | null;
  /** Latest streamed target on /cognibot/joint_command and its rate over the last 2 s. */
  command: JointState | null;
  commandRate: number;
  joints: JointState | null;
}

const deg = (rad: number) => ((rad * 180) / Math.PI).toFixed(1);

/** Live status of a streaming policy: who holds the arm, how fast it commands, where it aims. */
export function VlaView({ active, modeMsg, command, commandRate, joints }: Props) {
  const streaming = active && commandRate > 0;
  const status = streaming
    ? `Streaming · ${modeMsg?.requester}`
    : active
      ? `VLA mode held by ${modeMsg?.requester}, no commands`
      : "No policy client connected";
  const actual = new Map((joints?.name ?? []).map((n, i) => [n, joints?.position[i] ?? 0]));

  return (
    <div className="system vla">
      <section>
        <h2 className="legend">Policy stream</h2>
        <p className="vla__status" data-tone={streaming ? "on" : active ? "yellow" : "off"}>
          <span
            className="led"
            data-on={streaming}
            data-tone={active && !streaming ? "yellow" : undefined}
          />
          {status}
        </p>
        {active && command ? (
          <table className="table">
            <thead>
              <tr>
                <th>Joint</th>
                <th>Target</th>
                <th>Actual</th>
                <th>Δ</th>
              </tr>
            </thead>
            <tbody>
              {command.name.map((name, i) => {
                const target = command.position[i] ?? 0;
                const now = actual.get(name) ?? 0;
                return (
                  <tr key={name}>
                    <td className="nowrap" style={{ color: "var(--ink)" }}>
                      {name}
                    </td>
                    <td className="mono">{deg(target)}°</td>
                    <td className="mono">{deg(now)}°</td>
                    <td className="mono">{deg(target - now)}°</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        ) : (
          <p className="offline">
            <strong>Idle</strong>
            Stream a checkpoint with <code>make skill</code> (policy server from{" "}
            <code>make vla</code>
            ); the client requests VLA mode and its targets appear here as they pass the safety
            filter.
          </p>
        )}
      </section>
      <section>
        <h2 className="legend">Stream</h2>
        <table className="table">
          <tbody>
            <tr>
              <td>Command rate</td>
              <td className="mono" style={{ color: "var(--ink)" }}>
                {commandRate.toFixed(1)} Hz
              </td>
            </tr>
            <tr>
              <td>Mode holder</td>
              <td className="mono" style={{ color: "var(--ink)" }}>
                {active ? modeMsg?.requester : "—"}
              </td>
            </tr>
            <tr>
              <td>Reason</td>
              <td className="wrap">{active ? modeMsg?.reason : "—"}</td>
            </tr>
          </tbody>
        </table>
      </section>
    </div>
  );
}
