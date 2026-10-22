"""Bridge the Python app to the requested official Node OpenRouter SDK."""

from collections import OrderedDict
import json
import logging
import shutil
import subprocess
import threading
import time

from workflow.pipeline import ROOT

LOG = logging.getLogger(__name__)


class OpenRouterInsightWriter:
    def __init__(self, node, config):
        self.command = [node, f"--env-file-if-exists={ROOT / '.env'}", str(ROOT / "adapters/openrouter.mjs")]
        self.config = config
        self.slots = threading.BoundedSemaphore(2)
        self.lock = threading.Lock()
        self.cache = OrderedDict()

    def generate(self, request, cancelled=None):
        payload = json.dumps(request, ensure_ascii=False, sort_keys=True)
        with self.lock:
            if payload in self.cache:
                self.cache.move_to_end(payload)
                return self.cache[payload]
        if not self.slots.acquire(blocking=False):
            raise RuntimeError("OpenRouter is busy")
        try:
            process = subprocess.Popen(
                self.command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                encoding="utf-8", cwd=ROOT,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            deadline = time.monotonic() + self.config["timeoutMs"] / 1000 + 5
            first = True
            try:
                while True:
                    if cancelled is not None and cancelled():
                        raise RuntimeError("Viewer moved to another event")
                    if time.monotonic() >= deadline:
                        raise RuntimeError("OpenRouter adapter timed out")
                    try:
                        stdout, _ = process.communicate(input=payload if first else None, timeout=.2)
                        break
                    except subprocess.TimeoutExpired:
                        first = False
            finally:
                if process.poll() is None:
                    process.kill()
                    process.communicate()
            try:
                response = json.loads(stdout)
            except (ValueError, TypeError):
                raise RuntimeError("OpenRouter adapter did not return JSON") from None
            if process.returncode or response.get("error"):
                # These fields are sanitized by our Node wrapper; never log stderr.
                LOG.warning("OpenRouter unavailable: code=%s status=%s", response.get("error", "adapter_failed"), response.get("status"))
                raise RuntimeError("OpenRouter request failed")
            allowed = {item["event_id"] for item in request["evidence"]}
            refs = response.get("evidence_event_ids")
            valid = (isinstance(refs, list) and request["evidence"][-1]["event_id"] in refs
                     and all(isinstance(ref, str) and ref in allowed for ref in refs)
                     and all(isinstance(response.get(key), str) and 0 < len(response[key].strip()) <= limit
                             for key, limit in (("title", 60), ("text", 320))))
            if valid:
                with self.lock:
                    self.cache[payload] = response
                    while len(self.cache) > 128:
                        self.cache.popitem(last=False)
            return response
        finally:
            self.slots.release()


def configured_writer():
    node = shutil.which("node")
    if not node or not (ROOT / "node_modules/@openrouter/sdk").exists():
        return None
    try:
        command = [node, f"--env-file-if-exists={ROOT / '.env'}", str(ROOT / "adapters/openrouter.mjs"), "--check"]
        result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", timeout=10,
                                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        config = json.loads(result.stdout)
        if result.returncode == 0 and config.get("configured"):
            return OpenRouterInsightWriter(node, config)
    except (OSError, ValueError, subprocess.TimeoutExpired):
        LOG.warning("OpenRouter configuration unavailable; using rule insights")
    return None
