import copy
import unittest

from workflow.insights import build_insight
from workflow.pipeline import ROOT, read


class InsightTests(unittest.TestCase):
    def setUp(self):
        self.match = read(ROOT / "data/synthetic/match.json")
        self.events = read(ROOT / "data/synthetic/events.json")

    def build(self, index, **kwargs):
        return build_insight(self.match, self.events, self.events[index]["id"], **kwargs)

    def test_future_events_cannot_change_current_insight(self):
        for index in range(len(self.events)):
            complete = self.build(index)
            prefix = build_insight(self.match, self.events[:index+1], self.events[index]["id"])
            self.assertEqual(complete, prefix)
            known = {event["id"] for event in self.events[:index+1]}
            self.assertTrue(all(e["event_id"] in known for e in complete["evidence"]))
        for index in (0, 1, 2):
            self.assertNotIn("outcome", self.build(index)["ai_request"]["facts"])
            self.assertEqual(self.build(index)["facts"]["score_after"], [0, 0])

    def test_measured_distances_and_angle(self):
        facts = self.build(3)["facts"]
        self.assertEqual(facts["goal_distance_m"], 11.3)
        self.assertEqual(facts["nearest_defender_m"], 1.6)
        self.assertGreater(facts["goal_opening_angle_degrees"], 0)
        self.assertLess(facts["goal_opening_angle_degrees"], 180)

    def test_perspectives_change_words_not_facts(self):
        for index in range(len(self.events)):
            variants = [self.build(index, audience=a) for a in ("neutral", "home", "away")]
            self.assertEqual(len({v["text"] for v in variants}), 3)
            self.assertEqual(variants[0]["facts"], variants[1]["facts"])
            self.assertEqual(variants[1]["facts"], variants[2]["facts"])
        self.assertNotEqual(self.build(3)["text"], self.build(3, mode="analyst")["text"])

    def test_team_preference_follows_possession(self):
        events = copy.deepcopy(self.events)
        events[0]["possession_team"] = self.match["away_team"]
        reversed_view = build_insight(self.match, events, events[0]["id"], audience="away")
        self.assertEqual(self.build(0, audience="home")["text"], reversed_view["text"])

    def test_invalid_writer_falls_back(self):
        class Writer:
            def generate(self, request):
                return {"title": "Unsupported", "text": "Unsupported", "evidence_event_ids": ["future"]}
        result = self.build(0, writer=Writer())
        self.assertEqual(result["generator"], "rules-v1")
        self.assertEqual(result["ai_status"], "fallback")

    def test_valid_writer_can_use_current_evidence(self):
        class Writer:
            def generate(self, request):
                return {"title": "Model title", "text": "Model text", "evidence_event_ids": [request["evidence"][-1]["event_id"]]}
        result = self.build(0, writer=Writer())
        self.assertEqual(result["generator"], "ai")
        self.assertEqual(result["text"], "Model text")

    def test_turnover_and_pressure_explain_without_predicting(self):
        from scripts.generate_match import generate
        match, events, _ = generate(7)
        for kind in ("Interception", "Tackle", "Pressure"):
            event = next(item for item in events if item["type"]["name"] == kind)
            insight = build_insight(match, events, event["id"], audience="neutral")
            self.assertNotEqual(insight["title"], "比赛继续")
            self.assertIn("event_id", insight)
            self.assertEqual(insight["event_id"], event["id"])

    def test_rolling_context_uses_only_past_five_minutes(self):
        from scripts.generate_match import generate
        match, events, _ = generate(7)
        index = next(i for i, item in enumerate(events)
                     if item["type"]["name"] == "Shot" and item["minute"] >= 10)
        shot = events[index]
        insight = build_insight(match, events, shot["id"], mode="analyst")
        second = shot["minute"] * 60 + shot["second"]
        expected = sum(item["type"]["name"] == "Shot" and item["team"]["id"] == shot["team"]["id"]
                       and second - 300 < item["minute"] * 60 + item["second"] <= second
                       for item in events[:index + 1])
        self.assertEqual(insight["context"]["recent_shots"], expected)
        self.assertTrue(insight["analysis"]["verdict"])
        self.assertTrue(insight["analysis"]["why"])
        self.assertEqual(insight["context"], build_insight(match, events[:index + 1], shot["id"])["context"])


if __name__ == "__main__":
    unittest.main()
