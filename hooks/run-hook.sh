#!/bin/bash
# Cross-platform hook runner: finds the Loqi venv Python and runs the given hook script.
# Usage: run-hook.sh <script.py>

SCRIPT="$1"
PLUGIN_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

# Find the venv Python
if [ -f "$HOME/.loqi-env/Scripts/python.exe" ]; then
    # Windows (Git Bash)
    PYTHON="$HOME/.loqi-env/Scripts/python.exe"
elif [ -f "$HOME/.loqi-env/bin/python3" ]; then
    # Unix
    PYTHON="$HOME/.loqi-env/bin/python3"
elif [ -f "$USERPROFILE/.loqi-env/Scripts/python.exe" ]; then
    # Windows (USERPROFILE fallback)
    PYTHON="$USERPROFILE/.loqi-env/Scripts/python.exe"
else
    # Fallback: system python
    PYTHON="python3"
fi

export PYTHONPATH="${PLUGIN_ROOT}:${PYTHONPATH}"
export CLAUDE_PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-$PLUGIN_ROOT}"

exec "$PYTHON" "$SCRIPT"
