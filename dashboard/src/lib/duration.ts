export interface RosDuration {
  sec: number;
  nanosec: number;
}

export const toSeconds = (d: RosDuration | undefined): number => (d ? d.sec + d.nanosec / 1e9 : 0);

export const fromSeconds = (s: number): RosDuration => {
  const sec = Math.floor(s);
  return { sec, nanosec: Math.round((s - sec) * 1e9) };
};

/** Fraction of a trajectory executed, from FollowJointTrajectory feedback. */
export function trajectoryProgress(desiredElapsed: number, total: number): number {
  if (total <= 0) return 1;
  return Math.min(1, Math.max(0, desiredElapsed / total));
}
