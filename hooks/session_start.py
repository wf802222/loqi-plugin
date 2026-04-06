#!/usr/bin/env python3
"""SessionStart hook — start the Loqi server and index project files.

Called by Claude Code when a session begins. Responsible for:
1. Ensuring the background server is running
2. Scanning for new/modified markdown files
3. Indexing any changes
"""

import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

# Add plugin root for imports
PLUGIN_ROOT = os.environ.get("CLAUDE_PLUGIN_ROOT", str(Path(__file__).parent.parent))
if PLUGIN_ROOT not in sys.path:
    sys.path.insert(0, PLUGIN_ROOT)

from lib import client


def find_python() -> str:
    """Find a Python executable that can import loqi.

    Checks (in order):
    1. Dedicated Loqi virtualenv (~/.loqi-env/)
    2. Loqi project's own venv (if LOQI_SOURCE is set or default path exists)
    3. Current Python (if loqi is importable)
    4. System python3 as fallback
    """
    if sys.platform == "win32":
        venv_candidates = [
            Path.home() / ".loqi-env" / "Scripts" / "python.exe",
        ]
    else:
        venv_candidates = [
            Path.home() / ".loqi-env" / "bin" / "python3",
        ]

    # Also check LOQI_SOURCE if set (developer mode)
    loqi_source = os.environ.get("LOQI_SOURCE", "")
    if loqi_source:
        if sys.platform == "win32":
            venv_candidates.append(Path(loqi_source) / ".venv" / "Scripts" / "python.exe")
        else:
            venv_candidates.append(Path(loqi_source) / ".venv" / "bin" / "python3")

    for p in venv_candidates:
        if p.exists():
            return str(p)

    return "python3"


def server_env() -> dict:
    """Build environment variables for the server process.

    Ensures PYTHONPATH includes both the Loqi source and the plugin root
    so the server can import from both loqi.* and server.*.
    """
    env = dict(os.environ)
    plugin_root = PLUGIN_ROOT
    paths = [plugin_root]

    # If LOQI_SOURCE is set, add its src/ to PYTHONPATH (developer mode)
    loqi_source = os.environ.get("LOQI_SOURCE", "")
    if loqi_source:
        loqi_src = os.path.join(loqi_source, "src")
        if os.path.isdir(loqi_src):
            paths.insert(0, loqi_src)

    existing = env.get("PYTHONPATH", "")
    if existing:
        paths.append(existing)

    env["PYTHONPATH"] = os.pathsep.join(paths)
    return env


def start_server() -> bool:
    """Start the Loqi background server. Returns True if started."""
    python = find_python()
    server_script = os.path.join(PLUGIN_ROOT, "server", "loqi_server.py")

    env = server_env()

    # Start as detached background process
    if sys.platform == "win32":
        CREATE_NO_WINDOW = 0x08000000
        subprocess.Popen(
            [python, server_script],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=env,
            creationflags=CREATE_NO_WINDOW,
        )
    else:
        subprocess.Popen(
            [python, server_script],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=env,
            start_new_session=True,
        )

    # Wait for server to be ready
    for _ in range(20):
        time.sleep(0.5)
        if client.ping():
            return True

    return False


def file_hash(path: Path) -> str:
    """SHA256 hash of a file's contents."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def scan_and_index(cwd: str) -> dict:
    """Scan for new/modified markdown files and index them.

    Returns summary of what was indexed.
    """
    project_path = Path(cwd)
    loqi_dir = project_path / ".loqi"
    loqi_dir.mkdir(parents=True, exist_ok=True)
    (loqi_dir / "memories").mkdir(exist_ok=True)

    index_file = loqi_dir / "index.json"

    # Load existing index
    existing_index = {}
    if index_file.exists():
        try:
            existing_index = json.loads(index_file.read_text())
        except (json.JSONDecodeError, OSError):
            pass

    # Find indexable files
    md_files = []
    # Project root markdown files
    for f in project_path.glob("*.md"):
        md_files.append(f)
    # .claude/ directory
    claude_dir = project_path / ".claude"
    if claude_dir.exists():
        for f in claude_dir.rglob("*.md"):
            md_files.append(f)
    # .loqi/memories/ directory
    memories_dir = loqi_dir / "memories"
    if memories_dir.exists():
        for f in memories_dir.glob("*.md"):
            md_files.append(f)

    # Check for new/modified files
    files_indexed = 0
    sections_created = 0
    new_index = {}

    for f in md_files:
        fpath = str(f.resolve())
        fhash = file_hash(f)
        new_index[fpath] = {"hash": fhash, "mtime": f.stat().st_mtime}

        # Skip if unchanged
        if fpath in existing_index and existing_index[fpath].get("hash") == fhash:
            continue

        # Index the file
        content = f.read_text(encoding="utf-8", errors="replace")
        doc_id = f.stem  # filename without extension
        title = f.stem.replace("_", " ").replace("-", " ").title()

        count = client.index_document(cwd, doc_id, title, content)
        files_indexed += 1
        sections_created += count

    # Save updated index
    index_file.write_text(json.dumps(new_index, indent=2))

    return {
        "files_scanned": len(md_files),
        "files_indexed": files_indexed,
        "sections_created": sections_created,
    }


def main():
    try:
        input_data = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        input_data = {}

    cwd = input_data.get("cwd", os.getcwd())

    # Step 1: Ensure server is running
    server_ready = client.ping()
    if not server_ready:
        server_ready = start_server()

    if not server_ready:
        # Server failed to start — exit silently
        print(json.dumps({}))
        sys.exit(0)

    # Step 2: Scan and index files
    summary = scan_and_index(cwd)

    # Step 3: Build output message
    parts = ["Loqi memory active."]
    if summary["files_indexed"] > 0:
        parts.append(
            f"Indexed {summary['files_indexed']} file(s), "
            f"{summary['sections_created']} new section(s)."
        )

    status = client.status(cwd)
    if status and status.get("project"):
        proj = status["project"]
        parts.append(
            f"Memory: {proj.get('sections', 0)} sections, "
            f"{proj.get('edges', 0)} edges, "
            f"{proj.get('triggers_explicit', 0)}+{proj.get('triggers_hebbian', 0)} triggers."
        )

    context_msg = " ".join(parts)

    output = {
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": context_msg,
        }
    }
    print(json.dumps(output))
    sys.exit(0)


if __name__ == "__main__":
    main()
