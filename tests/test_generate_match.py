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
        self.assertNotEqual(events[0]["location"], generate(8)[1][0]["location"])
        self.assertGreater(len(events), 500)
        self.assertEqual(events[-1]["minute"], 90)
        self.assertEqual(len(match["players"]), 22)
        self.assertEqual({c["generation_constraints"]["outcome"] for c in clips},
                         {"Goal", "Saved", "Off T"})
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


if __name__ == "__main__":
    unittest.main()
