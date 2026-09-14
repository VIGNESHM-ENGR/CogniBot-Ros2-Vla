import type { GoalRun } from "../ros/hooks";
import type { ControlModeMsg, ExecuteSkillFeedback, JointState } from "../ros/messages";

interface Props {
  /** True while mode_manager has granted VLA to a policy client. */
  active: boolean;
  modeMsg: ControlModeMsg | null;
  /** Latest streamed target on /cognibot/joint_command and its rate over the last 2 s. */
  command: JointState | null;
  commandRate: number;
  joints: JointState | null;
  /** skill_executor's ExecuteSkill action server is in the graph. */
  executorOnline: boolean;
  run: GoalRun<ExecuteSkillFeedback> | null;
  instruction: string;
  onInstruction: (text: string) => void;
  stopped: boolean;
  onStart: () => void;
  onStop: () => void;
}

const deg = (rad: number) => ((rad * 180) / Math.PI).toFixed(1);

/** Live status of a streaming policy: who holds the arm, how fast it commands, where it aims. */
export function VlaView(props: Props) {
  const { active, modeMsg, command, commandRate, joints, executorOnline, run } = props;
  const streaming = active && commandRate > 0;
  const running = run?.phase === "active";
  const status = streaming
    ? `Streaming · ${modeMsg?.requester}`
    : active
      ? `VLA mode held by ${modeMsg?.requester}, no commands`
      : "No policy client connected";
  const actual = new Map((joints?.name ?? []).map((n, i) => [n, joints?.position[i] ?? 0]));

  return (
    <div className="system vla">
      <section>
        <h2 className="legend">Policy run</h2>
        {executorOnline ? (
          <form
            onSubmit={(e) => {
              e.preventDefault();
              if (!running) props.onStart();
            }}
          >
            <label className="field" style={{ marginBottom: 8 }}>
              <span className="legend">Instruction</span>
              <input
                type="text"
                value={props.instruction}
                disabled={running}
                onChange={(e) => props.onInstruction(e.target.value)}
              />
            </label>
            <div className="keygrid">
              <button
                type="submit"
                className="key"
                disabled={running || props.stopped}
                data-flash={running}
              >
                <span className="led" data-on={running} />
                <span className="key__legend">Start policy</span>
              </button>
              <button type="button" className="key" disabled={!running} onClick={props.onStop}>
                <span className="key__legend">Stop policy</span>
                <span className="key__cap">C</span>
              </button>
            </div>
            <p className="note">
              {running
                ? `Running · ${Math.round(run.feedback?.elapsed_s ?? 0)} s · ${(run.feedback?.rate_hz ?? 0).toFixed(0)} Hz. The client takes VLA mode itself and hands the arm back to IDLE when stopped.`
                : run
                  ? `${run.label}: ${run.phase} · ${run.detail}`
                  : props.stopped
                    ? "Stopped: release the stop (R) before starting a policy."
                    : "Starts the vla-client's configured checkpoint with this instruction; Esc or STOP ends it."}
            </p>
          </form>
        ) : (
          <p className="offline">
            <strong>skill_executor not running</strong>
            Start it with <code>make vla</code>.
          </p>
        )}
      </section>
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
      <section className="vla__side">
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
