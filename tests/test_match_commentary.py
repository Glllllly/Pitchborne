import unittest

from scripts.generate_match import generate
from workflow.match_commentary import build_tracks


class CommentaryTests(unittest.TestCase):
    def test_every_event_has_three_grounded_viewpoints(self):
        match, events, _ = generate(7)
        tracks = build_tracks(match, events)
        self.assertEqual(set(tracks), {"home", "away", "neutral"})
        for audience, lines in tracks.items():
            self.assertEqual([line["event_id"] for line in lines], [event["id"] for event in events])
            self.assertEqual(lines[-1]["match_second"], 5400)
            self.assertTrue(lines[-1]["text"])
        self.assertTrue(any(line["text"] for line in tracks["neutral"][:-1]))

    def test_goal_reaction_follows_allegiance_and_current_score(self):
        match, events, _ = generate(7)
        tracks = build_tracks(match, events)
        index = next(i for i, event in enumerate(events)
                     if event.get("shot", {}).get("outcome", {}).get("name") == "Goal")
        scorer = events[index]["team"]["id"]
        supporter = "home" if scorer == match["home_team"]["id"] else "away"
        opponent = "away" if supporter == "home" else "home"
        self.assertIn("我们", tracks[supporter][index]["text"])
        self.assertIn("丢球", tracks[opponent][index]["text"])
        self.assertNotIn("我们", tracks["neutral"][index]["text"])
        self.assertIn("球进了", tracks["neutral"][index]["text"])


if __name__ == "__main__":
    unittest.main()
