import unittest

from scripts.generate_match import generate
from workflow.match_commentary import build_tracks, build_english_tracks
from workflow.commentary_romance import build_romance_tracks


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

    def test_english_tracks_share_timing_and_change_with_allegiance(self):
        match, events, _ = generate(7)
        tracks = build_english_tracks(match, events)
        self.assertEqual(set(tracks), {"home", "away", "neutral"})
        for lines in tracks.values():
            self.assertEqual([line["event_id"] for line in lines], [event["id"] for event in events])
        index = next(i for i, event in enumerate(events)
                     if event.get("shot", {}).get("outcome", {}).get("name") == "Goal")
        self.assertEqual(len({tracks[side][index]["text"] for side in tracks}), 3)

    def test_spanish_and_french_tracks_keep_timing_lineups_and_fan_reactions(self):
        match, events, _ = generate(7)
        goal_index = next(i for i, event in enumerate(events)
                          if event.get("shot", {}).get("outcome", {}).get("name") == "Goal")
        for language in ("es", "fr"):
            tracks = build_romance_tracks(match, events, language)
            self.assertEqual(set(tracks), {"home", "away", "neutral"})
            for lines in tracks.values():
                self.assertEqual([line["event_id"] for line in lines], [event["id"] for event in events])
                self.assertEqual(len(lines[0]["intro"]), 3)
                self.assertEqual(sum("summary" in line for line in lines), 9)
                self.assertTrue(lines[-1]["text"])
            self.assertEqual(len({tracks[side][goal_index]["text"] for side in tracks}), 3)
            earlier = build_romance_tracks(match, events[:240], language)
            self.assertEqual(tracks["neutral"][:240], earlier["neutral"])

    def test_goal_restart_has_timed_commentary_in_both_languages(self):
        match, events, _ = generate(7)
        index = next(i for i, event in enumerate(events) if event["type"]["name"] == "Kick Off")
        for builder in (build_tracks, build_english_tracks):
            tracks = builder(match, events)
            self.assertTrue(all(tracks[side][index]["text"] for side in tracks))
            self.assertEqual({tracks[side][index]["event_id"] for side in tracks}, {events[index]["id"]})

    def test_opening_call_is_not_described_as_a_restart_after_a_goal(self):
        match, events, _ = generate(7)
        self.assertEqual(events[0]["type"]["name"], "Kick Off")
        self.assertIn("比赛开始", build_tracks(match, events)["neutral"][0]["text"])
        self.assertIn("underway", build_english_tracks(match, events)["neutral"][0]["text"])

    def test_variety_and_past_only_writing(self):
        match, events, _ = generate(7)
        for builder in (build_tracks, build_english_tracks):
            tracks = builder(match, events)
            neutral = [line["text"] for line in tracks["neutral"] if line["text"]]
            self.assertGreater(len(set(neutral)), len(neutral) * .65)
            for cutoff in (80, 240, 500):
                earlier = builder(match, events[:cutoff])
                for audience in tracks:
                    self.assertEqual(tracks[audience][:cutoff], earlier[audience])
            for index, event in enumerate(events):
                if event["type"]["name"] == "Goal Keeper":
                    self.assertTrue(all(not tracks[side][index]["text"] for side in tracks))

    def test_kickoff_lineups_and_interval_summaries(self):
        match, events, _ = generate(7)
        for builder in (build_tracks, build_english_tracks):
            tracks = builder(match, events)
            for audience, lines in tracks.items():
                self.assertEqual(len(lines[0]["intro"]), 3)
                for team in (match["home_team"], match["away_team"]):
                    self.assertTrue(any(team["name"] in intro for intro in lines[0]["intro"]))
                summaries = [(index, line["summary"]) for index, line in enumerate(lines) if line.get("summary")]
                self.assertEqual(len(summaries), 9)
                for index, summary in summaries:
                    self.assertTrue(summary["text"])
                    self.assertLessEqual(summary["period_end_second"],
                                         events[index]["minute"] * 60 + events[index]["second"])
                    if index < len(events) - 1:
                        start = summary["period_start_second"]
                        end = summary["period_end_second"]
                        expected = sum(item["type"]["name"] == "Shot" and
                                       item["team"]["id"] == match["home_team"]["id"] and
                                       start < item["minute"] * 60 + item["second"] <= end
                                       for item in events[:index + 1])
                        self.assertEqual(summary["facts"]["home"]["shots"], expected)


if __name__ == "__main__":
    unittest.main()
