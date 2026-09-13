import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { Ros } from "roslib";

export type LinkState = "connecting" | "connected" | "disconnected";

interface RosContextValue {
  ros: Ros;
  link: LinkState;
  url: string;
}

const RosContext = createContext<RosContextValue | null>(null);

/** One rosbridge connection for the app, reconnecting with capped exponential backoff. */
export function RosProvider({ url, children }: { url: string; children: ReactNode }) {
  const ros = useMemo(() => new Ros({}), []);
  const [link, setLink] = useState<LinkState>("connecting");

  useEffect(() => {
    let delay = 1000;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let disposed = false;

    const connect = () => {
      if (disposed) return;
      setLink("connecting");
      ros.connect(url).catch(() => undefined);
    };
    const onConnection = () => {
      delay = 1000;
      setLink("connected");
    };
    const onClose = () => {
      if (disposed) return;
      setLink("disconnected");
      timer = setTimeout(connect, delay);
      delay = Math.min(delay * 2, 8000);
    };

    ros.on("connection", onConnection);
    ros.on("close", onClose);
    connect();
    return () => {
      disposed = true;
      clearTimeout(timer);
      ros.off("connection", onConnection);
      ros.off("close", onClose);
      ros.close();
    };
  }, [ros, url]);

  const value = useMemo(() => ({ ros, link, url }), [ros, link, url]);
  return <RosContext.Provider value={value}>{children}</RosContext.Provider>;
}

export function useRos(): RosContextValue {
  const value = useContext(RosContext);
  if (!value) throw new Error("useRos must be used inside <RosProvider>");
  return value;
}
