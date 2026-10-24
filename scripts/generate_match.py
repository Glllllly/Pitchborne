"""Seeded, fictional 90-minute event stream for the local replay app."""

import argparse
import copy
import json
import random
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from workflow.pipeline import ROOT
from workflow.match_commentary import build_tracks

SAMPLE = ROOT / "data" / "synthetic" / "match.json"


def clamp(value, low, high):
    return round(max(low, min(high, value)), 2)


def generate(seed):
    if not isinstance(seed, int) or not 0 <= seed <= 1_000_000_000:
        raise ValueError("seed must be an integer between 0 and 1,000,000,000")
    rng = random.Random(seed)
    match = copy.deepcopy(json.loads(SAMPLE.read_text(encoding="utf-8")))
    match["match_id"] = 1_000_000_000 + seed
    match["seed"] = seed
    match["generator_version"] = 4
    match["coverage"] = "Synthetic on-ball event stream across 90 simulated minutes; not continuous optical tracking."
    match["provenance"] = "Generated from this repository's seeded fictional simulator; no real match records copied."
    match["coordinate_system"]["attacking_direction"] = "positive_x for all supplied clips"
    match["tracking"]["type"] = "synthetic_event_keyframes"
    match["tracking"]["limitations"] = "Schematic positions within each event; no continuous player tracking, collision or offside model."
    roster = match["players"]
    teams = [match["home_team"], match["away_team"]]
    by_team = {team["id"]: [p for p in roster if p["team_id"] == team["id"]] for team in teams}
    events, candidates = [], []
    score = [0, 0]
    possession = 0
    forced_team_i = None

    def event_id(index):
        return str(uuid5(NAMESPACE_URL, f"pilot-full-match-v1/{seed}/{index}"))

    def tracking(event, target):
        own = event["team"]["id"]
        active = event["player"]["id"]
        receiver = event.get("pass", {}).get("recipient", {}).get("id")
        x, y = event["location"]
        points = []
        for entry in roster:
            pid = entry["player"]["id"]
            same = entry["team_id"] == own
            shirt = entry["shirt_number"]
            if entry["position"] == "GK":
                point = [6 if same else 117, 40]
            else:
                row = (shirt - 2) // 3
                lane = (shirt - 2) % 3
                px = (max(15, x - 35) + row * 14) if same else (min(111, x + 19) + row * 3)
                py = (17 + lane * 23 + (y - 40) * .22) if same else (18 + lane * 22 + (y - 40) * .16)
                point = [clamp(px, 2, 118), clamp(py, 2, 78)]
            if pid == active:
                point = list(event["location"])
            elif pid == receiver:
                point = list(target[:2])
            end = list(point)
            if pid == active and event["type"]["name"] == "Carry":
                end = list(target[:2])
            elif pid != receiver and pid != active and entry["position"] != "GK":
                end = [clamp(point[0] + (.4 if same else -.3), 1, 119), point[1]]
            points.append(({"player_id": pid, "team_id": entry["team_id"], "location": point},
                           {"player_id": pid, "team_id": entry["team_id"], "location": end}))
        return {"synthetic": True, "duration_seconds": 1.2,
                "start": [a for a, _ in points], "end": [b for _, b in points],
                "ball_start": event["location"][:2], "ball_end": target[:2]}

    def emit(kind, clock, team, player, location, details=None, target=None):
        index = len(events) + 1
        clock = min(5400, int(clock))
        period = 1 if clock < 2700 else 2
        local = clock if period == 1 else clock - 2700
        item = {
            "id": event_id(index), "index": index, "period": period,
            "timestamp": f"00:{local // 60:02d}:{local % 60:02d}.000",
            "minute": clock // 60, "second": clock % 60,
            "type": {"name": kind}, "possession": possession,
            "possession_team": team, "team": team, "player": player,
            "location": [round(location[0], 2), round(location[1], 2)],
            "duration": 1.2, "play_pattern": {"name": "Regular Play"},
            "synthetic": True, "related_events": [],
        }
        if details:
            item.update(details)
        item["tracking"] = tracking(item, target or location)
        events.append(item)
        return item

    clock = 0
    while clock < 5370:
        possession += 1
        team_i = (rng.randrange(2) if possession == 1 else
                  forced_team_i if forced_team_i is not None else
                  1 - team_i if rng.random() < .67 else team_i)
        forced_team_i = None
        team = teams[team_i]
        other_team = teams[1 - team_i]
        squad = [p["player"] for p in by_team[team["id"]] if p["position"] != "GK"]
        opponents = [p["player"] for p in by_team[other_team["id"]] if p["position"] != "GK"]
        passer, receiver = rng.sample(squad, 2)
        x, y = rng.uniform(24, 55), rng.uniform(12, 68)
        completed = rng.random() < .82
        shot_chance = completed and rng.random() < .11
        if shot_chance:
            receiver = rng.choice([p["player"] for p in by_team[team["id"]]
                                   if p["position"] in ("ST", "LW", "RW", "CM")])
            passer = rng.choice([p for p in squad if p["id"] != receiver["id"]])
            x = rng.uniform(78, 94)
        pass_end = [clamp(x + rng.uniform(3, 9), 7, 112), clamp(y + rng.uniform(-8, 8), 5, 75)]
        pass_event = emit("Pass", clock, team, passer, [x, y], {
            "pass": {"recipient": receiver, "end_location": pass_end,
                     "height": {"name": "Ground Pass"}, "body_part": {"name": "Right Foot"},
                     "outcome": {"name": "Complete" if completed else "Incomplete"}}}, pass_end)
        if not completed:
            interceptor = rng.choice(opponents)
            interception = emit("Interception", clock + 2, other_team, interceptor, pass_end)
            interception["possession_team"] = team
            pass_event["related_events"] = [interception["id"]]
            interception["related_events"] = [pass_event["id"]]
            forced_team_i = 1 - team_i
            clock += rng.randint(16, 27)
            continue
        receipt = emit("Ball Receipt*", clock + 2, team, receiver, pass_end)
        carry_end = [clamp(pass_end[0] + rng.uniform(2, 5), 7, 113), clamp(pass_end[1] + rng.uniform(-3, 3), 5, 75)]
        carry = emit("Carry", clock + 3, team, receiver, pass_end,
                     {"carry": {"end_location": carry_end}}, carry_end)
        chain = [pass_event, receipt, carry]
        if not shot_chance and rng.random() < .22:
            challenger = rng.choice(opponents)
            kind = "Tackle" if rng.random() < .4 else "Pressure"
            challenge = emit(kind, clock + 5, other_team, challenger, carry_end)
            challenge["possession_team"] = team
            chain.append(challenge)
            if kind == "Tackle":
                forced_team_i = 1 - team_i
        if shot_chance and clock + 6 < 5400:
            keeper = next(p["player"] for p in by_team[other_team["id"]] if p["position"] == "GK")
            defender = rng.choice(opponents)
            if not {"Goal", "Saved", "Off T"}.issubset({c["result"] for c in candidates}):
                result = next(value for value in ("Goal", "Saved", "Off T") if value not in {c["result"] for c in candidates})
            else:
                result = rng.choices(["Goal", "Saved", "Off T"], weights=[.11, .40, .49])[0]
            shot_x = clamp(carry_end[0], 85, 113)
            shot_y = clamp(carry_end[1], 19, 61)
            shot_pos = [shot_x, shot_y]
            end = ([120, rng.uniform(37, 43), rng.uniform(.2, 2)] if result == "Goal"
                   else [rng.uniform(115, 119), rng.uniform(36, 44), rng.uniform(.4, 2)] if result == "Saved"
                   else [120, rng.choice([rng.uniform(25, 35), rng.uniform(45, 57)]), rng.uniform(.2, 2)])
            end = [round(v, 2) for v in end]
            freeze = [
                {"location": [117, 40], "player": keeper, "position": {"name": "Goalkeeper"}, "teammate": False},
                {"location": [clamp(shot_x + 1.5, 1, 119), clamp(shot_y + 1.8, 1, 79)],
                 "player": defender, "position": {"name": "Center Back"}, "teammate": False},
                {"location": pass_event["location"], "player": passer,
                 "position": {"name": "Center Midfield"}, "teammate": True},
            ]
            before = score.copy()
            shot = emit("Shot", clock + 5, team, receiver, shot_pos,
                        {"under_pressure": True, "shot": {
                            "end_location": end, "key_pass_id": pass_event["id"],
                            "body_part": {"name": "Right Foot"}, "technique": {"name": "Normal"},
                            "type": {"name": "Open Play"}, "outcome": {"name": result},
                            "freeze_frame": freeze}}, end)
            chain.append(shot)
            if result == "Saved":
                save = emit("Goal Keeper", clock + 6, other_team, keeper, end[:2],
                            {"goalkeeper": {"type": {"name": "Shot Saved"},
                                            "outcome": {"name": "Success"}}})
                save["possession_team"] = team
                save["possession"] = possession
                chain.append(save)
            if result == "Goal":
                score[team_i] += 1
            candidates.append({"chain": chain[:], "shot": shot, "before": before,
                               "after": score.copy(), "result": result})
        for i, item in enumerate(chain):
            item["related_events"] = [other["id"] for j, other in enumerate(chain) if abs(i-j) == 1]
        clock += rng.randint(16, 27)

    # A full-time marker makes the simulated 90-minute coverage explicit.
    possession += 1
    emit("Full Time", 5400, teams[0], by_team[teams[0]["id"]][0]["player"], [60, 40])
    clips = []
    for result, target_minute in (("Goal", 18), ("Saved", 48), ("Off T", 75)):
        choices = [c for c in candidates if c["result"] == result]
        chosen = min(choices, key=lambda c: abs(c["shot"]["minute"] - target_minute))
        chain, shot = chosen["chain"], chosen["shot"]
        keeper = next(p["player"] for p in shot["shot"]["freeze_frame"] if p["position"]["name"] == "Goalkeeper")
        clips.append({
            "id": f"seed-{seed}-{result.lower().replace(' ', '-')}",
            "match_id": match["match_id"], "synthetic": True,
            "event_ids": [e["id"] for e in chain], "trigger_event_id": shot["id"],
            "score_before": chosen["before"], "score_after": chosen["after"],
            "available_pov_player_ids": [shot["player"]["id"], keeper["id"]],
            "generation_constraints": {"outcome": result, "attacking_direction": "positive_x",
                                       "target_duration_seconds": 6,
                                       "must_preserve": ["shot outcome", "player identities", "selected first-person viewpoint"],
                                       "creative_details": ["head movement", "crowd ambience", "lighting"]},
        })
    clips.sort(key=lambda c: next(e["index"] for e in events if e["id"] == c["trigger_event_id"]))
    validate(match, events, clips)
    return match, events, clips


def validate(match, events, clips):
    assert events[-1]["minute"] == 90
    assert len({e["id"] for e in events}) == len(events)
    assert [(e["minute"], e["second"]) for e in events] == sorted((e["minute"], e["second"]) for e in events)
    by_id = {e["id"]: e for e in events}
    goals = [sum(e["team"]["id"] == match[f"{side}_team"]["id"] and
                 e.get("shot", {}).get("outcome", {}).get("name") == "Goal" for e in events)
             for side in ("home", "away")]
    for event in events:
        assert all(ref in by_id for ref in event["related_events"])
        assert len(event["tracking"]["start"]) == len(event["tracking"]["end"]) == 22
        assert all(0 <= p["location"][0] <= 120 and 0 <= p["location"][1] <= 80
                   for p in event["tracking"]["start"] + event["tracking"]["end"])
    for clip in clips:
        shot = by_id[clip["trigger_event_id"]]
        outcome = shot["shot"]["outcome"]["name"]
        scorer = 0 if shot["team"]["id"] == match["home_team"]["id"] else 1
        assert clip["score_after"][scorer] == clip["score_before"][scorer] + (outcome == "Goal")
        assert by_id[shot["shot"]["key_pass_id"]]["type"]["name"] == "Pass"
    return goals


def save(seed, out=None):
    out = Path(out) if out else ROOT / "data" / "matches" / f"seed-{seed}"
    match, events, clips = generate(seed)
    out.mkdir(parents=True, exist_ok=True)
    for name, value in (("match.json", match), ("events.json", events), ("clips.json", clips),
                        ("commentary.json", build_tracks(match, events))):
        (out / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return out, match, events, clips


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    folder, match, events, clips = save(args.seed, args.out)
    goals = validate(match, events, clips)
    print(f"{folder}: {len(events)} events, {sum(e['type']['name']=='Shot' for e in events)} shots, "
          f"{goals[0]}:{goals[1]}, {len(clips)} featured highlights")
