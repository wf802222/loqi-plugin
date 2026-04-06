---
description: Show Loqi memory system status and statistics
allowed-tools: ["Bash"]
---

# Memory Status

Show the current state of the Loqi memory system for this project.

## What to do

1. Query the server status:
   ```
   curl -s "http://127.0.0.1:9471/status?project=$(python3 -c "import urllib.parse; print(urllib.parse.quote('$(pwd)', safe=''))")"
   ```

2. If the server is not responding, tell the user:
   - "Loqi server is not running. Start a new session or run `/loqi:index` to restart it."

3. If the server responds, display:
   - Server uptime
   - Whether the embedding model is loaded
   - Number of memory sections
   - Number of edges (connections between sections)
   - Number of explicit triggers (from document indexing)
   - Number of Hebbian triggers (learned from usage)
   - Number of episodes logged (retrieval events)
