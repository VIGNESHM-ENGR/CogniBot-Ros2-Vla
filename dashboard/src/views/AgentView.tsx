import type { GoalRun } from "../ros/hooks";
import type { AgentEventMsg, RunAgentTaskFeedback } from "../ros/messages";

interface Props {
  agentOnline: boolean;
  run: GoalRun<RunAgentTaskFeedback> | null;
  query: string;
  onQuery: (text: string) => void;
  onRun: () => void;
  onCancel: () => void;
  events: AgentEventMsg[];
}

const KIND = ["thought", "tool call", "result", "info", "error", "done"] as const;

function content(e: AgentEventMsg): string {
  // Tool arguments and results are JSON; show them compact, everything else verbatim.
  if (e.type === 1 || e.type === 2) {
    try {
      const parsed: unknown = JSON.parse(e.content);
      if (parsed && typeof parsed === "object") {
        return Object.entries(parsed as Record<string, unknown>)
          .map(([k, v]) => `${k}=${typeof v === "number" ? v.toFixed(3) : JSON.stringify(v)}`)
          .join("  ");
      }
    } catch {
      /* plain text result */
    }
  }
  return e.content;
}

/**
 * Language agent: a task in, the model's tool calls streamed out. Its detections are drawn on the
 * front feed in the viewport, which stays on screen while the agent works.
 */
export function AgentView(props: Props) {
  const { agentOnline, run, events } = props;
  const running = run?.phase === "active";
  return (
    <div className="panel">
      <section>
        <h2 className="legend">Task</h2>
        {agentOnline ? (
          <form
            onSubmit={(e) => {
              e.preventDefault();
              if (!running) props.onRun();
            }}
          >
            <label className="field" style={{ marginBottom: 8 }}>
              <span className="legend">Instruction</span>
              <input
                type="text"
                value={props.query}
                disabled={running}
                onChange={(e) => props.onQuery(e.target.value)}
              />
            </label>
            <div className="keygrid">
              <button type="submit" className="key" disabled={running} data-flash={running}>
                <span className="led" data-on={running} />
                <span className="key__legend">Run task</span>
              </button>
              <button type="button" className="key" disabled={!running} onClick={props.onCancel}>
                <span className="key__legend">Cancel</span>
                <span className="key__cap">C</span>
              </button>
            </div>
            <p className="note">
              {running
                ? "Qwen3-VL is looking at the front camera and calling robot tools."
                : run
                  ? `${run.phase} · ${run.detail}`
                  : "The model grounds objects in the front camera and calls fetch, place, gripper and policy tools. Motion runs in MOTION mode through the same servers as the Motion view."}
            </p>
          </form>
        ) : (
          <p className="offline">
            <strong>vlm_agent not running</strong>
            Start it with <code>make vlm</code>.
          </p>
        )}
      </section>
      <section className="trace">
        <h2 className="legend">Trace</h2>
        {events.length === 0 ? (
          <p className="note">Steps appear here as the model thinks and acts.</p>
        ) : (
          <ol className="trace__list">
            {events.map((e, i) => (
              <li key={`${e.task_id}-${i}`} className="trace__row" data-kind={e.type}>
                <span className="trace__step mono">{e.step}</span>
                <span className="trace__kind legend">
                  {e.tool_name && e.type !== 0 ? e.tool_name : KIND[e.type]}
                </span>
                <span className="trace__content">{content(e)}</span>
                {e.duration_s > 0 && (
                  <span className="trace__time mono">{e.duration_s.toFixed(1)} s</span>
                )}
              </li>
            ))}
          </ol>
        )}
      </section>
    </div>
  );
}
