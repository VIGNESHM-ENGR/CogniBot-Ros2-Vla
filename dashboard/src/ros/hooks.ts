import { useCallback, useEffect, useRef, useState } from "react";
import { Action, Service, Topic } from "roslib";
import { useRos } from "./RosProvider";

/** Latest message on a topic (null until one arrives), re-subscribing after reconnects. */
export function useTopic<T>(name: string, messageType: string, throttleMs = 0): T | null {
  const { ros, link } = useRos();
  const [message, setMessage] = useState<T | null>(null);

  useEffect(() => {
    if (link !== "connected") return;
    const topic = new Topic<T>({ ros, name, messageType, throttle_rate: throttleMs });
    topic.subscribe(setMessage);
    return () => topic.unsubscribe();
  }, [ros, link, name, messageType, throttleMs]);

  return link === "connected" ? message : null;
}

/** Messages per second on a topic over a sliding window, measured in the browser. */
export function useTopicRate(name: string, messageType: string, windowMs = 2000): number {
  const { ros, link } = useRos();
  const stamps = useRef<number[]>([]);
  const [rate, setRate] = useState(0);

  useEffect(() => {
    if (link !== "connected") return;
    const topic = new Topic({ ros, name, messageType });
    const onMessage = () => stamps.current.push(performance.now());
    topic.subscribe(onMessage);
    const timer = setInterval(() => {
      const now = performance.now();
      stamps.current = stamps.current.filter((t) => now - t <= windowMs);
      setRate((stamps.current.length * 1000) / windowMs);
    }, 500);
    return () => {
      clearInterval(timer);
      topic.unsubscribe(onMessage);
      stamps.current = [];
    };
  }, [ros, link, name, messageType, windowMs]);

  return link === "connected" ? rate : 0;
}

export interface Graph {
  services: Set<string>;
  topics: Set<string>;
  actions: Set<string>;
}

const EMPTY_GRAPH: Graph = { services: new Set(), topics: new Set(), actions: new Set() };

/** Services, topics and action servers in the ROS graph, polled through rosapi. */
export function useGraph(pollMs = 3000): Graph {
  const { ros, link } = useRos();
  const [graph, setGraph] = useState<Graph>(EMPTY_GRAPH);

  useEffect(() => {
    if (link !== "connected") return;
    // rosapi hides the hidden `_action` services, so action servers come from their own call.
    const actionServers = new Service<object, { action_servers: string[] }>({
      ros,
      name: "/rosapi/action_servers",
      serviceType: "rosapi_msgs/srv/GetActionServers",
    });
    const poll = () => {
      ros.getServices((services) => setGraph((g) => ({ ...g, services: new Set(services) })));
      ros.getTopics((result) => setGraph((g) => ({ ...g, topics: new Set(result.topics) })));
      actionServers.callService({}, (r) =>
        setGraph((g) => ({ ...g, actions: new Set(r.action_servers) })),
      );
    };
    poll();
    const timer = setInterval(poll, pollMs);
    return () => clearInterval(timer);
  }, [ros, link, pollMs]);

  return link === "connected" ? graph : EMPTY_GRAPH;
}

export function useServiceCall<TReq, TRes>(name: string, serviceType: string) {
  const { ros } = useRos();
  return useCallback(
    (request: TReq) =>
      new Promise<TRes>((resolve, reject) =>
        new Service<TReq, TRes>({ ros, name, serviceType }).callService(request, resolve, reject),
      ),
    [ros, name, serviceType],
  );
}

export type GoalPhase = "idle" | "active" | "succeeded" | "canceled" | "failed";

export interface GoalRun<TFeedback> {
  label: string;
  phase: GoalPhase;
  feedback: TFeedback | null;
  detail: string;
  startedAt: number;
}

/** Send one goal at a time to an action server and track its lifecycle. */
export function useActionGoal<TGoal, TFeedback, TResult>(name: string, actionType: string) {
  const { ros } = useRos();
  const [run, setRun] = useState<GoalRun<TFeedback> | null>(null);
  const active = useRef<{ action: Action<TGoal, TFeedback, TResult>; id: string } | null>(null);

  const send = useCallback(
    (
      label: string,
      goal: TGoal,
      describeResult?: (result: TResult) => string,
      onSucceeded?: (result: TResult) => void,
    ) => {
      const action = new Action<TGoal, TFeedback, TResult>({ ros, name, actionType });
      const settle = (phase: GoalPhase, detail: string) => {
        if (active.current?.action === action) active.current = null;
        setRun((r) =>
          r && r.label === label && r.phase === "active" ? { ...r, phase, detail } : r,
        );
      };
      setRun({ label, phase: "active", feedback: null, detail: "", startedAt: Date.now() });
      const id = action.sendGoal(
        goal,
        (result) => {
          settle("succeeded", describeResult?.(result) ?? "");
          onSucceeded?.(result);
        },
        (feedback) => setRun((r) => (r && r.label === label ? { ...r, feedback } : r)),
        (error) => settle(active.current ? "failed" : "canceled", error),
      );
      if (id) active.current = { action, id };
      else settle("failed", "rosbridge refused the goal");
    },
    [ros, name, actionType],
  );

  const cancel = useCallback(() => {
    const current = active.current;
    if (!current) return;
    active.current = null;
    current.action.cancelGoal(current.id);
    setRun((r) =>
      r && r.phase === "active" ? { ...r, phase: "canceled", detail: "canceled" } : r,
    );
  }, []);

  return { run, send, cancel };
}
