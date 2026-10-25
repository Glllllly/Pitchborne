"""OpenRouter's asynchronous video API; credentials never leave the server."""

import json
import os
import re
import hashlib
from pathlib import Path
from threading import Lock

import requests

from workflow.pipeline import ROOT

BASE = "https://openrouter.ai/api/v1/videos"
MAX_VIDEO_BYTES = 100 * 1024 * 1024


class VideoServiceError(RuntimeError):
    def __init__(self, message, status_code=None):
        super().__init__(message)
        self.status_code = status_code


def setting(name):
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8-sig").splitlines():
            key, sep, value = line.partition("=")
            if sep and key.strip() == name:
                configured = value.strip().strip('"\'')
                if configured:
                    return configured
    return os.environ.get(name, "")


class OpenRouterVideoProvider:
    def __init__(self, api_key, model="bytedance/seedance-2.0-mini", session=None):
        self.key = api_key
        self.model = model
        self.session = session or requests.Session()
        self.lock = Lock()
        self.submit_lock = Lock()
        self.submitted = {}

    @property
    def headers(self):
        return {"Authorization": f"Bearer {self.key}"}

    def _json(self, method, url, **kwargs):
        try:
            response = self.session.request(method, url, headers=self.headers,
                                            timeout=60, allow_redirects=False, **kwargs)
            response.raise_for_status()
            data = response.json()
            if not isinstance(data, dict):
                raise ValueError("Expected object")
            return data
        except (requests.RequestException, ValueError) as error:
            status = getattr(getattr(error, "response", None), "status_code", None)
            if status == 402:
                raise VideoServiceError("OpenRouter 视频请求被拒绝（HTTP 402）：请检查账户余额和 API Key 消费上限", status) from None
            raise VideoServiceError(f"OpenRouter video request failed{f' (HTTP {status})' if status else ''}", status) from None

    def submit(self, request):
        payload = {"model": self.model, "prompt": request["prompt"]}
        duration = request.get("duration_seconds")
        if isinstance(duration, int) and 4 <= duration <= 15:
            payload["duration"] = duration
        fingerprint = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
        with self.submit_lock:
            remote_id = self.submitted.get(fingerprint)
            if remote_id is None:
                data = self._json("POST", BASE, json=payload)
                remote_id = data.get("id")
                if not isinstance(remote_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", remote_id):
                    raise VideoServiceError("OpenRouter returned an invalid video job ID")
                self.submitted[fingerprint] = remote_id
        return {"provider": "openrouter", "model": self.model, "status": "queued",
                "remote_job_id": remote_id, "media_url": None}

    def poll(self, job, output_dir, local_id):
        with self.lock:
            saved = output_dir / "video_job.json"
            job = json.loads(saved.read_text(encoding="utf-8"))
            if job["status"] in ("succeeded", "failed"):
                return job
            remote_id = job["remote_job_id"]
            if not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", remote_id):
                raise VideoServiceError("Invalid video job ID")
            try:
                data = self._json("GET", f"{BASE}/{remote_id}")
            except VideoServiceError as error:
                if error.status_code != 404:
                    raise
                job["status"] = "failed"
                job["error"] = "OpenRouter 视频任务已失效或不存在（HTTP 404），无法继续查询"
                saved.write_text(json.dumps(job, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                return job
            status = data.get("status")
            if status == "pending":
                job["status"] = "queued"
            elif status == "in_progress":
                job["status"] = "running"
            elif status == "completed":
                self._download(remote_id, output_dir / "video.mp4")
                job["status"] = "succeeded"
                job["media_url"] = f"/api/highlights/{local_id}/video"
            elif status in ("failed", "cancelled", "expired"):
                job["status"] = "failed"
                job["error"] = str(data.get("error") or status)[:300]
            else:
                raise VideoServiceError("OpenRouter returned an unknown video status")
            saved.write_text(json.dumps(job, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            return job

    def _download(self, remote_id, destination):
        temporary = destination.with_suffix(".part")
        try:
            with self.session.get(f"{BASE}/{remote_id}/content?index=0", headers=self.headers,
                                  stream=True, timeout=120) as response:
                response.raise_for_status()
                if not response.headers.get("Content-Type", "").lower().startswith("video/"):
                    raise VideoServiceError("OpenRouter did not return video content")
                size = 0
                with temporary.open("wb") as output:
                    for chunk in response.iter_content(65536):
                        size += len(chunk)
                        if size > MAX_VIDEO_BYTES:
                            raise VideoServiceError("Generated video exceeds 100 MB")
                        output.write(chunk)
                if size == 0:
                    raise VideoServiceError("OpenRouter returned an empty video")
            temporary.replace(destination)
        except requests.RequestException as error:
            status = getattr(getattr(error, "response", None), "status_code", None)
            raise VideoServiceError(f"Video download failed{f' (HTTP {status})' if status else ''}") from None
        finally:
            temporary.unlink(missing_ok=True)


def configured_video_provider():
    key = setting("OPENROUTER_API_KEY")
    return OpenRouterVideoProvider(key, setting("OPENROUTER_VIDEO_MODEL") or
                                   "bytedance/seedance-2.0-mini") if key else None
