# Minor observations (not errors)

Import path nuance: The changelog says routers call services "from aria.services" — the routers actually import from the submodule directly (aria.services.compliance_query, aria.services.impact_report), though the symbols are also re-exported from aria.services.__init__. Not wrong, just a wording simplification.

CLI imports api.*: The changelog says the CLI "does not import api.*" for services — that is true for aria.services, but the CLI commands query.py, impact.py, ingest.py, and status.py do import from api.connections and api.config (for connect_app_dependencies, disconnect_app_dependencies, placeholder_api_enabled). The "no api.* import" claim is specifically about the services layer protocol, not the CLI wiring layer. The changelog could be slightly clearer here, but the intent (services don't depend on Starlette/FastAPI exceptions) is accurately implemented.

aria/cli/commands/__init__.py is a bare docstring-only file. Command registration happens in aria/cli/main.py via explicit imports + app.command(). This is fine structurally.

Ingestion wiring tests: The changelog says "vector indexer threading" is tested. The tests exercise the async callable that internally uses asyncio.to_thread, but don't explicitly mock/assert to_thread itself — they test behavior, not the threading mechanism. Reasonable test design.

aria telemetry exits code 2 on invalid --since, which the changelog correctly states. This is distinct from the other commands' exit-1-on-failure pattern — intentional (input validation vs runtime failure).