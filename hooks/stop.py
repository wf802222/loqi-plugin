#!/usr/bin/env python3
"""Stop hook — record the retrieval episode for Hebbian learning.

Called by Claude Code when Claude finishes responding. Picks up the
pending episode saved by user_prompt_submit.py and records it with
the pragmatic heuristic: if the user didn't complain, all retrieved
sections were useful.
"""

import json
import os
import sys
from pathlib import Path

# Add plugin root for imports
PLUGIN_ROOT = os.environ.get("CLAUDE_PLUGIN_ROOT", str(Path(__file__).parent.parent))
if PLUGIN_ROOT not in sys.path:
    sys.path.insert(0, PLUGIN_ROOT)

from lib import client


def main():
    try:
        input_data = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        input_data = {}

    cwd = input_data.get("cwd", os.getcwd())

    # Load pending episode
    pending_path = Path(cwd) / ".loqi" / "pending_episode.json"
    if not pending_path.exists():
        print(json.dumps({}))
        sys.exit(0)

    try:
        pending = json.loads(pending_path.read_text())
        pending_path.unlink()
    except (json.JSONDecodeError, OSError):
        print(json.dumps({}))
        sys.exit(0)

    query_text = pending.get("query", "")
    retrieved_ids = pending.get("retrieved_ids", [])

    if not retrieved_ids:
        print(json.dumps({}))
        sys.exit(0)

    # Pragmatic heuristic: all retrieved sections marked useful
    # (if user didn't complain, they were helpful)
    client.record_episode(
        project_path=cwd,
        query_text=query_text,
        retrieved_ids=retrieved_ids,
        useful_ids=retrieved_ids,
    )

    print(json.dumps({}))
    sys.exit(0)


if __name__ == "__main__":
    main()
