"""Per-project Loqi state management.

Maintains a cache of GraphStore + SectionRetrieval instances keyed by
project path. All projects share a single EmbeddingModel (the expensive
part). Each project gets its own SQLite database at .loqi/memory.db.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from loqi.graph.embeddings import EmbeddingModel
from loqi.graph.models import NodeType, TriggerOrigin
from loqi.graph.store import GraphStore
from loqi.graph.writer import MemoryWriter
from loqi.hebbian.consolidator import Consolidator
from loqi.hebbian.decay import DecayManager
from loqi.hebbian.episode import Episode, EpisodeLog
from loqi.hebbian.promoter import EdgePromoter
from loqi.hebbian.updater import HebbianUpdater
from loqi.pipeline.config import PipelineConfig, LOQI_FULL
from loqi.triggers.extractor import extract_triggers
from loqi.triggers.matcher import match_triggers


class ProjectState:
    """All Loqi state for a single project."""

    def __init__(self, project_path: str, model: EmbeddingModel, config: PipelineConfig):
        self.project_path = project_path
        self._model = model
        self._config = config

        loqi_dir = Path(project_path) / ".loqi"
        loqi_dir.mkdir(parents=True, exist_ok=True)

        db_path = str(loqi_dir / "memory.db")
        self._store = GraphStore(db_path)
        self._writer = MemoryWriter(self._store, self._model)
        self._episode_log = EpisodeLog()

        self._updater = HebbianUpdater(self._store, self._episode_log, self._config)
        self._promoter = EdgePromoter(
            self._store, self._episode_log, self._config, self._model
        )
        self._decay = DecayManager(self._store, self._config)
        self._consolidator = Consolidator(
            self._store, self._episode_log, self._config, self._model
        )

        # Hydrate in-memory caches from persisted SQLite
        self._section_nodes = []
        self._section_embeddings = None
        self._explicit_triggers = []
        self._rebuild_caches()

        # Load persisted episodes
        self._episodes_path = loqi_dir / "episodes.jsonl"
        self._load_episodes()

    def _rebuild_caches(self) -> None:
        """Load section nodes and triggers from SQLite into memory."""
        all_nodes = self._store.get_all_nodes()
        self._section_nodes = [
            n for n in all_nodes
            if n.node_type == NodeType.SECTION and n.embedding is not None
        ]
        if self._section_nodes:
            self._section_embeddings = np.array(
                [n.embedding for n in self._section_nodes], dtype=np.float32
            )
        else:
            self._section_embeddings = None

        self._explicit_triggers = self._store.get_all_triggers()

    def _load_episodes(self) -> None:
        """Load episodes from disk into the episode log."""
        if not self._episodes_path.exists():
            return
        try:
            with open(self._episodes_path, "r") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    data = json.loads(line)
                    ep = Episode(
                        context=data["context"],
                        retrieved_ids=data.get("retrieved_ids", []),
                        triggered_ids=set(data.get("triggered_ids", [])),
                        useful_ids=set(data.get("useful_ids", [])),
                    )
                    self._episode_log.record(ep)
        except (json.JSONDecodeError, KeyError, OSError):
            pass  # Corrupted file — start fresh

    def _save_episode(self, episode: Episode) -> None:
        """Append a single episode to the JSONL file."""
        data = {
            "context": episode.context,
            "retrieved_ids": episode.retrieved_ids,
            "triggered_ids": list(episode.triggered_ids),
            "useful_ids": list(episode.useful_ids),
            "timestamp": episode.timestamp.isoformat(),
        }
        with open(self._episodes_path, "a") as f:
            f.write(json.dumps(data) + "\n")

    def index_document(self, doc_id: str, title: str, content: str) -> int:
        """Index a document into the memory graph. Returns section count."""
        sections = self._writer.ingest_document(doc_id, title, content)

        if self._config.enable_triggers:
            for section in sections:
                section_content = f"{section.title}\n{section.content}"
                section_triggers = extract_triggers(
                    section.id, section_content, self._model
                )
                for trigger in section_triggers:
                    self._store.add_trigger(trigger)

        self._rebuild_caches()
        return len(sections)

    def query(self, query_text: str, top_k: int = 5) -> dict:
        """Retrieve relevant sections for a query. Returns structured result."""
        if not self._section_nodes or self._section_embeddings is None:
            return {"sections": [], "triggered": [], "metadata": {}}

        from loqi.graph.embeddings import cosine_similarity_matrix

        query_embedding = self._model.encode_single(query_text)

        # Channel 1: Semantic similarity
        similarities = cosine_similarity_matrix(
            query_embedding, self._section_embeddings
        )
        semantic_k = min(top_k * 2, len(self._section_nodes))
        semantic_indices = np.argsort(similarities)[::-1][:semantic_k]
        semantic_scores = {}
        for i in semantic_indices:
            node = self._section_nodes[int(i)]
            semantic_scores[node.id] = float(similarities[int(i)])

        # Channel 2: Trigger matching
        triggered_ids = []
        if self._config.enable_triggers and self._explicit_triggers:
            fired = match_triggers(
                self._explicit_triggers,
                query_text,
                query_embedding,
                threshold=self._config.trigger_confidence_threshold,
            )
            triggered_ids = [t.associated_node_id for t, score in fired]

        # Channel 3: Graph traversal (1-hop from top semantic hits)
        graph_boosts = {}
        if self._config.enable_graph:
            entry_ids = [self._section_nodes[int(i)].id for i in semantic_indices[:5]]
            entry_ids.extend(triggered_ids[:3])
            for entry_id in entry_ids:
                neighbors = self._store.get_neighbors(entry_id, min_weight=0.10)
                for neighbor_id, edge in neighbors:
                    if neighbor_id not in semantic_scores:
                        graph_boosts[neighbor_id] = max(
                            graph_boosts.get(neighbor_id, 0),
                            edge.weight * 0.3,
                        )

        # Merge scores
        final_scores = dict(semantic_scores)
        best_semantic = max(semantic_scores.values()) if semantic_scores else 0.0

        for tid in triggered_ids:
            if tid in final_scores:
                final_scores[tid] = min(
                    final_scores[tid] + 0.15, best_semantic + 0.05
                )
            else:
                final_scores[tid] = min(0.15, best_semantic + 0.05)

        for gid, boost in graph_boosts.items():
            if gid in final_scores:
                final_scores[gid] = min(
                    final_scores[gid] + boost, best_semantic + 0.03
                )
            else:
                final_scores[gid] = min(boost, best_semantic + 0.03)

        # Rank and return top_k
        ranked = sorted(final_scores.items(), key=lambda x: x[1], reverse=True)[:top_k]

        # Build result sections
        node_map = {n.id: n for n in self._section_nodes}
        # Also check nodes not in section cache (graph-discovered)
        for nid, _ in ranked:
            if nid not in node_map:
                node = self._store.get_node(nid)
                if node:
                    node_map[nid] = node

        sections = []
        for node_id, score in ranked:
            node = node_map.get(node_id)
            if node:
                sections.append({
                    "id": node.id,
                    "title": node.title,
                    "content": node.content,
                    "score": round(score, 4),
                    "parent_id": node.parent_id,
                })

        return {
            "sections": sections,
            "triggered": triggered_ids,
            "metadata": {
                "semantic_candidates": len(semantic_scores),
                "triggers_fired": len(triggered_ids),
                "graph_discovered": len(graph_boosts),
            },
        }

    def update(self, query_text: str, retrieved_ids: list[str], useful_ids: list[str]) -> None:
        """Record an episode and run Hebbian learning."""
        query_embedding = self._model.encode_single(query_text)

        episode = Episode(
            context=query_text,
            context_embedding=query_embedding,
            retrieved_ids=retrieved_ids,
            triggered_ids=set(),  # We don't track trigger IDs through the hook boundary
            useful_ids=set(useful_ids),
        )
        self._episode_log.record(episode)
        self._save_episode(episode)

        if self._config.enable_hebbian:
            self._updater.update(episode)
            self._decay.tick()

    def consolidate(self) -> dict:
        """Run consolidation cycle. Returns report."""
        report = self._consolidator.consolidate()
        self._rebuild_caches()
        result = {
            "episodes_replayed": report.episodes_replayed,
            "edges_strengthened": report.edges_strengthened,
            "promotions": len(report.promotions),
            "bridges_created": report.bridges_created,
            "trigger_candidates": report.trigger_candidates,
        }
        result.update(report.decay_summary)
        return result

    def status(self) -> dict:
        """Return stats about this project's memory."""
        all_triggers = self._store.get_all_triggers()
        explicit = sum(1 for t in all_triggers if t.origin == TriggerOrigin.EXPLICIT)
        hebbian = sum(1 for t in all_triggers if t.origin == TriggerOrigin.HEBBIAN)

        return {
            "nodes": self._store.get_node_count(),
            "sections": len(self._section_nodes),
            "edges": self._store.get_edge_count(),
            "triggers_explicit": explicit,
            "triggers_hebbian": hebbian,
            "episodes": len(self._episode_log),
        }


class ProjectManager:
    """Cache of per-project Loqi state, sharing one embedding model."""

    def __init__(self):
        self._model = EmbeddingModel()
        self._config = LOQI_FULL
        self._projects: dict[str, ProjectState] = {}

    def get(self, project_path: str) -> ProjectState:
        """Get or create state for a project."""
        key = os.path.normpath(project_path)
        if key not in self._projects:
            self._projects[key] = ProjectState(key, self._model, self._config)
        return self._projects[key]

    @property
    def model_loaded(self) -> bool:
        """Check if the embedding model has been loaded."""
        return self._model._model is not None
