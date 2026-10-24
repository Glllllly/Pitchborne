export const MATCH_REPLAY_MS = 9 * 60 * 1000;

export function buildSchedule(events) {
  if (!Array.isArray(events) || events.length < 2) return [];
  const weight = events.slice(0, -1).map((event, index) => {
    const next = events[index + 1];
    const elapsed = next.minute * 60 + next.second - event.minute * 60 - event.second;
    if (elapsed < 0) throw new Error("Match events must be chronological");
    return Math.max(0.5, elapsed) + (event.type.name === "Shot" ? 18 : 0)
      + (event.type.name === "Goal Keeper" ? 6 : 0);
  });
  const total = weight.reduce((sum, value) => sum + value, 0);
  return weight.map(value => value / total * MATCH_REPLAY_MS);
}
