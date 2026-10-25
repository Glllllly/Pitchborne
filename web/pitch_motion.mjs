const clamp01 = value => Math.max(0, Math.min(1, value));
const ease = value => {
  const t = clamp01(value);
  return t * t * (3 - 2 * t);
};
const mix = (a, b, t) => [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t];

// Tracking coordinates use a 120 x 80 grid for a roughly 105 x 68 m pitch.
export function pitchDistanceMetres(a, b) {
  return Math.hypot((a[0] - b[0]) * 105 / 120, (a[1] - b[1]) * 68 / 80);
}

// Smoothstep reaches 1.5 times its average speed at the midpoint. Limit the
// distance first so even that peak stays within the player's running speed.
export function playerMotion(from, target, progress, durationMs, maxSpeedMps) {
  const distance = pitchDistanceMetres(from, target);
  if (!distance) return [...from];
  const reachable = Math.min(1, maxSpeedMps * durationMs / 1000 / (1.5 * distance));
  return mix(from, target, reachable * ease(progress));
}

// A short acceleration and braking phase makes long runs readable without
// spending most of the event in slow smoothstep easing.
const runEase = value => {
  const t=clamp01(value),r=.12,normal=1-r;
  if(t<r)return t*t/(2*r*normal);
  if(t>1-r)return 1-(1-t)*(1-t)/(2*r*normal);
  return (t-r/2)/normal;
};

export function runningPose(previous,start,end,progress,setupShare){
  const t=clamp01(progress);
  if(t<=setupShare)return mix(previous,start,runEase(t/setupShare));
  return mix(start,end,ease((t-setupShare)/(1-setupShare)));
}

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

export function coordinatedMotion(previous, start, end, progress, setupShare, arrivalAt=1){
  const t=clamp01(progress);
  const arrival=Math.max(setupShare+.05,Math.min(1,arrivalAt));
  const mapped=t<=setupShare?t:setupShare+clamp01((t-setupShare)/(arrival-setupShare))*(1-setupShare);
  return interpolatePose(previous,start,end,mapped,setupShare);
}

export function setupShareFor(repositionDistance){
  return Math.max(.24,Math.min(.48,.24+repositionDistance/140));
}
