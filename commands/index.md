---
description: Force re-index project markdown files into Loqi memory
allowed-tools: ["Bash"]
---

# Re-index Project Memory

Scan the project for markdown files and index any new or modified ones into Loqi's memory graph.

## What to do

1. Run the indexing script:
   ```
   python3 ${CLAUDE_PLUGIN_ROOT}/hooks/session_start.py <<< '{"cwd": "'$(pwd)'"}'
   ```

2. Then check the status:
   ```
   curl -s "http://127.0.0.1:9471/status?project=$(python3 -c "import urllib.parse; print(urllib.parse.quote('$(pwd)', safe=''))")" | python3 -m json.tool
   ```

3. Report to the user:
   - How many files were scanned
   - How many were new or modified
   - How many sections were created
   - Current memory totals (sections, edges, triggers)
