import tempfile
import unittest
from pathlib import Path

from scripts.generate_match import generate
from workflow.pipeline import run


class FullMatchTests(unittest.TestCase):
    def test_seed_is_reproducible_and_covers_full_match(self):
        match, events, clips = generate(7)
        other_match, other_events, _ = generate(7)
        self.assertEqual(match, other_match)
        self.assertEqual(events, other_events)
        first_pass = next(event for event in events if event["type"]["name"] == "Pass")
        other_first_pass = next(event for event in generate(8)[1] if event["type"]["name"] == "Pass")
        self.assertNotEqual(first_pass["location"], other_first_pass["location"])
        self.assertGreater(len(events), 500)
        self.assertEqual(events[-1]["minute"], 90)
        self.assertEqual(len(match["players"]), 22)
        self.assertEqual(len({entry["player"]["name"] for entry in match["players"]}), 22)
        self.assertFalse(any(" Player " in entry["player"]["name"] for entry in match["players"]))
        roster = {entry["player"]["id"]: entry["player"]["name"] for entry in match["players"]}
        self.assertTrue(all(event["player"]["name"] == roster[event["player"]["id"]] for event in events))
        self.assertEqual({c["generation_constraints"]["outcome"] for c in clips},
                         {"Goal", "Saved"})
        self.assertEqual(len(clips), sum(event["type"]["name"] == "Shot" and
                                         event["shot"]["outcome"]["name"] in ("Goal", "Saved")
                                         for event in events))
        self.assertEqual({clip["trigger_event_id"] for clip in clips},
                         {event["id"] for event in events if event["type"]["name"] == "Shot" and
                          event["shot"]["outcome"]["name"] in ("Goal", "Saved")})
        self.assertTrue(any(e["team"]["id"] == match["away_team"]["id"] for e in events if e["type"]["name"] == "Shot"))

    def test_generated_highlights_use_existing_pipeline(self):
        match, events, clips = generate(42)
        with tempfile.TemporaryDirectory() as folder:
            data = Path(folder)
            import json
            for name, value in (("match.json", match), ("events.json", events), ("clips.json", clips)):
                (data / name).write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
            for clip in clips:
                result = run(clip["id"], "striker", "zh", data, data / "output", audience="neutral")
                self.assertEqual(result["validation.json"]["status"], "passed")

    def test_spanish_and_french_highlight_commentary(self):
        match, events, clips = generate(7)
        with tempfile.TemporaryDirectory() as folder:
            data = Path(folder)
            import json
            for name, value in (("match.json", match), ("events.json", events), ("clips.json", clips)):
                (data / name).write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
            for language in ("es", "fr"):
                result = run(clips[0]["id"], "striker", language, data, data / language,
                             audience="neutral")
                self.assertEqual(result["validation.json"]["status"], "passed")
                self.assertEqual(result["commentary.json"]["language"], language)

    def test_tracking_uses_team_shape_and_fixed_goal_sides(self):
        match, events, _ = generate(7)
        event = next(e for e in events if e["team"]["id"] == match["away_team"]["id"])
        positions = {point["player_id"]: point["location"]
                     for point in event["tracking"]["start"]}
        by_team = {side: {p["shirt_number"]: positions[p["player"]["id"]]
                          for p in match["players"] if p["team_id"] == match[f"{side}_team"]["id"]}
                   for side in ("home", "away")}
        self.assertLess(by_team["away"][1][0], 15)
        self.assertGreater(by_team["home"][1][0], 105)
        for side in ("home", "away"):
            team = {number: location if side == "away" else [120 - location[0], 80 - location[1]]
                    for number, location in by_team[side].items()}
            self.assertLess(team[2][0], team[7][0])
            self.assertLess(team[7][0], team[9][0])
            self.assertLess(team[2][1], team[5][1])

    def test_pass_receiver_moves_into_the_ball_arrival_point(self):
        _, events, _ = generate(7)
        event = next(item for item in events if item["type"]["name"] == "Pass")
        receiver_id = event["pass"]["recipient"]["id"]
        start = next(point["location"] for point in event["tracking"]["start"]
                     if point["player_id"] == receiver_id)
        end = next(point["location"] for point in event["tracking"]["end"]
                   if point["player_id"] == receiver_id)
        self.assertNotEqual(start, end)
        self.assertEqual(end, event["pass"]["end_location"])

    def test_saved_shots_keep_the_goalkeeper_at_the_defending_goal(self):
        match, events, _ = generate(7)
        home_id = match["home_team"]["id"]
        for shot, save in zip(events, events[1:]):
            if shot["type"]["name"] != "Shot" or shot["shot"]["outcome"]["name"] != "Saved":
                continue
            self.assertEqual(save["type"]["name"], "Goal Keeper")
            self.assertEqual(save["location"], [round(120 - shot["shot"]["end_location"][0], 2),
                                                round(80 - shot["shot"]["end_location"][1], 2)])
            self.assertLess(save["location"][0], 10)
            display_x = save["location"][0] if save["team"]["id"] == home_id else 120 - save["location"][0]
            if save["team"]["id"] == home_id:
                self.assertLess(display_x, 10)
            else:
                self.assertGreater(display_x, 110)

    def test_every_goal_is_followed_by_the_conceding_team_kicking_off(self):
        match, events, _ = generate(7)
        goal_indices = [i for i, event in enumerate(events)
                        if event["type"]["name"] == "Shot" and event["shot"]["outcome"]["name"] == "Goal"]
        self.assertTrue(goal_indices)
        for index in goal_indices:
            goal, restart = events[index:index + 2]
            self.assertEqual(restart["type"]["name"], "Kick Off")
            self.assertNotEqual(restart["team"]["id"], goal["team"]["id"])
            self.assertEqual(restart["location"], [60, 40])
            self.assertEqual(restart["tracking"]["ball_start"], [60, 40])
            self.assertEqual(restart["tracking"]["ball_end"], [57, 40])
            self.assertEqual(restart["kick_off"]["after_goal_id"], goal["id"])
            for frame in ("start", "end"):
                for point in restart["tracking"][frame]:
                    x, y = point["location"]
                    if point["player_id"] == restart["player"]["id"]:
                        self.assertEqual(point["location"], [60, 40])
                    elif point["team_id"] == restart["team"]["id"]:
                        self.assertLess(x, 60)
                    else:
                        self.assertGreater(x, 60)
                        self.assertGreaterEqual(((x - 60) ** 2 + (y - 40) ** 2) ** .5, 9)
            self.assertGreater(restart["minute"] * 60 + restart["second"],
                               goal["minute"] * 60 + goal["second"])
            following = events[index + 2]
            if following["team"]["id"] != restart["team"]["id"]:
                self.assertEqual(following["type"]["name"], "Interception")
                self.assertEqual(following["play_pattern"]["name"], "After Kick Off")

    def test_match_opens_with_both_teams_in_their_own_halves(self):
        for seed in (7, 8):
            _, events, _ = generate(seed)
            opening, first_pass = events[:2]
            self.assertEqual(opening["type"]["name"], "Kick Off")
            self.assertTrue(opening["kick_off"]["opening"])
            self.assertEqual((opening["minute"], opening["second"]), (0, 0))
            self.assertEqual(first_pass["type"]["name"], "Pass")
            self.assertEqual(first_pass["team"]["id"], opening["team"]["id"])
            self.assertGreater(first_pass["minute"] * 60 + first_pass["second"], 0)
            self.assertEqual(opening["tracking"]["ball_start"], [60, 40])
            self.assertEqual(opening["tracking"]["ball_end"], [57, 40])
            for point in opening["tracking"]["start"]:
                x = point["location"][0]
                if point["player_id"] == opening["player"]["id"]:
                    self.assertEqual(point["location"], [60, 40])
                elif point["team_id"] == opening["team"]["id"]:
                    self.assertLess(x, 60)
                else:
                    self.assertGreater(x, 60)

    def test_away_team_restart_stays_in_its_own_display_half(self):
        match, events, _ = generate(8)
        away_id = match["away_team"]["id"]
        restarts = [event for event in events if event["type"]["name"] == "Kick Off"
                    and event["team"]["id"] == away_id]
        self.assertTrue(restarts)
        for restart in restarts:
            for point in restart["tracking"]["start"]:
                display_x = 120 - point["location"][0]
                if point["player_id"] == restart["player"]["id"]:
                    self.assertEqual(display_x, 60)
                elif point["team_id"] == away_id:
                    self.assertGreater(display_x, 60)
                else:
                    self.assertLess(display_x, 60)


if __name__ == "__main__":
    unittest.main()
