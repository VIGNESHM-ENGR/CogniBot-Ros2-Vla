import { useEffect, useState } from "react";
import { SERVICES } from "../config";
import { useServiceCall } from "../ros/hooks";
import type { ControllerState, GpuStatus } from "../ros/messages";
import { useRos } from "../ros/RosProvider";

interface Props {
  services: Set<string>;
  topics: Set<string>;
  gpu: GpuStatus | null;
}

export function SystemView({ services, topics, gpu }: Props) {
  const { link } = useRos();
  const list = useServiceCall<object, { controller: ControllerState[] }>(
    SERVICES.listControllers,
    "controller_manager_msgs/srv/ListControllers",
  );
  const [controllers, setControllers] = useState<ControllerState[] | null>(null);
  const available = services.has(SERVICES.listControllers);

  useEffect(() => {
    if (link !== "connected" || !available) return;
    const poll = () =>
      list({}).then(
        (r) => setControllers(r.controller),
        () => setControllers(null),
      );
    poll();
    const timer = setInterval(poll, 2000);
    return () => clearInterval(timer);
  }, [link, available, list]);

  return (
    <div className="system">
      <section>
        <h2 className="legend">Controllers</h2>
        {available && controllers ? (
          <table className="table">
            <thead>
              <tr>
                <th>Controller</th>
                <th>State</th>
                <th>Type</th>
              </tr>
            </thead>
            <tbody>
              {controllers.map((c) => (
                <tr key={c.name}>
                  <td className="nowrap" style={{ color: "var(--ink)" }}>
                    {c.name}
                  </td>
                  <td>
                    <span style={{ display: "inline-flex", gap: 6, alignItems: "center" }}>
                      <span className="led" data-on={c.state === "active"} />
                      {c.state}
                    </span>
                  </td>
                  <td className="mono wrap">{c.type.replace("/", "/\u200b")}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <p className="offline">
            <strong>controller_manager offline</strong>
            Start the simulation with <code>make sim</code>.
          </p>
        )}
      </section>
      <section>
        <h2 className="legend">ROS graph</h2>
        <table className="table">
          <tbody>
            <tr>
              <td>Topics</td>
              <td style={{ color: "var(--ink)" }}>{topics.size}</td>
            </tr>
            <tr>
              <td>Services</td>
              <td style={{ color: "var(--ink)" }}>{services.size}</td>
            </tr>
          </tbody>
        </table>
        <h2 className="legend" style={{ marginTop: 20 }}>
          GPU processes
        </h2>
        {gpu && !gpu.name.includes("Fallback") && gpu.process_names.length > 0 ? (
          <table className="table">
            <tbody>
              {gpu.process_names.map((name, i) => (
                <tr key={`${name}-${i}`}>
                  <td className="mono">{name.split("/").pop()}</td>
                  <td style={{ color: "var(--ink)", textAlign: "right" }}>
                    {gpu.process_memory_mib[i]} MiB
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <p className="offline">
            <strong>No processes reported</strong>
            {gpu && !gpu.name.includes("Fallback")
              ? "NVML inside the container cannot see per-process usage."
              : "/cognibot/gpu is not publishing real NVML values."}
          </p>
        )}
      </section>
    </div>
  );
}
