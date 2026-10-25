"""Seeded, fictional 90-minute event stream for the local replay app."""

import argparse
import copy
import json
import math
import random
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from workflow.pipeline import ROOT
from workflow.match_commentary import build_tracks, build_english_tracks
from workflow.commentary_romance import build_romance_tracks
from workflow.kinematics import annotate_ball_event
from scripts.player_names import PLAYER_NAMES

SAMPLE = ROOT / "data" / "synthetic" / "match.json"
FORMATION = {
    1: (6, 40), 2: (30, 11), 3: (27, 31), 4: (27, 49), 5: (30, 69),
    6: (46, 40), 7: (57, 27), 8: (57, 53), 9: (76, 12),
    10: (82, 40), 11: (76, 68),
}


def clamp(value, low, high):
    return round(max(low, min(high, value)), 2)


def generate(seed):
    if not isinstance(seed, int) or not 0 <= seed <= 1_000_000_000:
        raise ValueError("seed must be an integer between 0 and 1,000,000,000")
    rng = random.Random(seed)
    match = copy.deepcopy(json.loads(SAMPLE.read_text(encoding="utf-8")))
    match["match_id"] = 1_000_000_000 + seed
    match["seed"] = seed
    match["generator_version"] = 18
    match["coverage"] = "Synthetic on-ball event stream across 90 simulated minutes; not continuous optical tracking."
    match["provenance"] = "Generated from this repository's seeded fictional simulator; no real match records copied."
    match["coordinate_system"]["attacking_direction"] = "positive_x for all supplied clips"
    match["tracking"]["type"] = "synthetic_event_keyframes"
    match["tracking"]["limitations"] = "Role-based 4-3-3 event snapshots; no continuous optical tracking, collision or offside model."
    match["coordinate_system"]["display_orientation"] = "home attacks right; away attacks left; away event coordinates rotate 180 degrees for display"
    roster = match["players"]
    for entry in roster:
        entry["player"]["name"] = PLAYER_NAMES[entry["team_id"]][entry["shirt_number"]]
    teams = [match["home_team"], match["away_team"]]
    by_team = {team["id"]: [p for p in roster if p["team_id"] == team["id"]] for team in teams}
    events, candidates = [], []
    score = [0, 0]
    possession = 0
    forced_team_i = None
    restart_team_id = None

    def event_id(index):
        return str(uuid5(NAMESPACE_URL, f"pilot-full-match-v1/{seed}/{index}"))

    def tracking(event, target):
        own = event["team"]["id"]
        active = event["player"]["id"]
        receiver = (event.get("pass", {}).get("recipient", {}).get("id") or
                    event.get("kick_off", {}).get("recipient", {}).get("id"))
        x, y = event["location"]
        # Locations are expressed in the acting team's attacking direction.
        # Build each side in its own 4-3-3, then rotate the defending side.
        anchor = (x, y)
        points = []
        for entry in roster:
            pid = entry["player"]["id"]
            same = entry["team_id"] == own
            shirt = entry["shirt_number"]
            base_x, base_y = FORMATION[shirt]
            ball_x, ball_y = anchor if same else (120 - x, 80 - y)
            if event["type"]["name"] == "Kick Off":
                # Before the restart every outfield player stays in their own
                # half; opponents also remain outside the centre circle.
                own_x = clamp(base_x * .65 + 3, 5, 58 if same else 50)
                own_y = clamp(base_y + math.sin(pid * .17) * .8, 5, 75)
            elif shirt == 1:
                own_x = clamp(6 + max(0, ball_x - 55) * .10, 3, 13)
                own_y = clamp(40 + (ball_y - 40) * .08, 36, 44)
            else:
                shift = clamp((ball_x - 60) * .38, -17, 17)
                own_x = clamp(base_x + shift, 11, 110)
                own_y = clamp(base_y + (ball_y - 40) * .12, 6, 74)
                # Small stable offsets stop each line looking ruler-straight.
                own_x = clamp(own_x + math.sin(pid * .17 + event["index"] * .11) * 1.3, 10, 110)
                own_y = clamp(own_y + math.cos(pid * .13 + event["index"] * .09) * 1.1, 5, 75)
            point = [own_x, own_y] if same else [clamp(120 - own_x, 2, 118), clamp(80 - own_y, 2, 78)]
            if pid == active:
                point = list(event["location"])
            elif pid == receiver:
                point = [clamp(target[0] - 2.2, 1, 119),
                         clamp(target[1] + (1.4 if shirt % 2 else -1.4), 1, 79)]
            end = list(point)
            if pid == active and event["type"]["name"] == "Carry":
                end = list(target[:2])
            elif pid == receiver:
                end = list(target[:2])
            elif pid != receiver and pid != active and entry["position"] != "GK":
                end = [clamp(point[0] + (.55 if same else -.35), 1, 119),
                       clamp(point[1] + (target[1] - y) * .08, 1, 79)]
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
        annotate_ball_event(match, item, seed)
        events.append(item)
        return item

    team_i = rng.randrange(2)
    opening_team = teams[team_i]
    opening_squad = by_team[opening_team["id"]]
    opening_kicker = next(entry["player"] for entry in opening_squad if entry["shirt_number"] == 10)
    opening_receiver = next(entry["player"] for entry in opening_squad if entry["shirt_number"] == 6)
    possession = 1
    emit("Kick Off", 0, opening_team, opening_kicker, [60, 40],
         {"kick_off": {"opening": True, "recipient": opening_receiver,
                       "end_location": [57, 40]}}, [57, 40])
    clock = 1
    first_play = True
    while clock < 5370:
        if first_play:
            first_play = False
        else:
            possession += 1
            team_i = (forced_team_i if forced_team_i is not None else
                      1 - team_i if rng.random() < .67 else team_i)
        forced_team_i = None
        team = teams[team_i]
        other_team = teams[1 - team_i]
        previous_restart_team_id = restart_team_id
        restart_team_id = None
        squad = [p["player"] for p in by_team[team["id"]] if p["position"] != "GK"]
        opponents = [p["player"] for p in by_team[other_team["id"]] if p["position"] != "GK"]
        if previous_restart_team_id is not None and team["id"] != previous_restart_team_id:
            winner = next(entry["player"] for entry in by_team[team["id"]]
                          if entry["shirt_number"] == 6)
            emit("Interception", clock - 3, team, winner, [60, 40],
                 {"play_pattern": {"name": "After Kick Off"}})
        x, y = rng.uniform(27, 69), rng.uniform(12, 68)
        passer_entry = min((p for p in by_team[team["id"]] if p["position"] != "GK"),
                           key=lambda p: abs(FORMATION[p["shirt_number"]][0] - x) + rng.uniform(0, 18))
        passer = passer_entry["player"]
        receiver_entry = min((p for p in by_team[team["id"]]
                              if p["position"] != "GK" and p["player"]["id"] != passer["id"]),
                             key=lambda p: (abs(FORMATION[p["shirt_number"]][0] - (x + 8))
                                            + abs(FORMATION[p["shirt_number"]][1] - y) * .35
                                            + rng.uniform(0, 12)))
        receiver = receiver_entry["player"]
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
        restart = None
        if shot_chance and clock + 8 < 5400:
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
                # The shot endpoint is in the shooter's attacking direction;
                # the keeper event uses the defending team's direction.
                save_location = [round(120 - end[0], 2), round(80 - end[1], 2)]
                save = emit("Goal Keeper", clock + 6, other_team, keeper, save_location,
                            {"goalkeeper": {"type": {"name": "Shot Saved"},
                                            "outcome": {"name": "Success"}}})
                save["possession_team"] = team
                save["possession"] = possession
                chain.append(save)
            if result == "Goal":
                score[team_i] += 1
                possession += 1
                restarting = by_team[other_team["id"]]
                kicker = next(entry["player"] for entry in restarting if entry["shirt_number"] == 10)
                recipient = next(entry["player"] for entry in restarting if entry["shirt_number"] == 6)
                restart = emit("Kick Off", clock + 8, other_team, kicker, [60, 40],
                               {"kick_off": {"after_goal_id": shot["id"], "recipient": recipient,
                                             "end_location": [57, 40]}}, [57, 40])
                restart_team_id = other_team["id"]
            candidates.append({"chain": chain[:], "shot": shot, "before": before,
                               "after": score.copy(), "result": result})
        for i, item in enumerate(chain):
            item["related_events"] = [other["id"] for j, other in enumerate(chain) if abs(i-j) == 1]
        if restart:
            shot["related_events"].append(restart["id"])
            restart["related_events"] = [shot["id"]]
        clock += rng.randint(16, 27)

    # A full-time marker makes the simulated 90-minute coverage explicit.
    possession += 1
    emit("Full Time", 5400, teams[0], by_team[teams[0]["id"]][0]["player"], [60, 40])
    clips = []
    for chosen in candidates:
        result = chosen["result"]
        if result not in ("Goal", "Saved"):
            continue
        chain, shot = chosen["chain"], chosen["shot"]
        keeper = next(p["player"] for p in shot["shot"]["freeze_frame"] if p["position"]["name"] == "Goalkeeper")
        clips.append({
            "id": f"seed-{seed}-shot-{shot['index']}",
            "match_id": match["match_id"], "synthetic": True,
            "event_ids": [e["id"] for e in chain], "trigger_event_id": shot["id"],
            "score_before": chosen["before"], "score_after": chosen["after"],
            "available_pov_player_ids": [shot["player"]["id"], keeper["id"]],
            "generation_constraints": {"outcome": result, "attacking_direction": "positive_x",
                                       "target_duration_seconds": 6,
                                       "must_preserve": ["shot outcome", "player identities", "selected first-person viewpoint"],
                                       "creative_details": ["head movement", "crowd ambience", "lighting"]},
        })
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
                        ("commentary.json", build_tracks(match, events)),
                        ("commentary_en.json", build_english_tracks(match, events)),
                        ("commentary_es.json", build_romance_tracks(match, events, "es")),
                        ("commentary_fr.json", build_romance_tracks(match, events, "fr"))):
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
