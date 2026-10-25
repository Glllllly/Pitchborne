"""Reproducible, explicitly synthetic ball-flight and pass-difficulty estimates."""

import math
import random


def pitch_distance(match, start, end):
    coordinates = match["coordinate_system"]
    physical = match["tracking"]["physical_pitch_metres"]
    return math.hypot((end[0] - start[0]) * physical[0] / coordinates["length"],
                      (end[1] - start[1]) * physical[1] / coordinates["width"])


def annotate_ball_event(match, event, seed):
    kind = event["type"]["name"]
    if kind not in ("Pass", "Shot"):
        return
    start = event["location"]
    end = event["pass"]["end_location"] if kind == "Pass" else event["shot"]["end_location"]
    distance = pitch_distance(match, start, end)
    rng = random.Random(f"{seed}:kinematics:{event['index']}")
    speed = ((32 + min(distance, 42) * .55 + rng.uniform(-6, 6)) if kind == "Pass"
             else (74 + min(distance, 35) * .7 + rng.uniform(-8, 8)))
    speed = round(max(18, speed), 1)
    metrics = {
        "source": "synthetic_kinematics_v1",
        "ball_distance_m": round(distance, 1),
        "ball_flight_seconds": round(distance * 3.6 / speed, 3),
        "ball_speed_kmh": speed,
    }
    if kind == "Pass":
        progress = (end[0] - start[0]) * match["tracking"]["physical_pitch_metres"][0] / match["coordinate_system"]["length"]
        defenders = [point for point in event["tracking"]["start"]
                     if point["team_id"] != event["team"]["id"]]
        nearest = min((pitch_distance(match, point["location"], end) for point in defenders), default=20)
        rating = round(min(100, max(0, 18 + distance * 1.2 + max(0, progress) * .8
                                     + max(0, 12 - nearest) * 3.5)))
        metrics.update(pass_difficulty=rating,
                       pass_difficulty_level="high" if rating >= 60 else "medium" if rating >= 30 else "low",
                       nearest_defender_to_target_m=round(nearest, 1))
    event["kinematics"] = metrics
