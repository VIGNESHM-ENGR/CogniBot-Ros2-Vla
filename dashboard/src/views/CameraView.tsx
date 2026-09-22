import type { ComponentProps } from "react";
import { TOPICS } from "../config";
import { SOURCE_KEY, SOURCE_LABELS as LABELS, type SourceId } from "../lib/modes";
import { CameraFeed } from "./CameraFeed";
import { FreeLook } from "./FreeLook";

type Overlay = ComponentProps<typeof CameraFeed>["overlay"];

function Source({ id, compact, overlay }: { id: SourceId; compact?: boolean; overlay?: Overlay }) {
  if (id === "free") return <FreeLook compact={compact} />;
  const topic = id === "front" ? TOPICS.frontCamera : TOPICS.wristCamera;
  return (
    <CameraFeed
      key={topic}
      topic={topic}
      label={id === "front" ? "Front RGB-D" : "Wrist"}
      compact={compact}
      overlay={id === "front" ? overlay : null}
    />
  );
}

/**
 * The always-on viewport: the main source plus the other two as insets. F1 or V cycles the main
 * source, clicking an inset swaps it in. The agent's latest detection is drawn on the front feed.
 */
export function CameraView({
  source,
  onSource,
  overlay = null,
}: {
  source: SourceId;
  onSource: (s: SourceId) => void;
  overlay?: Overlay;
}) {
  const others = (["free", "front", "wrist"] as SourceId[]).filter((s) => s !== source);
  return (
    <div className="camera">
      <Source id={source} overlay={overlay} />
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
      <span className="source-hint legend">
        {SOURCE_KEY} · {LABELS[source]}
      </span>
    </div>
  );
}
