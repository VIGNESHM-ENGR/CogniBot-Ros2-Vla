import { currentTask, gated, rankOptions, TRACKS, type TrackId } from "../lib/decisions";
import type { GoalRun } from "../ros/hooks";
import type { AgentEventMsg, DecisionMsg, RunDecisionTaskFeedback } from "../ros/messages";

interface Props {
  /** laya_decision's RunDecisionTask action server is in the graph. */
  online: boolean;
  run: GoalRun<RunDecisionTaskFeedback> | null;
  task: string;
  onTask: (text: string) => void;
  track: TrackId;
  onTrack: (track: TrackId) => void;
  minConfidence: number;
  decisions: DecisionMsg[];
  events: AgentEventMsg[];
  stopped: boolean;
  onStart: () => void;
  onStop: () => void;
}

const pct = (p: number) => `${Math.round(p * 100)}%`;

/**
 * The decision layer: a 421M text model reads the scene as JSON and answers typed questions.
 *
 * Each row is one question with the distribution it was scored over, so a confident wrong answer
 * and an unsure one look different at a glance — the reason for using a calibrated model.
 */
export function RlcdView(props: Props) {
  const { online, run, decisions, events, minConfidence, track } = props;
  const running = run?.phase === "active";
  const rows = currentTask(decisions);
  const escalation = events.find((e) => e.type === 4);
  const last = rows[rows.length - 1];

  return (
    <div className="split rlcd">
      <div className="panel">
        <section>
          <h2 className="legend">Decision run</h2>
          {online ? (
            <form
              onSubmit={(e) => {
                e.preventDefault();
                if (!running) props.onStart();
              }}
            >
              <fieldset className="rlcd__tracks">
                <legend className="legend">Track</legend>
                {TRACKS.map((t) => (
                  <button
                    key={t.id}
                    type="button"
                    className="key"
                    aria-pressed={track === t.id}
                    disabled={running}
                    onClick={() => props.onTrack(t.id)}
                  >
                    <span className="led" data-on={track === t.id} />
                    <span className="key__legend">{t.label}</span>
                  </button>
                ))}
              </fieldset>
              <p className="note">{TRACKS[track].help}</p>
              <label className="field" style={{ marginBottom: 8 }}>
                <span className="legend">Task</span>
                <input
                  type="text"
                  value={props.task}
                  disabled={running}
                  onChange={(e) => props.onTask(e.target.value)}
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
                  <span className="key__legend">Run decisions</span>
                </button>
                <button type="button" className="key" disabled={!running} onClick={props.onStop}>
                  <span className="key__legend">Stop</span>
                  <span className="key__cap">C</span>
                </button>
              </div>
              <p className="note">
                {running
                  ? `Deciding · step ${last?.step ?? 0} · ${TRACKS[track].legend.toLowerCase()}.`
                  : run
                    ? `${run.phase} · ${run.detail}`
                    : props.stopped
                      ? "Stopped: release the stop (R) before a decision run."
                      : `The model reads the object poses and joint angles as JSON and answers one question set per step. Answers under ${pct(minConfidence)} confidence escalate instead of moving the arm.`}
              </p>
            </form>
          ) : (
            <p className="offline">
              <strong>laya_decision not running</strong>
              Start it with <code>make rlcd</code>.
            </p>
          )}
        </section>
        <section className="trace">
          <h2 className="legend">Decisions</h2>
          {rows.length === 0 ? (
            <p className="note">
              Each step shows the question, every option the model scored and the confidence the
              gate reads.
            </p>
          ) : (
            <ol className="rlcd__list">
              {rows.map((d, i) => {
                const blocked = gated(d, minConfidence);
                return (
                  <li
                    key={`${d.task_id}-${i}`}
                    className="rlcd__row"
                    data-blocked={blocked || undefined}
                  >
                    <span className="rlcd__step mono">{d.step}</span>
                    <span className="rlcd__question legend">{d.question_id}</span>
                    <span className="rlcd__confidence">
                      <span
                        className="led"
                        data-on={!blocked}
                        data-tone={blocked ? "yellow" : undefined}
                      />
                      <span className="mono">{pct(d.confidence)}</span>
                      <span className="rlcd__gatelabel">{blocked ? "escalated" : "acted"}</span>
                    </span>
                    <ul className="rlcd__options">
                      {rankOptions(d).map((option) => (
                        <li
                          key={option.label}
                          className="rlcd__option"
                          data-chosen={option.chosen || undefined}
                        >
                          <span className="rlcd__optionname">{option.label}</span>
                          <span className="rlcd__bar">
                            <span
                              className="rlcd__barfill"
                              style={{ inlineSize: pct(option.probability) }}
                            />
                          </span>
                          <span className="rlcd__prob mono">{pct(option.probability)}</span>
                        </li>
                      ))}
                    </ul>
                  </li>
                );
              })}
            </ol>
          )}
        </section>
      </div>
      <div className="panel rlcd__side">
        <section>
          <h2 className="legend">Model</h2>
          <table className="table">
            <tbody>
              <tr>
                <td>Checkpoint</td>
                <td className="mono" style={{ color: "var(--ink)" }}>
                  {last?.model || "—"}
                </td>
              </tr>
              <tr>
                <td>Decision latency</td>
                <td className="mono" style={{ color: "var(--ink)" }}>
                  {last ? `${last.latency_ms.toFixed(0)} ms` : "—"}
                </td>
              </tr>
              <tr>
                <td>Confidence gate</td>
                <td className="mono" style={{ color: "var(--ink)" }}>
                  {pct(minConfidence)}
                </td>
              </tr>
              <tr>
                <td>Decisions</td>
                <td className="mono" style={{ color: "var(--ink)" }}>
                  {rows.length}
                </td>
              </tr>
            </tbody>
          </table>
          <p className="note">
            Laya scores each option at its own mask token; it never sees the camera. Grounding stays
            with the Agent view, and the arm is driven by the same actions and safety filter as
            every other view.
          </p>
        </section>
        <section className="trace">
          <h2 className="legend">Steps</h2>
          {events.length === 0 ? (
            <p className="note">What the loop did with each decision appears here.</p>
          ) : (
            <ol className="trace__list">
              {events.map((e, i) => (
                <li key={`${e.task_id}-step-${i}`} className="trace__row" data-kind={e.type}>
                  <span className="trace__step mono">{e.step}</span>
                  <span className="trace__content">{e.content}</span>
                </li>
              ))}
            </ol>
          )}
          {escalation && (
            <p className="rlcd__escalation">
              <span className="led" data-tone="yellow" data-on />
              {escalation.content}
            </p>
          )}
        </section>
      </div>
    </div>
  );
}
