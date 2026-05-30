#!/usr/bin/env bash
# ARIA MVP+ — Orchestrated query demo
# Requires: docker compose running (neo4j + chromadb), LLM configured, graph populated
# Usage: bash .dev/demo/aria-mvp-demo.sh
# Record: asciinema rec .dev/demo/aria-mvp-demo.cast

set -e

export ARIA_PLACEHOLDER_API=false
export LLM_MODEL=gpt-4o-mini
export LLM_BASE_URL=https://api.openai.com/v1
# For Ollama: export LLM_MODEL=ollama/llama3.1:8b  LLM_BASE_URL=http://localhost:11434

echo "=== ARIA MVP+ Demo: Orchestrated Query ==="
echo

echo "--- 1. Check backends ---"
aria status

echo
echo "--- 2. Standard query (GraphRAG + LLM) ---"
aria query "What are the data minimization requirements?" --json

echo
echo "--- 3. Orchestrated query (multi-agent graph routing + trace) ---"
aria query "What are the data minimization requirements?" --orchestrated --json

echo
echo "--- 4. Telemetry (per-step agent rows for orchestrated run) ---"
aria telemetry --hours 1

echo
echo "=== Demo complete ==="
