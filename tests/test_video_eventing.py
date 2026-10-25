import importlib.util
import tempfile
import unittest
from pathlib import Path

from scripts.generate_match import generate
from workflow.video_eventing import detect_video, render_synthetic_feed


@unittest.skipUnless(importlib.util.find_spec("cv2"), "optional OpenCV dependency is unavailable")
class VideoEventingTests(unittest.TestCase):
    def test_unlabelled_video_recovers_pass_and_shot(self):
        _, events, _ = generate(7)
        sample = [next(event for event in events if event["type"]["name"] == kind)
                  for kind in ("Pass", "Shot")]
        with tempfile.TemporaryDirectory() as folder:
            video = Path(folder) / "feed.avi"
            render_synthetic_feed(sample, video)
            found = detect_video(str(video))
        self.assertEqual([item["type"] for item in found], ["Pass", "Shot"])
        for detected, event in zip(found, sample):
            self.assertLess(abs(detected["ball_speed_kmh"] - event["kinematics"]["ball_speed_kmh"]), 20)


if __name__ == "__main__":
    unittest.main()
