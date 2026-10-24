"""Local application server. Run: python -m workflow.server"""

import json
import re
import select
import socket
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse
from uuid import UUID, uuid4

from workflow.pipeline import ROOT, read, run
from workflow.insights import build_insight
from workflow.openrouter_writer import configured_writer
from workflow.openrouter_video import configured_video_provider, VideoServiceError

DATA = ROOT / "data" / "synthetic"
WEB = ROOT / "web"
INSIGHT_WRITER = configured_writer()
VIDEO_PROVIDER = configured_video_provider()


class Handler(BaseHTTPRequestHandler):
    def disconnected(self):
        try:
            readable, _, _ = select.select([self.connection], [], [], 0)
            return bool(readable) and self.connection.recv(1, socket.MSG_PEEK) == b""
        except OSError:
            return True

    def respond(self, status, data, content_type="application/json; charset=utf-8"):
        body = json.dumps(data, ensure_ascii=False).encode() if isinstance(data, dict) else data
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass  # The viewer may have moved to the next event while AI was working.

    def do_GET(self):
        path = urlparse(self.path).path
        video_match = re.fullmatch(r"/api/highlights/([0-9a-f-]{36})(/video)?", path)
        if video_match:
            local_id = video_match.group(1)
            try:
                valid_id = str(UUID(local_id)) == local_id
            except ValueError:
                valid_id = False
            if not valid_id:
                return self.respond(404, {"error": "Not found"})
            folder = ROOT / "outputs" / local_id
            job_file = folder / "video_job.json"
            if not job_file.exists():
                return self.respond(404, {"error": "Video job not found"})
            if video_match.group(2):
                media = folder / "video.mp4"
                if not media.exists():
                    return self.respond(404, {"error": "Video not ready"})
                total = media.stat().st_size
                match = re.fullmatch(r"bytes=(\d*)-(\d*)", self.headers.get("Range", ""))
                start = int(match.group(1)) if match and match.group(1) else 0
                end = int(match.group(2)) if match and match.group(2) else total - 1
                if match and (start >= total or end < start):
                    self.send_response(416)
                    self.send_header("Content-Range", f"bytes */{total}")
                    self.end_headers()
                    return
                end = min(end, total - 1)
                self.send_response(206 if match else 200)
                self.send_header("Content-Type", "video/mp4")
                self.send_header("Accept-Ranges", "bytes")
                self.send_header("Content-Length", str(end - start + 1))
                if match:
                    self.send_header("Content-Range", f"bytes {start}-{end}/{total}")
                self.end_headers()
                try:
                    with media.open("rb") as source:
                        source.seek(start)
                        remaining = end - start + 1
                        while remaining:
                            chunk = source.read(min(65536, remaining))
                            if not chunk:
                                break
                            self.wfile.write(chunk)
                            remaining -= len(chunk)
                except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                    pass
                return
            job = read(job_file)
            if job.get("provider") == "openrouter" and VIDEO_PROVIDER:
                try:
                    job = VIDEO_PROVIDER.poll(job, folder, local_id)
                except VideoServiceError as error:
                    return self.respond(502, {"error": str(error)})
            return self.respond(200, {"job_id": local_id, "video_job": job})
        if path == "/api/match":
            return self.respond(200, {
                "match": read(DATA / "match.json"),
                "events": read(DATA / "events.json"),
                "clips": read(DATA / "clips.json"),
            })
        assets = {
            "/": ("index.html", "text/html; charset=utf-8"),
            "/app.js": ("app.js", "text/javascript; charset=utf-8"),
            "/style.css": ("style.css", "text/css; charset=utf-8"),
        }
        if path in assets:
            name, mime = assets[path]
            return self.respond(200, (WEB / name).read_bytes(), mime)
        self.respond(404, {"error": "Not found"})

    def do_POST(self):
        if self.path not in ("/api/highlights/prepare", "/api/insights"):
            return self.respond(404, {"error": "Not found"})
        # Local-only JSON endpoint; reject cross-origin browser requests.
        if self.headers.get("Origin") not in (None, "http://" + self.headers.get("Host", "")):
            return self.respond(403, {"error": "Cross-origin request rejected"})
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if not 0 < size <= 4096:
                raise ValueError("Expected a small JSON request")
            request = json.loads(self.rfile.read(size))
            if not isinstance(request, dict):
                raise ValueError("Expected JSON object")
            if self.path == "/api/insights":
                use_ai = request.get("use_ai", True)
                if not isinstance(use_ai, bool):
                    raise ValueError("use_ai must be boolean")
                writer = INSIGHT_WRITER if use_ai else None
                if writer is not None:
                    underlying = writer
                    handler = self
                    class CancellableWriter:
                        def generate(self, payload):
                            return underlying.generate(payload, cancelled=handler.disconnected)
                    writer = CancellableWriter()
                insight = build_insight(
                    read(DATA / "match.json"), read(DATA / "events.json"),
                    request.get("event_id"), request.get("audience", "neutral"),
                    request.get("mode", "casual"),
                    writer=writer,
                )
                insight["ai_available"] = INSIGHT_WRITER is not None
                if INSIGHT_WRITER is not None and not use_ai:
                    insight["generator_label"] = "规则解读 · AI 正在生成"
                return self.respond(200, insight)
            if request.get("clip_id") not in {item["id"] for item in read(DATA / "clips.json")}:
                raise ValueError("Unknown clip")
            job_id = str(uuid4())
            artifacts = run(
                request["clip_id"], request.get("pov", "striker"),
                request.get("language", "zh"), DATA, ROOT / "outputs" / job_id,
                audience=request.get("audience", "neutral"),
                provider=VIDEO_PROVIDER,
            )
            self.respond(200, {"job_id": job_id, "artifacts": artifacts})
        except (ValueError, KeyError, StopIteration) as error:
            self.respond(400, {"error": str(error) or "Invalid scene"})
        except OSError:
            self.respond(500, {"error": "Could not read or save workflow files"})
        except VideoServiceError as error:
            self.respond(502, {"error": str(error)})


if __name__ == "__main__":
    server = ThreadingHTTPServer(("127.0.0.1", 8000), Handler)
    print("Inside the Moment: http://127.0.0.1:8000", flush=True)
    print("Insights: OpenRouter enabled" if INSIGHT_WRITER else "Insights: rule baseline (OpenRouter not configured)", flush=True)
    print("Video: OpenRouter enabled" if VIDEO_PROVIDER else "Video: dry run (OpenRouter not configured)", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
