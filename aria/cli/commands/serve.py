"""Run the FastAPI app with uvicorn (``api.main:app``)."""

from __future__ import annotations

import typer
import uvicorn


def serve(
    host: str = typer.Option("127.0.0.1", "--host", "-h", help="Bind address."),
    port: int = typer.Option(8000, "--port", "-p", help="Listen port."),
    reload: bool = typer.Option(False, "--reload", help="Reload on code changes (dev)."),
) -> None:
    """Start the ARIA API server."""
    uvicorn.run(
        "api.main:app",
        host=host,
        port=port,
        reload=reload,
    )
