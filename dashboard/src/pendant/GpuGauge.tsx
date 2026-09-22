import { MODEL_SLOTS, stateOf } from "../lib/models";
import type { GpuStatus, ModelStatusMsg } from "../ros/messages";

/** Which of the three GPU models is resident, one row each with an LED and a state word. */
function ModelRows({ models }: { models: Record<string, ModelStatusMsg> }) {
  return (
    <ul className="models" aria-label="Models on the GPU">
      {MODEL_SLOTS.map((slot) => {
        const m = models[slot.name];
        const state = m ? stateOf(m) : "unloaded";
        const moving = state === "loading" || state === "unloading";
        return (
          <li key={slot.name} className="models__row" data-state={state}>
            <span
              className="led"
              data-on={state === "loaded"}
              data-tone={moving ? "yellow" : undefined}
            />
            <span className="models__slot legend">{slot.label}</span>
            <span className="models__name" title={m?.detail}>
              {m?.model || "—"}
            </span>
            <span className="models__state">{m ? state : "offline"}</span>
          </li>
        );
      })}
    </ul>
  );
}

/** VRAM and utilization from /cognibot/gpu, and which model holds it (/cognibot/models). */
export function GpuGauge({
  status,
  models,
}: {
  status: GpuStatus | null;
  models: Record<string, ModelStatusMsg>;
}) {
  if (!status) {
    return (
      <p className="offline">
        <strong>GPU monitor offline</strong>
        No messages on /cognibot/gpu.
      </p>
    );
  }
  if (status.name.includes("Fallback")) {
    return (
      <p className="offline">
        <strong>NVML unavailable</strong>
        gpu_monitor is publishing placeholder values; real VRAM is unknown.
      </p>
    );
  }
  const used = status.memory_used_mib;
  const total = Math.max(1, status.memory_total_mib);
  return (
    <div className="joint">
      <div className="joint__row">
        <span className="joint__name">VRAM</span>
        <span className="joint__value">
          {(used / 1024).toFixed(2)} / {(total / 1024).toFixed(1)} GiB
        </span>
      </div>
      <div className="bar bar--fill" aria-hidden="true">
        <span className="bar__fill" style={{ width: `${Math.min(100, (used / total) * 100)}%` }} />
      </div>
      <div className="joint__row">
        <span className="joint__name">Load · temp</span>
        <span className="joint__value">
          {status.utilization_pct.toFixed(0)}% · {status.temperature_c.toFixed(0)} °C
        </span>
      </div>
      <ModelRows models={models} />
    </div>
  );
}
