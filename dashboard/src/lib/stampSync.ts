/**
 * Sample several ROS streams at one common instant so a render never mixes stale and fresh data.
 * Both streams are buffered; the render time is the newest instant every stream covers, and each
 * stream is interpolated there.
 */

export interface Stamped {
  header: { stamp: { sec: number; nanosec: number } };
}

export const stampSeconds = (m: Stamped): number =>
  m.header.stamp.sec + m.header.stamp.nanosec / 1e9;

export interface Bracket<T> {
  before: T;
  after: T;
  /** 0 at `before`, 1 at `after`. */
  alpha: number;
}

/** Keep the most recent `capacity` messages in stamp order. */
export class StampBuffer<T extends Stamped> {
  private items: T[] = [];

  constructor(private capacity = 64) {}

  push(item: T): void {
    // Streams can arrive slightly out of order across rosbridge queues; keep the buffer sorted.
    const stamp = stampSeconds(item);
    let i = this.items.length;
    while (i > 0 && stampSeconds(this.items[i - 1] as T) > stamp) i--;
    this.items.splice(i, 0, item);
    if (this.items.length > this.capacity) this.items.shift();
  }

  get latest(): T | null {
    return this.items[this.items.length - 1] ?? null;
  }

  get latestStamp(): number {
    const last = this.latest;
    return last ? stampSeconds(last) : -Infinity;
  }

  /** Neighbouring messages around `stamp`, clamped to the buffer's ends; null when empty. */
  bracket(stamp: number): Bracket<T> | null {
    const n = this.items.length;
    if (n === 0) return null;
    const first = this.items[0] as T;
    const last = this.items[n - 1] as T;
    if (stamp <= stampSeconds(first)) return { before: first, after: first, alpha: 0 };
    if (stamp >= stampSeconds(last)) return { before: last, after: last, alpha: 0 };
    let lo = 0;
    let hi = n - 1;
    while (hi - lo > 1) {
      const mid = (lo + hi) >> 1;
      if (stampSeconds(this.items[mid] as T) <= stamp) lo = mid;
      else hi = mid;
    }
    const before = this.items[lo] as T;
    const after = this.items[hi] as T;
    const span = stampSeconds(after) - stampSeconds(before);
    return { before, after, alpha: span > 0 ? (stamp - stampSeconds(before)) / span : 0 };
  }
}

export const lerp = (a: number, b: number, t: number): number => a + (b - a) * t;

/** Normalized linear quaternion interpolation (w, x, y, z), taking the short way round. */
export function nlerpQuat(
  a: [number, number, number, number],
  b: [number, number, number, number],
  t: number,
): [number, number, number, number] {
  const sign = a[0] * b[0] + a[1] * b[1] + a[2] * b[2] + a[3] * b[3] < 0 ? -1 : 1;
  const q: [number, number, number, number] = [
    lerp(a[0], sign * b[0], t),
    lerp(a[1], sign * b[1], t),
    lerp(a[2], sign * b[2], t),
    lerp(a[3], sign * b[3], t),
  ];
  const norm = Math.hypot(...q) || 1;
  return [q[0] / norm, q[1] / norm, q[2] / norm, q[3] / norm];
}
