"""Offline evaluation store — append-only JSONL for human review.

Each eval run writes one JSONL file to ``eval_runs/{run_id}.jsonl``.
Records capture the full request/response/trace payload plus automated
check results so reviewers can annotate quality judgments offline.

Usage (CLI)::

    # List runs
    python -m tests.eval.eval_store list

    # Review pending cases in a run
    python -m tests.eval.eval_store review --run-id <run_id>

    # Summarize judgments
    python -m tests.eval.eval_store summary --run-id <run_id>
"""

from __future__ import annotations

import json
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

EVAL_RUNS_DIR = Path(__file__).resolve().parent / "eval_runs"


@dataclass
class EvalRecord:
    """A single evaluation observation.

    Payloads are scrubbed best-effort when emitted from the golden report; do not
    put secrets in golden YAML inputs — treat JSONL as review data, not a vault.
    """

    run_id: str
    correlation_id: str
    case_id: str
    timestamp: str = ""
    request: dict[str, Any] = field(default_factory=dict)
    response: dict[str, Any] = field(default_factory=dict)
    trace: dict[str, Any] = field(default_factory=dict)
    check_results: dict[str, Any] = field(default_factory=dict)
    human_judgment: dict[str, Any] | None = None


class EvalStore:
    """Append-only JSONL store for evaluation records."""

    def __init__(self, output_dir: Path | None = None) -> None:
        self._dir = output_dir or EVAL_RUNS_DIR
        self._dir.mkdir(parents=True, exist_ok=True)

    def _run_path(self, run_id: str) -> Path:
        return self._dir / f"{run_id}.jsonl"

    def append(self, record: EvalRecord) -> None:
        if not record.timestamp:
            record.timestamp = datetime.now(timezone.utc).isoformat()
        path = self._run_path(record.run_id)
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(asdict(record), default=str) + "\n")

    def load_run(self, run_id: str) -> list[EvalRecord]:
        path = self._run_path(run_id)
        if not path.exists():
            return []
        records: list[EvalRecord] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                records.append(EvalRecord(**json.loads(line)))
        return records

    def list_runs(self) -> list[str]:
        return sorted(p.stem for p in self._dir.glob("*.jsonl"))

    def update_judgment(
        self,
        run_id: str,
        case_id: str,
        judgment: dict[str, Any],
    ) -> bool:
        """Update the human_judgment for a specific case in a run.

        Rewrites the JSONL file with the updated record. Returns True if
        the case was found and updated.
        """
        path = self._run_path(run_id)
        if not path.exists():
            return False

        lines = path.read_text(encoding="utf-8").splitlines()
        updated = False
        new_lines: list[str] = []
        for line in lines:
            if not line.strip():
                continue
            record = json.loads(line)
            if record.get("case_id") == case_id:
                record["human_judgment"] = judgment
                updated = True
            new_lines.append(json.dumps(record, default=str))

        if updated:
            path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
        return updated

    def summary(self, run_id: str) -> dict[str, Any]:
        """Aggregate stats for a run."""
        records = self.load_run(run_id)
        total = len(records)
        judged = sum(1 for r in records if r.human_judgment is not None)
        avg_relevance = 0.0
        avg_faithfulness = 0.0
        scored = 0
        for r in records:
            if r.human_judgment:
                rel = r.human_judgment.get("relevance")
                faith = r.human_judgment.get("faithfulness")
                if rel is not None and faith is not None:
                    avg_relevance += float(rel)
                    avg_faithfulness += float(faith)
                    scored += 1
        if scored:
            avg_relevance /= scored
            avg_faithfulness /= scored
        return {
            "run_id": run_id,
            "total_cases": total,
            "judged": judged,
            "pending_review": total - judged,
            "avg_relevance": round(avg_relevance, 2) if scored else None,
            "avg_faithfulness": round(avg_faithfulness, 2) if scored else None,
        }


def _cli_list() -> None:
    store = EvalStore()
    runs = store.list_runs()
    if not runs:
        print("No eval runs found.")
        return
    print(f"{'Run ID':<20} {'Records':<10}")
    print("-" * 30)
    for run_id in runs:
        count = len(store.load_run(run_id))
        print(f"{run_id:<20} {count:<10}")


def _cli_review(run_id: str) -> None:
    store = EvalStore()
    records = store.load_run(run_id)
    if not records:
        print(f"No records found for run '{run_id}'.")
        return

    pending = [r for r in records if r.human_judgment is None]
    if not pending:
        print("All cases have been reviewed.")
        return

    print(f"\n{len(pending)} case(s) pending review:\n")
    for rec in pending:
        print(f"  Case: {rec.case_id}")
        print(f"  Correlation ID: {rec.correlation_id}")
        answer = rec.response.get("answer", "")[:200]
        print(f"  Answer preview: {answer}...")
        print()

        try:
            relevance = input("  Relevance (0-5, or 's' to skip): ").strip()
            if relevance.lower() == "s":
                continue
            faithfulness = input("  Faithfulness (0-5): ").strip()
            notes = input("  Notes (optional): ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nReview interrupted.")
            return

        judgment = {
            "relevance": int(relevance),
            "faithfulness": int(faithfulness),
            "notes": notes or None,
            "reviewed_at": datetime.now(timezone.utc).isoformat(),
        }
        store.update_judgment(run_id, rec.case_id, judgment)
        print(f"  -> Saved judgment for {rec.case_id}\n")


def _cli_summary(run_id: str) -> None:
    store = EvalStore()
    s = store.summary(run_id)
    print(json.dumps(s, indent=2))


def main() -> None:
    args = sys.argv[1:]
    if not args or args[0] == "list":
        _cli_list()
    elif args[0] == "review":
        run_id = args[args.index("--run-id") + 1] if "--run-id" in args else ""
        if not run_id:
            print("Usage: python -m tests.eval.eval_store review --run-id <id>")
            sys.exit(1)
        _cli_review(run_id)
    elif args[0] == "summary":
        run_id = args[args.index("--run-id") + 1] if "--run-id" in args else ""
        if not run_id:
            print("Usage: python -m tests.eval.eval_store summary --run-id <id>")
            sys.exit(1)
        _cli_summary(run_id)
    else:
        print(f"Unknown command: {args[0]}")
        print("Available: list, review, summary")
        sys.exit(1)


if __name__ == "__main__":
    main()
