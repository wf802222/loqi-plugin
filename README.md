# Loqi — Claude Code Memory Plugin

Persistent project memory for Claude Code. Loqi automatically indexes your project's documentation, retrieves relevant knowledge on every prompt, and learns what's useful over time through Hebbian reinforcement.

## What it does

- **On session start**: Indexes your project's markdown files into a section-level memory graph
- **On every prompt**: Retrieves relevant sections via semantic similarity, associative triggers, and graph traversal — injects them into Claude's context automatically
- **On every response**: Records what was retrieved for Hebbian learning (connections that prove useful grow stronger)
- **Over time**: Learns triggers that fire on specific patterns, promoting frequently-useful connections

## Setup

```bash
cd /path/to/loqi-plugin
bash setup.sh
```

This creates a virtualenv at `~/.loqi-env/` and installs Loqi with the embedding model.

## Install

```bash
claude plugin add /path/to/loqi-plugin
```

## Commands

| Command | Purpose |
|---------|---------|
| `/loqi:index` | Force re-index project markdown files |
| `/loqi:status` | Show memory stats (sections, edges, triggers) |
| `/loqi:query <text>` | Test what Loqi retrieves for a query |
| `/loqi:add-memory` | Add a free-form memory note |
| `/loqi:consolidate` | Run memory consolidation (decay + learning) |

## How it works

A background server on `localhost:9471` holds the embedding model warm. Hooks communicate with it via HTTP:

```
User prompt → UserPromptSubmit hook → HTTP query to server
  → Semantic search + trigger matching + graph traversal
  → Top 5 sections injected as additionalContext
  → Claude sees prompt + relevant project knowledge
```

Per-project data lives in `.loqi/` (add to `.gitignore`):
- `memory.db` — SQLite graph database
- `episodes.jsonl` — Retrieval log for Hebbian learning
- `index.json` — File fingerprint index
- `memories/` — User-created memory notes

## Architecture

Three retrieval channels:
1. **Semantic**: cosine similarity between query and section embeddings
2. **Triggers**: keyword + semantic pattern matching that fires before retrieval
3. **Graph**: edge traversal from top hits to connected sections

Hebbian learning: sections that are retrieved together and prove useful get stronger connections. After enough co-activations, edges promote through the hierarchy (DIFFUSE → SOFT → HARD → Trigger).

## Requirements

- Python 3.12+
- ~500MB disk for the embedding model (all-MiniLM-L6-v2)
- Loqi source code (for editable install)
