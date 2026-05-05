"""Aggregate pilot metrics.json files into summary.csv and report.md."""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path
from statistics import mean
from typing import Any

from lib.logger import get_logger

logger = get_logger(__name__)

PILOT_CONDITIONS = ["C0", "C1", "C3"]
SUMMARY_FIELDS = [
    "agent",
    "model",
    "reasoning_effort",
    "condition",
    "task_id",
    "rep",
    "build_success",
    "test_pass_count",
    "test_total_count",
    "requirements_satisfied_count",
    "requirements_total_count",
    "elapsed_seconds",
    "static_analysis_errors_count",
    "ruff_errors",
    "run_status",
    "metrics_path",
]


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="aggregate.py",
        description="Collect metrics.json under a result root and write summary.csv + report.md.",
    )
    parser.add_argument("--run-root", required=True, type=Path)
    parser.add_argument("--scope", default=None, help="Optional prefix such as codex/gpt-5.4-mini")
    parser.add_argument("--out-dir", type=Path, default=None)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    if not args.run_root.exists():
        logger.error("run-root not found: %s", args.run_root)
        return 2

    out_dir = args.out_dir
    if out_dir is None:
        out_dir = args.run_root if not args.scope else args.run_root / args.scope
    out_dir.mkdir(parents=True, exist_ok=True)

    rows = _scan_metrics(args.run_root, args.scope)
    _write_summary_csv(rows, out_dir / "summary.csv")
    _write_report(args.run_root, out_dir / "report.md", rows, args.scope)

    if args.scope:
        all_rows = _scan_metrics(args.run_root, None)
        _write_summary_csv(all_rows, args.run_root / "summary.csv")
        _write_report(args.run_root, args.run_root / "report.md", all_rows, None)
    return 0


def _scan_metrics(run_root: Path, scope: str | None) -> list[dict[str, Any]]:
    base = run_root / scope if scope else run_root
    if not base.exists():
        logger.warning("scope root not found: %s", base)
        return []

    rows: list[dict[str, Any]] = []
    for path in base.rglob("metrics.json"):
        try:
            raw = json.loads(path.read_text(encoding="utf-8-sig"))
        except Exception as exc:  # noqa: BLE001
            logger.warning("skip unreadable metrics %s: %s", path, exc)
            continue
        if isinstance(raw, dict):
            rows.append(_normalize_row(raw, path))
    rows.sort(key=_sort_key)
    logger.info("collected %d metrics.json under %s", len(rows), base)
    return rows


def _normalize_row(data: dict[str, Any], path: Path) -> dict[str, Any]:
    test_pass_count = data.get("test_pass_count", data.get("pytest_passed", 0))
    test_total_count = data.get("test_total_count", data.get("pytest_total", 0))
    elapsed_seconds = data.get("elapsed_seconds", data.get("wall_seconds", 0.0))
    static_errors = data.get("static_analysis_errors_count", data.get("static_errors_total", 0))
    ruff_errors = data.get("ruff_errors")
    if ruff_errors is None:
        breakdown = data.get("static_errors_breakdown")
        ruff_errors = breakdown.get("ruff", 0) if isinstance(breakdown, dict) else 0
    requirements_total = data.get("requirements_total_count", 0)
    requirements_satisfied = data.get("requirements_satisfied_count")
    if requirements_satisfied is None:
        requirements_satisfied = data.get("requirements_fulfillment", 0)

    row = {
        "agent": data.get("agent", ""),
        "model": data.get("model", ""),
        "reasoning_effort": data.get("reasoning_effort") or "default",
        "condition": data.get("condition", ""),
        "task_id": data.get("task_id", ""),
        "rep": data.get("rep", ""),
        "build_success": bool(data.get("build_success", False)),
        "test_pass_count": _to_number(test_pass_count),
        "test_total_count": _to_number(test_total_count),
        "requirements_satisfied_count": _to_number(requirements_satisfied),
        "requirements_total_count": _to_number(requirements_total),
        "elapsed_seconds": _to_number(elapsed_seconds),
        "static_analysis_errors_count": _to_number(static_errors),
        "ruff_errors": _to_number(ruff_errors),
        "run_status": data.get("run_status") or "completed",
        "metrics_path": str(path),
    }
    return row


def _sort_key(row: dict[str, Any]) -> tuple[Any, ...]:
    condition = str(row.get("condition", ""))
    condition_idx = {"C0": 0, "C1": 1, "C2": 2, "C3": 3, "C4": 4}.get(condition, 99)
    return (
        str(row.get("agent", "")),
        str(row.get("model", "")),
        str(row.get("reasoning_effort", "")),
        condition_idx,
        str(row.get("task_id", "")),
        str(row.get("rep", "")),
    )


def _to_number(value: Any) -> float | int:
    if value is None or value == "":
        return 0
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        return value
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0
    return int(number) if number.is_integer() else number


def _write_summary_csv(rows: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=SUMMARY_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in SUMMARY_FIELDS})
    logger.info("wrote %s (%d rows)", path, len(rows))


def _write_report(
    run_root: Path,
    path: Path,
    rows: list[dict[str, Any]],
    scope: str | None,
) -> None:
    lines = [
        f"# Research 2 Pilot Report - {run_root.name}",
        "",
        "Default pilot scope: C0, C1, C3 / task-1-todo-crud / no LLM judge.",
        "",
    ]
    if scope:
        lines.extend([f"Scope: `{scope}`", ""])
    lines.extend([f"Total metrics collected: {len(rows)}", ""])

    lines.extend(
        [
            "## Research 2 Pilot Condition Comparison",
            "",
            _condition_table(rows),
            "",
            "## Run Details",
            "",
            _run_table(rows),
            "",
            "## Files",
            "",
            f"- summary.csv: `{path.parent / 'summary.csv'}`",
            f"- report.md: `{path}`",
            f"- run_root: `{run_root}`",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")
    logger.info("wrote %s", path)


def _condition_table(rows: list[dict[str, Any]]) -> str:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if row.get("condition") in PILOT_CONDITIONS:
            grouped[str(row["condition"])].append(row)

    table_rows: list[list[str]] = []
    for condition in PILOT_CONDITIONS:
        condition_rows = grouped.get(condition, [])
        if not condition_rows:
            table_rows.append([condition, "0", "-", "-", "-", "-", "-", "-"])
            continue
        table_rows.append(
            [
                condition,
                str(len(condition_rows)),
                _fmt(sum(1 for row in condition_rows if row["build_success"]) / len(condition_rows)),
                _fmt(mean(float(row["test_pass_count"]) for row in condition_rows)),
                _fmt(mean(float(row["test_total_count"]) for row in condition_rows)),
                _fmt(mean(float(row["requirements_satisfied_count"]) for row in condition_rows)),
                _fmt(mean(float(row["requirements_total_count"]) for row in condition_rows)),
                _fmt(mean(float(row["elapsed_seconds"]) for row in condition_rows)),
            ]
        )
    return _markdown_table(
        [
            "condition",
            "runs",
            "build_success_rate",
            "avg_test_pass",
            "avg_test_total",
            "avg_req_satisfied",
            "avg_req_total",
            "avg_elapsed_sec",
        ],
        table_rows,
    )


def _run_table(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "_No metrics.json files found._"
    table_rows = [
        [
            str(row["condition"]),
            str(row["agent"]),
            str(row["model"]),
            str(row["task_id"]),
            str(row["rep"]),
            str(row["build_success"]),
            f"{row['test_pass_count']}/{row['test_total_count']}",
            f"{row['requirements_satisfied_count']}/{row['requirements_total_count']}",
            _fmt(float(row["elapsed_seconds"])),
            str(row["run_status"]),
        ]
        for row in rows
    ]
    return _markdown_table(
        [
            "condition",
            "agent",
            "model",
            "task",
            "rep",
            "build",
            "tests",
            "requirements",
            "elapsed",
            "status",
        ],
        table_rows,
    )


def _markdown_table(headers: list[str], rows: list[list[str]]) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)


def _fmt(value: float) -> str:
    return f"{value:.2f}"


if __name__ == "__main__":
    raise SystemExit(main())
