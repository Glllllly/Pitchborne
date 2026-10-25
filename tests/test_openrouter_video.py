import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from requests import HTTPError, Response

from workflow.openrouter_video import OpenRouterVideoProvider, VideoServiceError, setting


class FakeResponse:
    def __init__(self, data=None, content=b"video-data", mime="video/mp4"):
        self.data = data
        self.content = content
        self.headers = {"Content-Type": mime}

    def raise_for_status(self):
        pass

    def json(self):
        return self.data

    def iter_content(self, size):
        yield self.content

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


class FakeSession:
    def __init__(self, statuses):
        self.statuses = iter(statuses)
        self.calls = []

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        if method == "POST":
            return FakeResponse({"id": "remote123", "status": "pending"})
        return FakeResponse(next(self.statuses))

    def get(self, url, **kwargs):
        self.calls.append(("DOWNLOAD", url, kwargs))
        return FakeResponse()


class OpenRouterVideoTests(unittest.TestCase):
    def test_dotenv_key_takes_precedence_over_process_environment(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / ".env").write_text("OPENROUTER_API_KEY=dotenv-key\n", encoding="utf-8")
            with patch("workflow.openrouter_video.ROOT", Path(tmp)), patch.dict("os.environ", {"OPENROUTER_API_KEY": "old-key"}):
                self.assertEqual(setting("OPENROUTER_API_KEY"), "dotenv-key")

    def test_submit_poll_download_and_keep_key_server_side(self):
        session = FakeSession([{"status": "in_progress"}, {"status": "completed"}])
        provider = OpenRouterVideoProvider("secret", session=session)
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            job = provider.submit({"prompt": "POV football", "duration_seconds": 6})
            self.assertEqual(session.calls[0][2]["json"]["duration"], 6)
            saved = folder / "video_job.json"
            saved.write_text(json.dumps(job), encoding="utf-8")
            self.assertEqual(provider.poll(job, folder, "local-id")["status"], "running")
            result = provider.poll(job, folder, "local-id")
            self.assertEqual(result["status"], "succeeded")
            self.assertEqual(result["media_url"], "/api/highlights/local-id/video")
            self.assertEqual((folder / "video.mp4").read_bytes(), b"video-data")
            self.assertEqual(session.calls[-1][2]["headers"]["Authorization"], "Bearer secret")
            self.assertNotIn("secret", saved.read_text(encoding="utf-8"))
            self.assertEqual(provider.poll(job, folder, "local-id")["status"], "succeeded")
            self.assertEqual(len(session.calls), 4)

    def test_failed_job_does_not_download(self):
        session = FakeSession([{"status": "failed", "error": "provider error"}])
        provider = OpenRouterVideoProvider("secret", session=session)
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            job = provider.submit({"prompt": "football"})
            (folder / "video_job.json").write_text(json.dumps(job), encoding="utf-8")
            result = provider.poll(job, folder, "local-id")
            self.assertEqual(result["status"], "failed")
            self.assertFalse((folder / "video.mp4").exists())

    def test_reject_invalid_remote_id(self):
        session = FakeSession([])
        session.request = lambda *args, **kwargs: FakeResponse({"id": "https://evil.example"})
        with self.assertRaises(VideoServiceError):
            OpenRouterVideoProvider("secret", session=session).submit({"prompt": "football"})

    def test_payment_required_explains_why_no_job_was_created(self):
        session = FakeSession([])
        def rejected(*args, **kwargs):
            response = Response()
            response.status_code = 402
            raise HTTPError(response=response)
        session.request = rejected
        with self.assertRaisesRegex(VideoServiceError, "HTTP 402.*credits"):
            OpenRouterVideoProvider("secret", session=session).submit({"prompt": "football"})

    def test_missing_remote_job_becomes_terminal_failure(self):
        session = FakeSession([])
        def missing(*args, **kwargs):
            response = Response()
            response.status_code = 404
            raise HTTPError(response=response)
        session.request = missing
        provider = OpenRouterVideoProvider("secret", session=session)
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            job = {"provider": "openrouter", "status": "queued", "remote_job_id": "remote123"}
            (folder / "video_job.json").write_text(json.dumps(job), encoding="utf-8")
            result = provider.poll(job, folder, "local-id")
            self.assertEqual(result["status"], "failed")
            self.assertIn("HTTP 404", result["error"])
            self.assertEqual(provider.poll(job, folder, "local-id")["status"], "failed")


if __name__ == "__main__":
    unittest.main()
