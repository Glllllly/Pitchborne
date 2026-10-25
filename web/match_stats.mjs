const PITCH_LENGTH_METRES = 105;
const PITCH_WIDTH_METRES = 68;
const LONG_PASS_METRES = 30;

function eventSecond(event) {
  return Number(event.minute || 0) * 60 + Number(event.second || 0);
}

function passDistanceMetres(event) {
  if (Number.isFinite(event.kinematics?.ball_distance_m)) return event.kinematics.ball_distance_m;
  const start = event.location, end = event.pass?.end_location;
  if (!Array.isArray(start) || !Array.isArray(end)) return 0;
  return Math.hypot((end[0] - start[0]) * PITCH_LENGTH_METRES / 120,
                    (end[1] - start[1]) * PITCH_WIDTH_METRES / 80);
}

function cardName(event) {
  return event.bad_behaviour?.card?.name || event.foul_committed?.card?.name || "";
}

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
  const possessionSeconds = new Map(teams.map(team => [team.id, 0]));
  events.forEach((event, index) => {
    if (event.type.name === "Full Time") return;
    const owner = event.possession_team?.id;
    if (!possessionSeconds.has(owner)) return;
    const elapsed = Math.max(0, (events[index + 1] ? eventSecond(events[index + 1]) :
      eventSecond(event) + (Number(event.duration) || 0)) - eventSecond(event));
    possessionSeconds.set(owner, possessionSeconds.get(owner) + elapsed);
  });
  const possessionTotal = [...possessionSeconds.values()].reduce((sum, seconds) => sum + seconds, 0);
  return teams.map(team => {
    const own = events.filter(event => event.team.id === team.id);
    const ownShots = own.filter(event => event.type.name === "Shot");
    const passes = own.filter(event => event.type.name === "Pass");
    const averageSpeed = rows => rows.length ? rows.reduce((total,event)=>total+(event.kinematics?.ball_speed_kmh||0),0)/rows.length : 0;
    return {
      team,
      goals: ownShots.filter(event => event.shot.outcome.name === "Goal").length,
      shots: ownShots.length,
      shotsOnTarget: ownShots.filter(event => ["Goal", "Saved"].includes(event.shot.outcome.name)).length,
      shotsInsideBox: ownShots.filter(event => Array.isArray(event.location) && event.location[0] >= 102 &&
        event.location[1] >= 18 && event.location[1] <= 62).length,
      shotsOutsideBox: ownShots.filter(event => !Array.isArray(event.location) || event.location[0] < 102 ||
        event.location[1] < 18 || event.location[1] > 62).length,
      possession: possessionTotal ? (possessionSeconds.get(team.id) || 0) / possessionTotal : 0,
      offsides: own.filter(event => event.type.name === "Offside").length,
      fouls: own.filter(event => event.type.name === "Foul Committed").length,
      yellowCards: own.filter(event => ["Yellow Card", "Second Yellow"].includes(cardName(event))).length,
      redCards: own.filter(event => ["Red Card", "Second Yellow"].includes(cardName(event))).length,
      longPasses: passes.filter(event => passDistanceMetres(event) >= LONG_PASS_METRES).length,
      keyPasses: passes.filter(event => keyPassIds.has(event.id) && event.pass?.outcome.name === "Complete").length,
      passes: passes.length,
      completedPasses: passes.filter(event => event.pass?.outcome.name === "Complete").length,
      passAccuracy: passes.length ? passes.filter(event => event.pass?.outcome.name === "Complete").length / passes.length : 0,
      averagePassSpeed: averageSpeed(passes),
      averageShotSpeed: averageSpeed(ownShots),
      xg: ownShots.reduce((sum, shot) => sum + estimatedShotXg(shot), 0),
    };
  });
}
