---
description: Manually query Loqi memory to test what it retrieves for a given input
argument-hint: "query text"
allowed-tools: ["Bash"]
---

# Query Memory

Manually query the Loqi memory system to see what sections it would retrieve for a given query. Useful for testing and debugging retrieval quality.

## What to do

1. Take the user's argument as the query text: $ARGUMENTS

2. Send the query to the server:
   ```
   curl -s -X POST http://127.0.0.1:9471/query \
     -H "Content-Type: application/json" \
     -d '{"project_path": "'$(pwd)'", "query": "'"$ARGUMENTS"'", "top_k": 5}'
   ```

3. Display the results clearly:
   - For each section returned, show:
     - Section title
     - Score (higher = more relevant)
     - Source document (parent_id)
     - Content preview (first 200 chars)
   - Show metadata: how many semantic candidates, triggers fired, graph-discovered sections
   - If triggers fired, explain which triggers matched and why

4. If no results, explain that the memory may be empty — suggest running `/loqi:index`.
