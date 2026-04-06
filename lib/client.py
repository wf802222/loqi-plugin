"""HTTP client for hooks to communicate with the Loqi server.

All methods have a 3-second timeout and fail silently —
the user experience must never degrade because the server is slow or down.
"""

from __future__ import annotations

import json
import urllib.request
import urllib.error

BASE_URL = "http://127.0.0.1:9471"
TIMEOUT = 3  # seconds


def _post(path: str, data: dict) -> dict | None:
    """POST JSON to the server. Returns parsed response or None on failure."""
    try:
        body = json.dumps(data).encode("utf-8")
        req = urllib.request.Request(
            f"{BASE_URL}{path}",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return json.loads(resp.read())
    except (urllib.error.URLError, OSError, json.JSONDecodeError, TimeoutError):
        return None


def _get(path: str) -> dict | None:
    """GET from the server. Returns parsed response or None on failure."""
    try:
        req = urllib.request.Request(f"{BASE_URL}{path}")
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return json.loads(resp.read())
    except (urllib.error.URLError, OSError, json.JSONDecodeError, TimeoutError):
        return None


def ping() -> bool:
    """Check if the server is running."""
    result = _get("/ping")
    return result is not None and result.get("ok", False)


def query(project_path: str, query_text: str, top_k: int = 5) -> dict | None:
    """Retrieve memories for a query. Returns None if server is down."""
    return _post("/query", {
        "project_path": project_path,
        "query": query_text,
        "top_k": top_k,
    })


def index_document(project_path: str, doc_id: str, title: str, content: str) -> int:
    """Index a document. Returns section count (0 on failure)."""
    result = _post("/index", {
        "project_path": project_path,
        "doc_id": doc_id,
        "title": title,
        "content": content,
    })
    if result:
        return result.get("sections_created", 0)
    return 0


def record_episode(project_path: str, query_text: str, retrieved_ids: list[str], useful_ids: list[str]) -> bool:
    """Record a retrieval episode for Hebbian learning."""
    result = _post("/update", {
        "project_path": project_path,
        "query": query_text,
        "retrieved_ids": retrieved_ids,
        "useful_ids": useful_ids,
    })
    return result is not None


def consolidate(project_path: str) -> dict | None:
    """Run consolidation. Returns report or None."""
    return _post("/consolidate", {"project_path": project_path})


def status(project_path: str) -> dict | None:
    """Get server and project status."""
    from urllib.parse import quote
    return _get(f"/status?project={quote(project_path, safe='')}")
