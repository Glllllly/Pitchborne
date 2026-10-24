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


if __name__ == "__main__":
    unittest.main()
