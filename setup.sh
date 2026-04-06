#!/bin/bash
# Loqi Plugin Setup
# Creates a virtualenv and installs Loqi + dependencies.
# Run once after cloning the plugin.

set -e

VENV_DIR="$HOME/.loqi-env"

echo "=== Loqi Plugin Setup ==="
echo ""

# Step 1: Create virtualenv
if [ -d "$VENV_DIR" ]; then
    echo "Virtualenv already exists at $VENV_DIR"
else
    echo "Creating virtualenv at $VENV_DIR..."
    python3 -m venv "$VENV_DIR"
fi

# Step 2: Find pip
if [ -f "$VENV_DIR/Scripts/pip.exe" ]; then
    PIP="$VENV_DIR/Scripts/pip.exe"
    PYTHON="$VENV_DIR/Scripts/python.exe"
elif [ -f "$VENV_DIR/bin/pip" ]; then
    PIP="$VENV_DIR/bin/pip"
    PYTHON="$VENV_DIR/bin/python3"
else
    echo "ERROR: Could not find pip in virtualenv"
    exit 1
fi

# Step 3: Install Loqi
echo "Installing Loqi..."

if [ -n "$LOQI_SOURCE" ] && [ -d "$LOQI_SOURCE" ]; then
    # Development: install from local source
    echo "Installing from local source: $LOQI_SOURCE"
    "$PIP" install -e "$LOQI_SOURCE" --quiet
else
    # Production: install from PyPI
    echo "Installing from PyPI..."
    "$PIP" install loqi --quiet
fi

# Step 4: Pre-download the embedding model
echo "Downloading embedding model (one-time, ~90MB)..."
"$PYTHON" -c "
from sentence_transformers import SentenceTransformer
m = SentenceTransformer('all-MiniLM-L6-v2')
print(f'Model ready: {m.get_sentence_embedding_dimension()}d')
"

echo ""
echo "=== Setup Complete ==="
echo ""
echo "Install the plugin in Claude Code:"
echo "  claude plugin add $(cd "$(dirname "$0")" && pwd)"
echo ""
