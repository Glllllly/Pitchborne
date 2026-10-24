const clamp01 = value => Math.max(0, Math.min(1, value));
const ease = value => {
  const t = clamp01(value);
  return t * t * (3 - 2 * t);
};
const mix = (a, b, t) => [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t];

// Reposition into the next event, then perform that event's action.
export function interpolatePose(previous, start, end, progress, setupShare) {
  const t = clamp01(progress);
  if (setupShare == null) {
    const reposition = Math.hypot(start[0] - previous[0], start[1] - previous[1]);
    const action = Math.hypot(end[0] - start[0], end[1] - start[1]);
    setupShare = Math.max(0.18, Math.min(0.75, reposition / (reposition + action + 1)));
  }
  if (t <= setupShare) return mix(previous, start, ease(t / setupShare));
  return mix(start, end, ease((t - setupShare) / (1 - setupShare)));
}
