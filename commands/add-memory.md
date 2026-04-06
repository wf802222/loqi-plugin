---
description: Add an ad-hoc memory note to Loqi that persists across sessions
argument-hint: "memory content or topic"
allowed-tools: ["Bash", "Write"]
---

# Add Memory

Add a free-form memory note to the Loqi system. The note is saved as a markdown file in `.loqi/memories/` and indexed into the memory graph.

## What to do

1. Take the user's input: $ARGUMENTS

2. Generate a short filename from the topic (lowercase, hyphens, no spaces):
   - Example: "always use snake_case" → "always-use-snake-case.md"

3. Write the memory to `.loqi/memories/<filename>.md` using the Write tool:
   ```markdown
   ## <Title derived from content>

   <User's memory content>

   _Added: <current date>_
   ```

4. Index the file by calling:
   ```
   curl -s -X POST http://127.0.0.1:9471/index \
     -H "Content-Type: application/json" \
     -d '{"project_path": "'$(pwd)'", "doc_id": "<filename>", "title": "<title>", "content": "<full content>"}'
   ```

5. Confirm to the user what was saved and that it will be retrieved in future sessions.
