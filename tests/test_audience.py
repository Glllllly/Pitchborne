import copy
import tempfile
import unittest
from pathlib import Path

from workflow.pipeline import ROOT, audience_profile, load_context, run


class AudienceTests(unittest.TestCase):
    def test_team_mapping_reverses_when_away_shoots(self):
        context = load_context(ROOT / "data/synthetic", "goal")
        for attacking_side in ("home", "away"):
            altered = copy.deepcopy(context)
            altered["shot"]["team"] = altered["match"][f"{attacking_side}_team"]
            for supported in ("home", "away"):
                profile = audience_profile(altered, supported, "striker")
                is_attack = attacking_side == supported
                self.assertEqual(profile["pov"], "striker" if is_attack else "goalkeeper")
                self.assertEqual(profile["emotion"], "joyful" if is_attack else "disappointed")

    def test_all_outcomes_languages_and_audiences(self):
        with tempfile.TemporaryDirectory() as folder:
            for clip in ("goal", "saved", "off_target"):
                for language in ("zh", "en"):
                    for audience in ("neutral", "home", "away"):
                        result = run(clip, "goalkeeper", language, ROOT / "data/synthetic",
                                     Path(folder), audience=audience)
                        viewer = result["scene.json"]["viewer"]
                        expected = "striker" if audience == "home" else "goalkeeper"
                        self.assertEqual(result["scene.json"]["pov"], expected)
                        self.assertEqual(viewer["autoplay"], audience != "neutral")
                        self.assertEqual(result["commentary.json"]["emotion"], viewer["emotion"])
                        self.assertEqual(result["video_request.json"]["outcome"],
                                         result["commentary.json"]["outcome"])
                        self.assertEqual(result["video_job.json"]["status"], "not_submitted")
                        self.assertEqual(result["validation.json"]["status"], "passed")

    def test_invalid_audience_rejected(self):
        context = load_context(ROOT / "data/synthetic", "saved")
        with self.assertRaises(ValueError):
            audience_profile(context, "invalid", "striker")


if __name__ == "__main__":
    unittest.main()
