import { useCallback, useEffect, useReducer, useRef } from "react";
import { Topic } from "roslib";
import { TOPICS } from "../config";
import type { JogKey } from "../lib/modes";
import { commandFor, EMPTY_JOG, jogReducer, type TeleopCommandMsg } from "../lib/teleopKeys";
import { useRos } from "../ros/RosProvider";

const PUBLISH_HZ = 30;

/**
 * Publishes TeleopCommand at 30 Hz while jog keys are held (or a gripper toggle is pending),
 * stops on release, window blur or tab hide, and only when `enabled`.
 */
export function useKeyboardTeleop(enabled: boolean, frameId: string) {
  const { ros, link } = useRos();
  const [state, dispatch] = useReducer(jogReducer, EMPTY_JOG);
  const topic = useRef<Topic<TeleopCommandMsg> | null>(null);

  useEffect(() => {
    if (link !== "connected") return;
    const t = new Topic<TeleopCommandMsg>({
      ros,
      name: TOPICS.teleop,
      messageType: "cognibot_interfaces/msg/TeleopCommand",
    });
    t.advertise();
    topic.current = t;
    return () => {
      t.unadvertise();
      topic.current = null;
    };
  }, [ros, link]);

  useEffect(() => {
    if (!enabled) dispatch({ type: "release-all" });
  }, [enabled]);

  useEffect(() => {
    const release = () => dispatch({ type: "release-all" });
    window.addEventListener("blur", release);
    document.addEventListener("visibilitychange", release);
    return () => {
      window.removeEventListener("blur", release);
      document.removeEventListener("visibilitychange", release);
    };
  }, []);

  useEffect(() => {
    const command = enabled ? commandFor(state, frameId) : null;
    if (!command) return;
    const publish = () => {
      topic.current?.publish(command);
      dispatch({ type: "published" });
    };
    publish();
    const timer = setInterval(publish, 1000 / PUBLISH_HZ);
    return () => clearInterval(timer);
  }, [enabled, state, frameId]);

  const down = useCallback((jog: JogKey) => dispatch({ type: "down", jog }), []);
  const up = useCallback((jog: JogKey) => dispatch({ type: "up", jog }), []);
  return { held: state.held, down, up };
}
