import { TOPICS } from "../config";
import type { SourceId } from "../lib/modes";
import { CameraFeed } from "./CameraFeed";
import { FreeLook } from "./FreeLook";

const LABELS: Record<SourceId, string> = { free: "Free look", front: "Front", wrist: "Wrist" };

function Source({ id, compact }: { id: SourceId; compact?: boolean }) {
  if (id === "free") return <FreeLook compact={compact} />;
  const topic = id === "front" ? TOPICS.frontCamera : TOPICS.wristCamera;
  return (
    <CameraFeed
      key={topic}
      topic={topic}
      label={id === "front" ? "Front RGB-D" : "Wrist"}
      compact={compact}
    />
  );
}

/** Main viewport plus the two other sources as insets; click an inset or press V to swap. */
export function CameraView({
  source,
  onSource,
}: {
  source: SourceId;
  onSource: (s: SourceId) => void;
}) {
  const others = (["free", "front", "wrist"] as SourceId[]).filter((s) => s !== source);
  return (
    <div className="camera">
      <Source id={source} />
      <div className="insets">
        {others.map((id) => (
          <button
            key={id}
            type="button"
            className="camera__inset"
            onClick={() => onSource(id)}
            aria-label={`Show ${LABELS[id]} in the main view`}
          >
            <Source id={id} compact />
          </button>
        ))}
      </div>
      <span className="source-hint legend">V · {LABELS[source]}</span>
    </div>
  );
}
