#!/usr/bin/env python3
"""UserPromptSubmit hook — query Loqi and inject relevant memory.

Called by Claude Code before processing each user prompt. This is the
core context injection point: we query the memory graph and return
relevant sections as additionalContext that Claude sees alongside the prompt.

If the server is down or slow, we fail silently — never block the user.
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
from lib.formatting import format_memory_context


def main():
    try:
        input_data = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        print(json.dumps({}))
        sys.exit(0)

    prompt = input_data.get("user_prompt", "")
    cwd = input_data.get("cwd", os.getcwd())

    # Skip empty prompts or slash commands (they have their own handling)
    if not prompt or prompt.startswith("/"):
        print(json.dumps({}))
        sys.exit(0)

    # Query the server
    result = client.query(cwd, prompt, top_k=5)

    if not result or not result.get("sections"):
        print(json.dumps({}))
        sys.exit(0)

    # Format the memory context
    context = format_memory_context(result)

    if not context:
        print(json.dumps({}))
        sys.exit(0)

    # Save pending episode for the Stop hook to pick up
    pending = {
        "query": prompt,
        "retrieved_ids": [s["id"] for s in result.get("sections", [])],
        "triggered_ids": result.get("triggered", []),
    }

    pending_path = Path(cwd) / ".loqi" / "pending_episode.json"
    try:
        pending_path.parent.mkdir(parents=True, exist_ok=True)
        pending_path.write_text(json.dumps(pending))
    except OSError:
        pass  # Non-critical — learning just won't happen for this prompt

    # Output the injection
    output = {
        "hookSpecificOutput": {
            "hookEventName": "UserPromptSubmit",
            "additionalContext": context,
        }
    }
    print(json.dumps(output))
    sys.exit(0)


if __name__ == "__main__":
    main()
