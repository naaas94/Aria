"""Typer entry point for the `aria` console script."""

from __future__ import annotations

import typer
from dotenv import load_dotenv

from aria.cli.commands.eval import run_golden_eval
from aria.cli.commands.impact import impact
from aria.cli.commands.ingest import ingest
from aria.cli.commands.init import init_schema
from aria.cli.commands.query import query
from aria.cli.commands.serve import serve
from aria.cli.commands.status import status
from aria.cli.commands.telemetry_cmd import telemetry_cli

app = typer.Typer(
    name="aria",
    help="ARIA — Automated Regulatory Impact Agent",
    no_args_is_help=True,
)


@app.callback()
def _root() -> None:
    """Load environment defaults from ``.env`` before subcommands run."""
    load_dotenv()


app.command("serve")(serve)
app.command("init")(init_schema)
app.command("ingest")(ingest)
app.command("status")(status)
app.command("query")(query)
app.command("impact")(impact)
app.command("telemetry")(telemetry_cli)
app.command(
    "eval",
    context_settings={"allow_extra_args": True, "ignore_unknown_options": True},
)(run_golden_eval)


def main() -> None:
    """Run the Typer CLI application."""
    app()


if __name__ == "__main__":
    main()
