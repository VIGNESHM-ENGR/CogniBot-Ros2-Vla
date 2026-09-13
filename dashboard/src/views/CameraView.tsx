import { TOPICS } from "../config";
import { CameraFeed } from "./CameraFeed";

export function CameraView() {
  return (
    <div className="camera">
      <CameraFeed key={TOPICS.frontCamera} topic={TOPICS.frontCamera} label="Front RGB-D" />
      <div className="camera__inset">
        <CameraFeed key={TOPICS.wristCamera} topic={TOPICS.wristCamera} label="Wrist" compact />
      </div>
    </div>
  );
}
