---
description: Run Loqi memory consolidation (decay, replay, bridge discovery, trigger mining)
allowed-tools: ["Bash"]
---

# Consolidate Memory

Run the Loqi consolidation cycle — the system's equivalent of "sleeping on it." This process:
- **Decays** stale edges that haven't been used recently
- **Replays** recent episodes to re-strengthen useful connections
- **Promotes** edges that have been co-activated enough (DIFFUSE → SOFT → HARD → Trigger)
- **Discovers bridges** between sections that share strong neighbors
- **Mines triggers** from sections that keep appearing useful

## What to do

1. Run consolidation:
   ```
   curl -s -X POST http://127.0.0.1:9471/consolidate \
     -H "Content-Type: application/json" \
     -d '{"project_path": "'$(pwd)'"}'
   ```

2. Display the consolidation report:
   - Episodes replayed
   - Edges strengthened
   - Promotions (edge type upgrades)
   - Bridges discovered (new cross-section connections)
   - Trigger candidates (new learned triggers)
   - Any decay statistics

3. Explain what changed in plain language. For example:
   - "3 edges promoted from DIFFUSE to SOFT — these connections are getting stronger through repeated use"
   - "1 new Hebbian trigger mined — the system learned a new retrieval pattern"
