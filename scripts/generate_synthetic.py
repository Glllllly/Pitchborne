"""Generate fictional, StatsBomb-inspired event clips using only stdlib."""

import json
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "synthetic"


def ident(value):
    return str(uuid5(NAMESPACE_URL, f"pilot-synthetic-v1/{value}"))


def write(name, value):
    (OUT / name).write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def generate():
    OUT.mkdir(parents=True, exist_ok=True)
    home = {"id": 9001, "name": "Harbor Comets"}
    away = {"id": 9002, "name": "Mountain Lanterns"}
    striker = {"id": 9101, "name": "Arin Vale"}
    passer = {"id": 9102, "name": "Niko Reed"}
    keeper = {"id": 9201, "name": "Toma Finch"}
    defender = {"id": 9202, "name": "Lio Moss"}
    specs = [
        ("goal", 12, "Goal", [108, 35], [120, 43, 1.2], [117, 38]),
        ("off_target", 34, "Off T", [103, 47], [120, 46, 1.0], [117, 42]),
        ("saved", 67, "Saved", [109, 42], [118, 41, 0.8], [118, 40]),
    ]
    events, clips = [], []
    score = [0, 0]
    for possession, (key, minute, result, location, end, keeper_pos) in enumerate(specs, 1):
        period = 1 if minute < 45 else 2
        local_minute = minute if period == 1 else minute - 45
        before = score.copy()
        sequence = []

        def event(kind, second, player, position, duration):
            value = {
                "id": ident(f"{key}/{kind}"),
                "index": len(events) + len(sequence) + 1,
                "period": period,
                "timestamp": f"00:{local_minute:02d}:{second:02d}.000",
                "minute": minute,
                "second": second,
                "type": {"name": kind},
                "possession": possession,
                "possession_team": home,
                "team": away if kind == "Goal Keeper" else home,
                "player": player,
                "location": position,
                "duration": duration,
                "play_pattern": {"name": "Regular Play"},
                "synthetic": True,
            }
            sequence.append(value)
            return value

        pass_event = event("Pass", 10, passer, [91, 32], 1.5)
        pass_event["pass"] = {
            "recipient": striker,
            "end_location": [location[0] - 3, location[1]],
            "height": {"name": "Ground Pass"},
            "body_part": {"name": "Right Foot"},
            "outcome": {"name": "Complete"},
        }
        receipt = event("Ball Receipt*", 12, striker, pass_event["pass"]["end_location"], 0)
        carry = event("Carry", 12, striker, receipt["location"], 2)
        carry["carry"] = {"end_location": location}
        shot = event("Shot", 14, striker, location, 0.6)
        shot["under_pressure"] = True
        shot["shot"] = {
            "end_location": end,
            "key_pass_id": pass_event["id"],
            "body_part": {"name": "Right Foot"},
            "technique": {"name": "Normal"},
            "type": {"name": "Open Play"},
            "outcome": {"name": result},
            "freeze_frame": [
                {"location": keeper_pos, "player": keeper,
                 "position": {"name": "Goalkeeper"}, "teammate": False},
                {"location": [location[0] - 1.5, location[1] - 1], "player": defender,
                 "position": {"name": "Center Back"}, "teammate": False},
                {"location": [96, 33], "player": passer,
                 "position": {"name": "Center Midfield"}, "teammate": True},
            ],
        }
        if result == "Saved":
            save = event("Goal Keeper", 15, keeper, end[:2], 0.4)
            save["goalkeeper"] = {
                "type": {"name": "Shot Saved"},
                "outcome": {"name": "Success"},
            }
        for i, item in enumerate(sequence):
            item["related_events"] = [
                other["id"] for j, other in enumerate(sequence) if abs(i - j) == 1
            ]
        if result == "Goal":
            score[0] += 1
        events.extend(sequence)
        clips.append({
            "id": key,
            "match_id": 990001,
            "synthetic": True,
            "event_ids": [item["id"] for item in sequence],
            "trigger_event_id": shot["id"],
            "score_before": before,
            "score_after": score.copy(),
            "available_pov_player_ids": [striker["id"], keeper["id"]],
            "generation_constraints": {
                "outcome": result,
                "attacking_direction": "positive_x",
                "target_duration_seconds": 6,
                "must_preserve": [
                    "shot outcome", "right-footed shot", "player identities",
                    "relative positions at shot time", "selected first-person viewpoint",
                ],
                "creative_details": [
                    "head movement", "crowd ambience", "breathing", "lighting",
                ],
            },
        })
    match = {
        "match_id": 990001,
        "schema": "pilot.statsbomb-inspired.v1",
        "synthetic": True,
        "provenance": "Authored fictional scenarios; no real match records copied.",
        "home_team": home,
        "away_team": away,
        "coverage": "Three isolated highlight clips, not a complete match event stream.",
        "coordinate_system": {
            "length": 120, "width": 80,
            "xy_units": "normalized pitch units, not metres",
            "z_units": "metres",
            "attacking_direction": "positive_x for all supplied clips",
            "goal_line_x": 120,
            "goal_mouth_y": [36, 44],
            "goal_height_metres": 2.44,
        },
        "clock": "minute is match elapsed minute; timestamp is elapsed within period",
        "players": [
            {"player": striker, "team_id": 9001, "role": "striker"},
            {"player": passer, "team_id": 9001, "role": "midfielder"},
            {"player": keeper, "team_id": 9002, "role": "goalkeeper"},
            {"player": defender, "team_id": 9002, "role": "defender"},
        ],
    }
    validate(match, events, clips)
    write("match.json", match)
    write("events.json", events)
    write("clips.json", clips)
    print(f"Validated and generated {len(events)} events across {len(clips)} clips: {OUT}")


def validate(match, events, clips):
    by_id = {event["id"]: event for event in events}
    assert len(by_id) == len(events), "Duplicate event IDs"
    players = {item["player"]["id"] for item in match["players"]}
    for event in events:
        assert event["player"]["id"] in players
        assert all(ref in by_id for ref in event["related_events"])
        x, y = event["location"]
        assert 0 <= x <= 120 and 0 <= y <= 80
    for clip in clips:
        chain = [by_id[ref] for ref in clip["event_ids"]]
        times = [event["minute"] * 60 + event["second"] for event in chain]
        assert times == sorted(times), "Events must be chronological"
        shot = by_id[clip["trigger_event_id"]]
        outcome = shot["shot"]["outcome"]["name"]
        assert by_id[shot["shot"]["key_pass_id"]]["type"]["name"] == "Pass"
        assert chain[2]["carry"]["end_location"] == shot["location"]
        x, y, z = shot["shot"]["end_location"]
        if outcome == "Goal":
            assert x == 120 and 36 < y < 44 and 0 < z < 2.44
        elif outcome == "Off T":
            assert x == 120 and (y < 36 or y > 44 or z > 2.44)
        elif outcome == "Saved":
            assert x < 120 and chain[-1]["type"]["name"] == "Goal Keeper"
        assert clip["score_after"] == [
            clip["score_before"][0] + int(outcome == "Goal"), clip["score_before"][1]
        ]


if __name__ == "__main__":
    generate()
