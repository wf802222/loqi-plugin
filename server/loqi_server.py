"""Loqi background HTTP server.

Holds the embedding model warm and serves per-project memory operations.
Runs on localhost:9471. Auto-exits after 30 minutes of inactivity.

Start:  python loqi_server.py
Check:  curl http://localhost:9471/ping
Logs:   ~/.loqi/server.log
"""

from __future__ import annotations

import json
import logging
import sys
import time
import traceback
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path

# Add the plugin root for imports
PLUGIN_ROOT = Path(__file__).parent.parent
if str(PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGIN_ROOT))

from server.lifecycle import IdleShutdown, write_pid, remove_pid
from server.project_manager import ProjectManager

PORT = 9471
LOG_DIR = Path.home() / ".loqi"
LOG_PATH = LOG_DIR / "server.log"

_start_time = time.time()
_manager: ProjectManager | None = None
_idle: IdleShutdown | None = None
log = logging.getLogger("loqi")


def setup_logging() -> None:
    """Configure logging to file at ~/.loqi/server.log."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    handler = logging.FileHandler(str(LOG_PATH), encoding="utf-8")
    handler.setFormatter(logging.Formatter(
        "%(asctime)s %(levelname)s %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    ))

    root = logging.getLogger("loqi")
    root.setLevel(logging.INFO)
    root.addHandler(handler)


class LoqiHandler(BaseHTTPRequestHandler):
    """HTTP request handler for Loqi memory operations."""

    def log_message(self, format, *args):
        """Log HTTP requests to file instead of stderr."""
        log.info(format, *args)

    def _send_json(self, data: dict, status: int = 200) -> None:
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self) -> dict:
        length = int(self.headers.get("Content-Length", 0))
        if length == 0:
            return {}
        raw = self.rfile.read(length)
        return json.loads(raw)

    def _check_model_ready(self) -> bool:
        """Return True if model is ready. Sends 503 and returns False if not."""
        if not _manager or not _manager.model_loaded:
            self._send_json({"error": "Model not ready", "retry": True}, 503)
            return False
        return True

    def do_GET(self) -> None:
        global _idle
        if _idle:
            _idle.reset()

        if self.path == "/ping":
            self._send_json({"ok": True})

        elif self.path.startswith("/status"):
            self._handle_status()

        else:
            self._send_json({"error": "Not found"}, 404)

    def do_POST(self) -> None:
        global _idle
        if _idle:
            _idle.reset()

        try:
            if self.path == "/query":
                self._handle_query()
            elif self.path == "/index":
                self._handle_index()
            elif self.path == "/update":
                self._handle_update()
            elif self.path == "/consolidate":
                self._handle_consolidate()
            else:
                self._send_json({"error": "Not found"}, 404)
        except Exception as e:
            log.error("Error handling %s: %s\n%s", self.path, e, traceback.format_exc())
            self._send_json({"error": str(e)}, 500)

    def _handle_query(self) -> None:
        if not self._check_model_ready():
            return

        data = self._read_json()
        project_path = data.get("project_path", "")
        query = data.get("query", "")
        top_k = data.get("top_k", 5)

        if not project_path or not query:
            self._send_json({"error": "project_path and query required"}, 400)
            return

        state = _manager.get(project_path)
        result = state.query(query, top_k=top_k)
        self._send_json(result)

    def _handle_index(self) -> None:
        if not self._check_model_ready():
            return

        data = self._read_json()
        project_path = data.get("project_path", "")
        doc_id = data.get("doc_id", "")
        title = data.get("title", "")
        content = data.get("content", "")

        if not project_path or not doc_id:
            self._send_json({"error": "project_path and doc_id required"}, 400)
            return

        state = _manager.get(project_path)
        count = state.index_document(doc_id, title, content)
        self._send_json({"sections_created": count})

    def _handle_update(self) -> None:
        data = self._read_json()
        project_path = data.get("project_path", "")
        query_text = data.get("query", "")
        retrieved_ids = data.get("retrieved_ids", [])
        useful_ids = data.get("useful_ids", [])

        if not project_path:
            self._send_json({"error": "project_path required"}, 400)
            return

        state = _manager.get(project_path)
        state.update(query_text, retrieved_ids, useful_ids)
        self._send_json({"ok": True})

    def _handle_consolidate(self) -> None:
        data = self._read_json()
        project_path = data.get("project_path", "")

        if not project_path:
            self._send_json({"error": "project_path required"}, 400)
            return

        state = _manager.get(project_path)
        report = state.consolidate()
        self._send_json(report)

    def _handle_status(self) -> None:
        # Parse project from query string
        project_path = ""
        if "?" in self.path:
            params = self.path.split("?", 1)[1]
            for pair in params.split("&"):
                if pair.startswith("project="):
                    project_path = pair[8:]

        result = {
            "ok": True,
            "uptime_seconds": int(time.time() - _start_time),
            "model_loaded": _manager.model_loaded if _manager else False,
        }

        if project_path:
            from urllib.parse import unquote
            project_path = unquote(project_path)
            state = _manager.get(project_path)
            result["project"] = state.status()

        self._send_json(result)


def main():
    global _manager, _idle

    setup_logging()
    write_pid()

    try:
        log.info("Loqi server starting on port %d...", PORT)
        _manager = ProjectManager()
        log.info("Server ready.")

        _idle = IdleShutdown()

        server = HTTPServer(("127.0.0.1", PORT), LoqiHandler)
        log.info("Listening on http://127.0.0.1:%d", PORT)
        server.serve_forever()
    except KeyboardInterrupt:
        log.info("Shutdown requested.")
    except OSError as e:
        if "Address already in use" in str(e) or "10048" in str(e):
            log.warning("Port %d already in use — another server is likely running.", PORT)
            sys.exit(0)
        log.error("Startup error: %s", e, exc_info=True)
        raise
    except Exception as e:
        log.error("Fatal error: %s", e, exc_info=True)
        raise
    finally:
        remove_pid()


if __name__ == "__main__":
    main()
