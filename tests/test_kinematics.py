import unittest

from scripts.generate_match import generate


class KinematicsTests(unittest.TestCase):
    def test_ball_metrics_are_deterministic_and_bounded(self):
        _, events, _ = generate(7)
        _, again, _ = generate(7)
        for event, repeated in zip(events, again):
            self.assertEqual(event.get("kinematics"), repeated.get("kinematics"))
            if event["type"]["name"] not in ("Pass", "Shot"):
                self.assertNotIn("kinematics", event)
                continue
            values = event["kinematics"]
            self.assertGreater(values["ball_distance_m"], 0)
            self.assertGreater(values["ball_flight_seconds"], 0)
            self.assertGreater(values["ball_speed_kmh"], 0)
            if event["type"]["name"] == "Pass":
                self.assertIn(values["pass_difficulty_level"], ("low", "medium", "high"))
                self.assertGreaterEqual(values["pass_difficulty"], 0)
                self.assertLessEqual(values["pass_difficulty"], 100)
            else:
                self.assertNotIn("pass_difficulty", values)


if __name__ == "__main__":
    unittest.main()
