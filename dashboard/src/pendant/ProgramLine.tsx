import type { GoalPhase } from "../ros/hooks";

export interface ProgramState {
  name: string;
  phase: GoalPhase;
  detail: string;
}

const PHASE_TEXT: Record<GoalPhase, string> = {
  idle: "idle",
  active: "running",
  succeeded: "done",
  canceled: "canceled",
  failed: "failed",
};

/** The running program: what the arm is doing, how far along, and how to cancel it. */
export function ProgramLine({
  program,
  onCancel,
}: {
  program: ProgramState | null;
  onCancel: () => void;
}) {
  const active = program?.phase === "active";
  return (
    <footer className="program" aria-live="polite">
      <span className="status__label">Program</span>
      <div style={{ minWidth: 0 }}>
        <div style={{ display: "flex", gap: 10, alignItems: "baseline", minWidth: 0 }}>
          <span className="program__name">{program ? program.name : "No program"}</span>
          <span className="program__detail">
            {program
              ? `${PHASE_TEXT[program.phase]}${program.detail ? ` · ${program.detail}` : ""}`
              : "Motion goals from the Motion view run here."}
          </span>
        </div>
        <div className="progress" aria-hidden="true">
          <span
            className="progress__fill"
            data-phase={program?.phase ?? "idle"}
            style={{ width: program ? "100%" : "0%" }}
          />
        </div>
      </div>
      <button type="button" className="key" disabled={!active} onClick={onCancel}>
        <span className="key__legend">Cancel</span>
        <span className="key__cap">C</span>
      </button>
    </footer>
  );
}
