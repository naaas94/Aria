"""Neo4j driver wrapper with connection pooling and health checks."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

from neo4j import AsyncDriver, AsyncGraphDatabase, AsyncSession

from aria.graph.schema import generate_constraint_statements, generate_index_statements

logger = logging.getLogger(__name__)


class Neo4jClient:
    """Thin async wrapper around the Neo4j Python driver."""

    def __init__(self, uri: str, user: str, password: str) -> None:
        self._uri = uri
        self._user = user
        self._password = password
        self._driver: AsyncDriver | None = None

    async def connect(self) -> None:
        self._driver = AsyncGraphDatabase.driver(
            self._uri, auth=(self._user, self._password)
        )
        await self._driver.verify_connectivity()
        logger.info("Connected to Neo4j at %s", self._uri)

    async def close(self) -> None:
        if self._driver:
            await self._driver.close()
            self._driver = None

    @asynccontextmanager
    async def session(self, database: str = "neo4j") -> AsyncIterator[AsyncSession]:
        if not self._driver:
            raise RuntimeError("Neo4jClient is not connected — call connect() first")
        async with self._driver.session(database=database) as session:
            yield session

    async def execute_read(
        self,
        query: str,
        parameters: dict[str, Any] | None = None,
        database: str = "neo4j",
    ) -> list[dict[str, Any]]:
        async with self.session(database) as session:
            result = await session.run(query, parameters or {})
            return [record.data() async for record in result]

    async def execute_write(
        self,
        query: str,
        parameters: dict[str, Any] | None = None,
        database: str = "neo4j",
    ) -> list[dict[str, Any]]:
        async with self.session(database) as session:
            result = await session.run(query, parameters or {})
            return [record.data() async for record in result]

    async def initialize_schema(self) -> None:
        """Create uniqueness constraints and indexes if they don't exist."""
        statements = generate_constraint_statements() + generate_index_statements()
        async with self.session() as session:
            for stmt in statements:
                await session.run(stmt)
        logger.info("Graph schema initialized (%d statements)", len(statements))

    async def health_check(self) -> bool:
        try:
            await self.execute_read("RETURN 1 AS ok")
            return True
        except Exception:
            logger.exception("Neo4j health check failed")
            return False
