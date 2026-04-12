"""Typer entry point for the `aria` console script."""

import typer

app = typer.Typer(
    name="aria",
    help="ARIA — Automated Regulatory Impact Agent",
    no_args_is_help=True,
)


@app.callback()
def _root() -> None:
    """ARIA CLI root group; subcommands are added in later tasks."""


def main() -> None:
    """Run the Typer CLI application."""
    app()


if __name__ == "__main__":
    main()
