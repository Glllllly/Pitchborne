"""Deterministic 22-player keyframes, authored for the three highlight clips."""

import math

from scripts.player_names import PLAYER_NAMES


def lerp(a, b, weight):
    return [round(x + (y - x) * weight, 4) for x, y in zip(a, b)]


def add_tracking(match, events, clips):
    # Independent fictional 4-3-3 layout. Coordinates use the existing 120x80 pitch.
    slots = [
        ("GK", [8, 40]), ("LB", [40, 10]), ("CB", [35, 29]),
        ("CB", [35, 51]), ("RB", [40, 70]), ("DM", [58, 40]),
        ("CM", [72, 22]), ("CM", [72, 58]), ("LW", [91, 12]),
        ("ST", [102, 40]), ("RW", [91, 68]),
    ]
    existing = {p["player"]["id"]: p for p in match["players"]}
    players = []
    bases = {}
    for team in (9001, 9002):
        for i, (position, base) in enumerate(slots):
            special = {(9001, 9): 9101, (9001, 6): 9102, (9002, 0): 9201, (9002, 2): 9202}
            pid = special.get((team, i), team * 10 + i)
            entry = dict(existing.get(pid, {
                "player": {"id": pid, "name": PLAYER_NAMES[team][i + 1]},
                "team_id": team, "role": "goalkeeper" if i == 0 else "outfield",
            }))
            entry.update({"shirt_number": i + 1, "position": position})
            players.append(entry)
            bases[pid] = base if team == 9001 else [120 - base[0] * .48, 80 - base[1]]
    match["players"] = players
    match["tracking"] = {
        "type": "synthetic_keyframes",
        "formation": "4-3-3",
        "physical_pitch_metres": [105, 68],
        "interpolation": "linear between each event's start/end frame",
        "limitations": "Authored movements, not physical simulation; no collision or offside solver.",
    }
    by_id = {e["id"]: e for e in events}
    for clip in clips:
        chain = [by_id[eid] for eid in clip["event_ids"]]
        shot = by_id[clip["trigger_event_id"]]
        target = {pid: list(pos) for pid, pos in bases.items()}
        target[9101] = shot["location"]
        for point in shot["shot"]["freeze_frame"]:
            target[point["player"]["id"]] = point["location"]
        start = {}
        for entry in players:
            pid = entry["player"]["id"]
            tx, ty = target[pid]
            # Support runs forward; defensive block retreats with the attack.
            dx = 0.8 if entry["role"] == "goalkeeper" else 2.5 + (entry["shirt_number"] % 3)
            start[pid] = [max(1, tx - dx), min(78, max(2, ty + (entry["shirt_number"] % 3 - 1) * 1.2))]
        start[9102] = chain[0]["location"]
        receipt = chain[0]["pass"]["end_location"]
        start[9101] = [receipt[0] - 2, receipt[1] + 1]
        durations = [2, .4, 2, .8] + ([.5] if len(chain) == 5 else [])
        elapsed = 0

        def frame(t):
            weight = min(t / 4.4, 1)
            positions = {pid: lerp(start[pid], target[pid], weight) for pid in target}
            if t <= 2:
                positions[9101] = lerp(start[9101], receipt, t / 2)
            elif t <= 2.4:
                positions[9101] = list(receipt)
            else:
                positions[9101] = lerp(receipt, shot["location"], min((t - 2.4) / 2, 1))
            if t > 4.4 and shot["shot"]["outcome"]["name"] == "Saved":
                positions[9201] = lerp(target[9201], shot["shot"]["end_location"][:2], min((t - 4.4) / .8, 1))
            return [{"player_id": p["player"]["id"], "team_id": p["team_id"],
                     "location": positions[p["player"]["id"]]} for p in players]

        for event, duration in zip(chain, durations):
            start_frame, end_frame = frame(elapsed), frame(elapsed + duration)
            ball_start = event["location"]
            ball_end = event.get("pass", event.get("carry", event.get("shot", {}))).get("end_location", ball_start)
            event["tracking"] = {
                "synthetic": True, "clip_time_seconds": round(elapsed, 2),
                "duration_seconds": duration, "start": start_frame, "end": end_frame,
                "ball_start": ball_start[:2], "ball_end": ball_end[:2],
            }
            for a, b in zip(start_frame, end_frame):
                dx = (b["location"][0] - a["location"][0]) * 105 / 120
                dy = (b["location"][1] - a["location"][1]) * 68 / 80
                assert math.hypot(dx, dy) / duration <= 10, "Unrealistic player speed"
                assert 0 <= b["location"][0] <= 120 and 0 <= b["location"][1] <= 80
            elapsed += duration
        clip["tracking_duration_seconds"] = round(elapsed, 2)
