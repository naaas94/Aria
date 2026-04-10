"""Durable ingestion idempotency and progress in Neo4j.

``IngestionRecord`` nodes track whether a content hash finished the full pipeline
and which stages succeeded, so restarts can skip completed work and retries can
resume after partial failures (e.g. graph OK, vector down).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime

from aria.graph.client import Neo4jClient

INGESTION_LABEL = "IngestionRecord"


async def is_pipeline_complete(client: Neo4jClient, content_hash: str) -> bool:
    rows = await client.execute_read(
        f"""
        MATCH (r:{INGESTION_LABEL} {{content_hash: $h}})
        WHERE r.pipeline_complete = true
        RETURN true AS ok
        LIMIT 1
        """,
        {"h": content_hash},
    )
    return bool(rows)


async def iter_complete_content_hashes(
    client: Neo4jClient,
    *,
    batch_size: int = 5000,
) -> AsyncIterator[str]:
    """Yield ``pipeline_complete`` content hashes in lexicographic order, batched.

    Uses cursor pagination so callers can process very large sets without loading
    all rows into memory at once. Prefer :func:`is_pipeline_complete` for
    single-hash idempotency checks (e.g. ingestion dedup).
    """
    if batch_size < 1:
        raise ValueError("batch_size must be at least 1")
    last: str | None = None
    while True:
        rows = await client.execute_read(
            f"""
            MATCH (r:{INGESTION_LABEL})
            WHERE r.pipeline_complete = true
              AND ($last IS NULL OR r.content_hash > $last)
            WITH r ORDER BY r.content_hash
            RETURN r.content_hash AS h
            LIMIT $lim
            """,
            {"last": last, "lim": batch_size},
        )
        batch = [str(row["h"]) for row in rows if row.get("h") is not None]
        if not batch:
            break
        for h in batch:
            yield h
        if len(batch) < batch_size:
            break
        last = batch[-1]


async def upsert_ingestion_progress(
    client: Neo4jClient,
    content_hash: str,
    *,
    graph_indexed: bool,
    vector_indexed: bool,
    pipeline_complete: bool,
) -> None:
    now = datetime.now(UTC).isoformat()
    await client.execute_write(
        f"""
        MERGE (r:{INGESTION_LABEL} {{content_hash: $h}})
        SET r.graph_indexed = $g,
            r.vector_indexed = $v,
            r.pipeline_complete = $p,
            r.updated_at = $t
        """,
        {
            "h": content_hash,
            "g": graph_indexed,
            "v": vector_indexed,
            "p": pipeline_complete,
            "t": now,
        },
    )
