import json
import sys
import time
import unittest

from workflow.openrouter_writer import OpenRouterInsightWriter


class WriterTests(unittest.TestCase):
    def writer(self, source):
        writer = OpenRouterInsightWriter(sys.executable, {"timeoutMs": 1000})
        writer.command = [sys.executable, "-c", source]
        return writer

    def test_cancel_kills_process_and_releases_slot(self):
        writer = self.writer("import time; time.sleep(30)")
        started = time.monotonic()
        with self.assertRaisesRegex(RuntimeError, "another event"):
            writer.generate({"evidence": [{"event_id": "one"}]}, cancelled=lambda: time.monotonic()-started > .3)
        self.assertLess(time.monotonic()-started, 3)
        self.assertTrue(writer.slots.acquire(blocking=False))
        self.assertTrue(writer.slots.acquire(blocking=False))
        writer.slots.release()
        writer.slots.release()

    def test_valid_response_is_cached_without_another_process(self):
        response = {"title": "A title", "text": "Grounded text", "evidence_event_ids": ["one"]}
        writer = self.writer("print(" + repr(json.dumps(response)) + ")")
        request = {"evidence": [{"event_id": "one"}]}
        self.assertEqual(writer.generate(request), response)
        writer.command = ["nonexistent-test-executable"]
        self.assertEqual(writer.generate(request), response)

    def test_invalid_citations_are_not_cached(self):
        response = {"title": "A title", "text": "Grounded text", "evidence_event_ids": ["future"]}
        writer = self.writer("print(" + repr(json.dumps(response)) + ")")
        writer.generate({"evidence": [{"event_id": "one"}]})
        self.assertFalse(writer.cache)


if __name__ == "__main__":
    unittest.main()
