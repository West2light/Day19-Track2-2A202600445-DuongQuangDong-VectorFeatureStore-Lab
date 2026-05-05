#!/usr/bin/env python3
"""Demo script — 5 queries showcasing HybridMemoryAgent.

Run:  python bonus/demo.py
Exit: 0 on success.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Ensure project root is on sys.path so `from bonus.agent import ...` works
# when running as `python bonus/demo.py` from repo root.
_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

from bonus.agent import HybridMemoryAgent  # noqa: E402


def main() -> None:
    print("=" * 70)
    print("Bonus Demo — HybridMemoryAgent (5 queries)")
    print("=" * 70)

    # ── Setup agent ──────────────────────────────────────────────────────
    print("\n[init] Building HybridMemoryAgent (embedding model load ~10s)...")
    agent = HybridMemoryAgent()

    # ── Seed episodic memories ───────────────────────────────────────────
    memories = [
        "Kubernetes supports horizontal pod autoscaling based on CPU and memory metrics. "
        "The HPA controller checks metrics every 15 seconds by default.",

        "Cloud security best practices include network segmentation, IAM least-privilege, "
        "encryption at rest and in transit, and continuous monitoring with SIEM tools.",

        "Terraform is an infrastructure-as-code tool that uses declarative HCL configuration. "
        "It supports multi-cloud deployments across AWS, GCP, and Azure.",

        "Vietnamese NLP faces challenges with word segmentation because Vietnamese words are "
        "multi-syllable but written as space-separated syllables. Tools like underthesea and "
        "pyvi provide tokenization for Vietnamese text processing.",

        "Docker containers package applications with their dependencies. Docker Compose "
        "orchestrates multi-container setups. Kubernetes manages containers at scale.",

        "Serverless computing with AWS Lambda or Google Cloud Functions eliminates server "
        "management. Cold starts can add 100-500ms latency on first invocation.",

        "CI/CD pipelines automate build, test, and deploy. GitHub Actions and GitLab CI "
        "are popular choices. Blue-green deployments reduce downtime risk.",

        "Vector databases like Qdrant, Pinecone, and Weaviate enable similarity search "
        "on high-dimensional embeddings. They are essential for RAG pipelines.",
    ]
    print(f"[seed] Remembering {len(memories)} documents...")
    for mem in memories:
        agent.remember(mem, user_id="u_001")
    print(f"[seed] Done — {len(memories)} memories stored.\n")

    # ── 5 Demo Queries ───────────────────────────────────────────────────
    queries = [
        # Q1: simple vector hit — should find Kubernetes autoscaling memory
        ("Q1 — Simple vector hit (Kubernetes)",
         "Tôi đã đọc gì về Kubernetes?"),

        # Q2: needs profile context — topic_affinity used for recommendation
        ("Q2 — Profile-aware recommendation",
         "Recommend đọc gì tiếp theo cho tôi?"),

        # Q3: needs recent activity — queries_last_hour
        ("Q3 — Recent activity awareness",
         "Tôi đang quan tâm gì gần đây?"),

        # Q4: paraphrase (vector wins) — no keyword "autoscaling" in query
        ("Q4 — Paraphrase query (vector wins)",
         "Tài liệu về tự động mở rộng hạ tầng?"),

        # Q5: mixed (hybrid + profile) — combines keyword "cloud" + semantic "security"
        ("Q5 — Mixed: hybrid + profile",
         "Cho tôi summary về cloud security"),
    ]

    for label, query in queries:
        print("-" * 70)
        print(f"  {label}")
        print(f"  Query: \"{query}\"")
        print("-" * 70)
        context = agent.recall(query, user_id="u_001")
        print(context)
        print()

    print("=" * 70)
    print("All 5 queries completed successfully.")
    print("=" * 70)


if __name__ == "__main__":
    main()
