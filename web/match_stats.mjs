const PITCH_LENGTH_METRES = 105;
const PITCH_WIDTH_METRES = 68;

export function estimatedShotXg(shot) {
  const [x, y] = shot.location;
  const dx = Math.max(0.5, (120 - x) * PITCH_LENGTH_METRES / 120);
  const dy = (40 - y) * PITCH_WIDTH_METRES / 80;
  const distance = Math.hypot(dx, dy);
  const halfGoal = 3.66;
  const angle = Math.abs(Math.atan2(dy + halfGoal, dx) - Math.atan2(dy - halfGoal, dx));
  const logOdds = -1.7 - 0.085 * distance + 2.4 * angle - (shot.under_pressure ? 0.35 : 0);
  return Math.max(0.01, Math.min(0.8, 1 / (1 + Math.exp(-logOdds))));
}

export function summarizeMatch(match, events) {
  const teams = [match.home_team, match.away_team];
  const shots = events.filter(event => event.type.name === "Shot");
  const keyPassIds = new Set(shots.map(event => event.shot.key_pass_id).filter(Boolean));
  return teams.map(team => {
    const own = events.filter(event => event.team.id === team.id);
    const ownShots = own.filter(event => event.type.name === "Shot");
    const passes = own.filter(event => event.type.name === "Pass");
    return {
      team,
      goals: ownShots.filter(event => event.shot.outcome.name === "Goal").length,
      shots: ownShots.length,
      shotsOnTarget: ownShots.filter(event => ["Goal", "Saved"].includes(event.shot.outcome.name)).length,
      keyPasses: passes.filter(event => keyPassIds.has(event.id) && event.pass?.outcome.name === "Complete").length,
      passes: passes.length,
      completedPasses: passes.filter(event => event.pass?.outcome.name === "Complete").length,
      xg: ownShots.reduce((sum, shot) => sum + estimatedShotXg(shot), 0),
    };
  });
}
