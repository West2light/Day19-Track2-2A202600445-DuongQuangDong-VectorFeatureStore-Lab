"""HybridMemoryAgent — combines episodic memory (Qdrant) with user profile (Feast).

Usage:
    agent = HybridMemoryAgent()
    agent.remember("Kubernetes supports auto-scaling pods based on CPU usage.", user_id="u_001")
    context = agent.recall("How does auto-scaling work?", user_id="u_001")
    print(context)
"""
from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Optional

from fastembed import TextEmbedding
from feast import FeatureStore
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    PointStruct,
    VectorParams,
)
from rank_bm25 import BM25Okapi

EMBED_MODEL = "BAAI/bge-small-en-v1.5"
EMBED_DIM = 384
COLLECTION = "episodic_memory"
CHUNK_MAX_TOKENS = 300
CHUNK_OVERLAP_TOKENS = 50
RRF_K = 60

_ROOT = Path(__file__).resolve().parent.parent
_FEAST_REPO = _ROOT / "app" / "feast_repo"


class HybridMemoryAgent:
    """Minimal POC: episodic vector memory + Feast user profile."""

    def __init__(self, feast_repo_path: Optional[Path] = None) -> None:
        self._embedder = TextEmbedding(model_name=EMBED_MODEL)
        self._client = QdrantClient(":memory:")
        self._client.create_collection(
            collection_name=COLLECTION,
            vectors_config=VectorParams(size=EMBED_DIM, distance=Distance.COSINE),
        )

        # BM25 state — rebuilt on every remember() call for simplicity.
        self._chunks: list[dict] = []  # {"id": str, "text": str, "user_id": str}
        self._bm25: Optional[BM25Okapi] = None

        # Feast — optional, graceful fallback if not materialized.
        self._feast: Optional[FeatureStore] = None
        repo = feast_repo_path or _FEAST_REPO
        if (repo / "feature_store.yaml").exists():
            try:
                self._feast = FeatureStore(repo_path=str(repo))
            except Exception:
                self._feast = None

    # ── Chunking ─────────────────────────────────────────────────────────
    @staticmethod
    def _chunk_text(text: str, max_tokens: int = CHUNK_MAX_TOKENS,
                    overlap: int = CHUNK_OVERLAP_TOKENS) -> list[str]:
        """Split text into token-bounded chunks with overlap."""
        words = text.split()
        if len(words) <= max_tokens:
            return [text]
        chunks = []
        start = 0
        while start < len(words):
            end = min(start + max_tokens, len(words))
            chunks.append(" ".join(words[start:end]))
            start += max_tokens - overlap
        return chunks

    # ── Remember ─────────────────────────────────────────────────────────
    def remember(self, text: str, user_id: str = "u_001") -> None:
        """Chunk text → embed → upsert to Qdrant with user_id filter."""
        chunks = self._chunk_text(text)
        points: list[PointStruct] = []

        vectors = list(self._embedder.embed(chunks))
        for chunk_text, vec in zip(chunks, vectors):
            chunk_id = str(uuid.uuid4())
            entry = {"id": chunk_id, "text": chunk_text, "user_id": user_id}
            self._chunks.append(entry)
            points.append(PointStruct(
                id=chunk_id,
                vector=vec.tolist(),
                payload={"text": chunk_text, "user_id": user_id},
            ))

        self._client.upsert(collection_name=COLLECTION, points=points)

        # Rebuild BM25 on all chunks (simple; production would use incremental).
        self._bm25 = BM25Okapi([c["text"].lower().split() for c in self._chunks])

    # ── Recall ───────────────────────────────────────────────────────────
    def recall(self, query: str, user_id: str = "u_001", top_k: int = 3) -> str:
        """Hybrid search + user profile → assembled context string."""
        # 1. Feast online lookup (graceful fallback).
        profile = self._get_user_profile(user_id)

        # 2. Hybrid search filtered by user_id.
        memories = self._hybrid_search(query, user_id, top_k)

        # 3. Assemble context.
        mem_text = "\n".join(
            f"  [{i+1}] {m['text'][:200]}" for i, m in enumerate(memories)
        )
        if not mem_text:
            mem_text = "  (no memories found)"

        context = (
            f"=== User Profile ===\n"
            f"  user_id: {user_id}\n"
            f"  topic_affinity: {profile.get('topic_affinity', 'unknown')}\n"
            f"  preferred_language: {profile.get('preferred_language', 'unknown')}\n"
            f"  reading_speed_wpm: {profile.get('reading_speed_wpm', 'unknown')}\n"
            f"  queries_last_hour: {profile.get('queries_last_hour', 'unknown')}\n"
            f"\n=== Top-{top_k} Episodic Memories ===\n"
            f"{mem_text}\n"
            f"\n=== Query ===\n"
            f"  {query}"
        )
        return context

    # ── Internal helpers ─────────────────────────────────────────────────
    def _get_user_profile(self, user_id: str) -> dict:
        """Fetch profile + activity features from Feast online store."""
        if self._feast is None:
            return {}
        try:
            features = self._feast.get_online_features(
                features=[
                    "user_profile_features:reading_speed_wpm",
                    "user_profile_features:preferred_language",
                    "user_profile_features:topic_affinity",
                    "query_velocity_features:queries_last_hour",
                    "query_velocity_features:distinct_topics_24h",
                ],
                entity_rows=[{"user_id": user_id}],
            ).to_dict()
            return {k: v[0] for k, v in features.items() if v[0] is not None}
        except Exception:
            return {}

    def _hybrid_search(self, query: str, user_id: str, top_k: int) -> list[dict]:
        """BM25 + vector → RRF merge, filtered by user_id."""
        if not self._chunks:
            return []

        depth = max(top_k * 5, 20)
        kw_hits = self._search_keyword(query, user_id, depth)
        sem_hits = self._search_semantic(query, user_id, depth)

        # RRF fusion (1-based ranks).
        rrf: dict[str, float] = {}
        meta: dict[str, dict] = {}
        for hits in (kw_hits, sem_hits):
            for rank, h in enumerate(hits, start=1):
                key = h["id"]
                rrf[key] = rrf.get(key, 0.0) + 1.0 / (RRF_K + rank)
                meta.setdefault(key, h)

        ordered = sorted(rrf.items(), key=lambda kv: -kv[1])[:top_k]
        return [meta[doc_id] for doc_id, _ in ordered]

    def _search_keyword(self, query: str, user_id: str, top_k: int) -> list[dict]:
        if self._bm25 is None:
            return []
        scores = self._bm25.get_scores(query.lower().split())
        user_indices = [i for i, c in enumerate(self._chunks) if c["user_id"] == user_id]
        ranked = sorted(user_indices, key=lambda i: -scores[i])[:top_k]
        return [self._chunks[i] for i in ranked]

    def _search_semantic(self, query: str, user_id: str, top_k: int) -> list[dict]:
        q_vec = next(self._embedder.embed([query])).tolist()
        result = self._client.query_points(
            collection_name=COLLECTION,
            query=q_vec,
            query_filter=Filter(must=[
                FieldCondition(key="user_id", match=MatchValue(value=user_id)),
            ]),
            limit=top_k,
        )
        return [
            {"id": str(p.id), "text": p.payload["text"], "user_id": p.payload["user_id"]}
            for p in result.points
        ]
