import json
import threading
import unittest
from http.server import ThreadingHTTPServer
from urllib.request import Request, urlopen

from workflow.server import Handler


class InsightEndpointTests(unittest.TestCase):
    def test_insight_endpoint_accepts_current_match_event(self):
        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        base = f"http://127.0.0.1:{server.server_port}"
        try:
            with urlopen(base + "/api/match") as response:
                match = json.load(response)
            shot = next(event for event in match["events"] if event["type"]["name"] == "Shot")
            request = Request(
                base + "/api/insights",
                data=json.dumps({"event_id": shot["id"], "audience": "neutral",
                                 "mode": "casual", "use_ai": False}).encode(),
                headers={"Content-Type": "application/json"},
            )
            with urlopen(request) as response:
                insight = json.load(response)
            self.assertEqual(insight["event_id"], shot["id"])
            self.assertTrue(insight["text"])
        finally:
            server.shutdown()
            server.server_close()
            worker.join(timeout=2)


if __name__ == "__main__":
    unittest.main()
