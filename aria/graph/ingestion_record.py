"""Durable ingestion idempotency and progress in Neo4j.

``IngestionRecord`` nodes track whether a content hash finished the full pipeline
and which stages succeeded, so restarts can skip completed work and retries can
resume after partial failures (e.g. graph OK, vector down).
"""

from __future__ import annotations

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


async def list_complete_content_hashes(client: Neo4jClient) -> list[str]:
    rows = await client.execute_read(
        f"""
        MATCH (r:{INGESTION_LABEL})
        WHERE r.pipeline_complete = true
        RETURN r.content_hash AS h
        """,
    )
    return [str(row["h"]) for row in rows if row.get("h") is not None]


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
