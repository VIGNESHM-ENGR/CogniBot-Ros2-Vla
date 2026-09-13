import type { GpuStatus } from "../ros/messages";

/** VRAM and utilization from /cognibot/gpu. Synthetic fallback data is reported as unavailable. */
export function GpuGauge({ status }: { status: GpuStatus | null }) {
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
    </div>
  );
}
