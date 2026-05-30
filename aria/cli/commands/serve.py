"""Run the FastAPI app with uvicorn (``api.main:app``)."""

from __future__ import annotations

import os

import typer
import uvicorn


def serve(
    host: str = typer.Option("127.0.0.1", "--host", "-h", help="Bind address."),
    port: int = typer.Option(8080, "--port", "-p", help="Listen port (overridden by API_PORT env var)."),
    reload: bool = typer.Option(False, "--reload", help="Reload on code changes (dev)."),
) -> None:
    """Start the ARIA API server."""
    effective_port = int(os.getenv("API_PORT", str(port)))
    uvicorn.run(
        "api.main:app",
        host=host,
        port=effective_port,
        reload=reload,
    )
