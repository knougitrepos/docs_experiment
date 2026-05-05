"""Pilot-mode metrics for one experiment run.

The default Research 2 pilot intentionally reports a small, stable metric set:

* build_success
* test_pass_count
* test_total_count
* requirements_satisfied_count
* elapsed_seconds

Legacy fields are still emitted as aliases where possible so older aggregate
artifacts do not become unreadable.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]

from .logger import get_logger
from .stream_parser import parse_stream

logger = get_logger(__name__)


TASK1_REQUIREMENT_IDS = {
    "todo_create",
    "todo_list",
    "todo_get_one",
    "todo_update",
    "todo_delete",
    "invalid_input_handled",
}

LEGACY_ID_ALIASES = {
    "fr_crud_post": "todo_create",
    "fr_crud_list": "todo_list",
    "fr_crud_get_one": "todo_get_one",
    "fr_crud_put": "todo_update",
    "fr_crud_delete": "todo_delete",
    "qual_error_format": "invalid_input_handled",
}


@dataclass
class AcceptanceResult:
    item_id: str
    text: str
    satisfied: bool
    evidence: str
    review_required: bool = False


@dataclass
class MetricResult:
    agent: str = ""
    task_id: str = ""
    condition: str = ""
    model: str = ""
    reasoning_effort: str = "default"
    rep: int = 0

    build_success: bool = False
    test_pass_count: int = 0
    test_total_count: int = 0
    requirements_satisfied_count: int = 0
    elapsed_seconds: float = 0.0

    requirements_total_count: int = 0
    static_analysis_errors_count: int = 0
    ruff_errors: int = 0
    run_status: str = "completed"
    acceptance_checklist_path: str = ""
    errors: list[str] = field(default_factory=list)

    # Backward-compatible aliases for older reports.
    test_pass_rate: float = 0.0
    requirements_fulfillment: float = 0.0
    static_errors_total: int = 0
    static_errors_breakdown: dict[str, int] = field(default_factory=dict)
    wall_seconds: float = 0.0
    pytest_passed: int = 0
    pytest_failed: int = 0
    pytest_errors: int = 0
    pytest_total: int = 0
    coverage_percent: float = 0.0
    checklist_scores: dict[str, int] = field(default_factory=dict)
    judge_success: bool = False
    judge_error: str | None = None
    agent_steps: int = 0
    total_tokens: int = 0
    total_cost_usd: float = 0.0
    input_docs_bytes: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def write_failure_metrics(
    *,
    run_dir: Path,
    task_id: str,
    condition: str,
    model: str,
    rep: int,
    agent: str,
    reasoning_effort: str = "default",
    elapsed_seconds: float = 0.0,
    errors: list[str] | None = None,
) -> MetricResult:
    """Write a minimal metrics.json for a failed or skipped run."""
    res = MetricResult(
        agent=agent,
        task_id=task_id,
        condition=condition,
        model=model,
        reasoning_effort=reasoning_effort,
        rep=rep,
        elapsed_seconds=round(float(elapsed_seconds or 0.0), 2),
        wall_seconds=round(float(elapsed_seconds or 0.0), 2),
        run_status="failed",
        errors=errors or [],
    )
    if task_id == "task-1-todo-crud":
        res.requirements_total_count = 6
    _write_metrics(run_dir, res)
    return res


def evaluate_run(
    *,
    run_dir: Path,
    workspace: Path,
    task_id: str,
    condition: str,
    model: str,
    rep: int,
    repo_root: Path,
    agent: str = "codex",
    reasoning_effort: str = "default",
    use_judge: bool = False,
    judge_model: str = "sonnet",
) -> MetricResult:
    """Evaluate one run and always write metrics.json on success."""
    run_dir.mkdir(parents=True, exist_ok=True)
    res = MetricResult(
        agent=agent,
        task_id=task_id,
        condition=condition,
        model=model,
        reasoning_effort=reasoning_effort,
        rep=rep,
    )

    meta = _read_json(run_dir / "run.meta.json")
    res.elapsed_seconds = round(float(meta.get("wall_seconds") or 0.0), 2)
    res.wall_seconds = res.elapsed_seconds
    meta_errors = meta.get("errors")
    if isinstance(meta_errors, list) and meta_errors:
        res.run_status = "failed"
        res.errors.extend(str(error) for error in meta_errors)
    for exit_field in ("adapter_exit", "pytest_exit", "ruff_exit", "mypy_exit"):
        exit_value = int(meta.get(exit_field) or 0)
        if exit_value != 0:
            res.run_status = "failed"
            res.errors.append(f"{exit_field}={exit_value}")

    pytest = _read_pytest_json(run_dir)
    res.test_pass_count = pytest["passed"]
    res.test_total_count = pytest["total"]
    res.pytest_passed = pytest["passed"]
    res.pytest_failed = pytest["failed"]
    res.pytest_errors = pytest["errors"]
    res.pytest_total = pytest["total"]
    res.coverage_percent = pytest["coverage"]
    res.test_pass_rate = (
        res.test_pass_count / res.test_total_count if res.test_total_count else 0.0
    )

    res.ruff_errors = _read_ruff_count(run_dir)
    res.static_analysis_errors_count = res.ruff_errors
    res.static_errors_total = res.static_analysis_errors_count
    res.static_errors_breakdown = {"ruff": res.ruff_errors}

    res.build_success = _import_smoke(workspace, run_dir)

    stream = parse_stream(run_dir / "stream.jsonl")
    res.agent_steps = stream.tool_calls
    res.total_tokens = stream.total_tokens
    res.total_cost_usd = stream.total_cost_usd

    acceptance = _evaluate_acceptance(repo_root, workspace, task_id)
    res.requirements_total_count = len(acceptance)
    res.requirements_satisfied_count = sum(1 for item in acceptance if item.satisfied)
    res.requirements_fulfillment = (
        res.requirements_satisfied_count / res.requirements_total_count
        if res.requirements_total_count
        else 0.0
    )
    res.checklist_scores = {
        item.item_id: int(item.satisfied)
        for item in acceptance
        if not item.review_required
    }
    res.acceptance_checklist_path = str(
        _write_acceptance_checklist(run_dir, workspace, task_id, acceptance)
    )

    if use_judge:
        _run_optional_judge(
            res=res,
            run_dir=run_dir,
            workspace=workspace,
            repo_root=repo_root,
            acceptance=acceptance,
            judge_model=judge_model,
        )

    res.input_docs_bytes = _sum_docs_bytes(workspace)
    _write_metrics(run_dir, res)
    logger.info(
        "evaluated %s/%s/%s rep=%d: build=%s tests=%d/%d req=%d/%d",
        task_id,
        condition,
        model,
        rep,
        res.build_success,
        res.test_pass_count,
        res.test_total_count,
        res.requirements_satisfied_count,
        res.requirements_total_count,
    )
    return res


def _write_metrics(run_dir: Path, res: MetricResult) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "metrics.json").write_text(
        json.dumps(res.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig", errors="replace"))
    except json.JSONDecodeError as exc:
        logger.warning("cannot parse json %s: %s", path, exc)
        return {}
    return data if isinstance(data, dict) else {}


def _read_pytest_json(run_dir: Path) -> dict[str, int | float]:
    data = _read_json(run_dir / "pytest.json")
    summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
    passed = int(summary.get("passed", 0) or 0)
    failed = int(summary.get("failed", 0) or 0)
    errors = int(summary.get("error", 0) or summary.get("errors", 0) or 0)
    total = int(summary.get("total", passed + failed + errors) or 0)
    coverage = _read_coverage_percent(run_dir / "pytest.log")
    return {
        "passed": passed,
        "failed": failed,
        "errors": errors,
        "total": total,
        "coverage": coverage,
    }


def _read_coverage_percent(log_path: Path) -> float:
    if not log_path.exists():
        return 0.0
    text = log_path.read_text(encoding="utf-8", errors="replace")
    match = re.search(r"TOTAL\s+\d+\s+\d+\s+(\d+)%", text)
    return float(match.group(1)) if match else 0.0


def _read_ruff_count(run_dir: Path) -> int:
    path = run_dir / "ruff.json"
    if not path.exists():
        return 0
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except json.JSONDecodeError:
        logger.warning("ruff.json is not parseable: %s", path)
        return 0
    if isinstance(data, list):
        return len(data)
    if isinstance(data, dict):
        return int(data.get("errors", 0) or data.get("count", 0) or 0)
    return 0


def _import_smoke(workspace: Path, run_dir: Path) -> bool:
    """Use importability as the pilot build signal."""
    log_path = run_dir / "build.log"
    if not workspace.exists():
        log_path.write_text("workspace missing\n", encoding="utf-8")
        return False
    env = {**os.environ, "PYTHONPATH": str(workspace)}
    try:
        proc = subprocess.run(
            [sys.executable, "-c", "import app; print('ok')"],
            cwd=str(workspace),
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=60,
            check=False,
        )
    except Exception as exc:  # noqa: BLE001
        log_path.write_text(f"import smoke crashed: {exc}\n", encoding="utf-8")
        return False
    log_path.write_text(
        f"exit={proc.returncode}\n--- stdout ---\n{proc.stdout}\n--- stderr ---\n{proc.stderr}\n",
        encoding="utf-8",
    )
    return proc.returncode == 0


def _evaluate_acceptance(
    repo_root: Path,
    workspace: Path,
    task_id: str,
) -> list[AcceptanceResult]:
    items = _load_acceptance(repo_root, task_id)
    routes = set(_extract_routes(workspace))
    results: list[AcceptanceResult] = []
    for item in items:
        item_id = str(item.get("id") or "")
        text = str(item.get("text") or item_id)
        canonical_id = LEGACY_ID_ALIASES.get(item_id, item_id)
        satisfied, evidence, review_required = _check_acceptance_item(
            canonical_id,
            routes,
            workspace,
        )
        results.append(
            AcceptanceResult(
                item_id=item_id,
                text=text,
                satisfied=satisfied,
                evidence=evidence,
                review_required=review_required,
            )
        )
    return results


def _load_acceptance(repo_root: Path, task_id: str) -> list[dict[str, Any]]:
    path = repo_root / "experiments" / "prompts" / f"acceptance.{task_id}.yaml"
    if not path.exists():
        logger.warning("acceptance checklist not found: %s", path)
        return []
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    items = data.get("items") if isinstance(data, dict) else []
    return list(items or [])


def _check_acceptance_item(
    item_id: str,
    routes: set[str],
    workspace: Path,
) -> tuple[bool, str, bool]:
    if item_id == "todo_create":
        return _route_result("POST /api/v1/todos", routes)
    if item_id == "todo_list":
        return _route_result("GET /api/v1/todos", routes)
    if item_id == "todo_get_one":
        ok = any(route.startswith("GET /api/v1/todos/") for route in routes)
        return ok, "GET /api/v1/todos/{id}" if ok else "route not found", False
    if item_id == "todo_update":
        ok = any(
            route.startswith("PUT /api/v1/todos/")
            or route.startswith("PATCH /api/v1/todos/")
            for route in routes
        )
        return ok, "PUT/PATCH /api/v1/todos/{id}" if ok else "route not found", False
    if item_id == "todo_delete":
        ok = any(route.startswith("DELETE /api/v1/todos/") for route in routes)
        return ok, "DELETE /api/v1/todos/{id}" if ok else "route not found", False
    if item_id == "invalid_input_handled":
        needles = [
            "HTTPException",
            "status_code=400",
            "status_code=422",
            "ValidationError",
            "Field(",
            "min_length",
            "TODO_NOT_FOUND",
        ]
        ok = _grep_any(workspace / "app", needles)
        evidence = "validation/error handling token found" if ok else "manual review needed"
        return ok, evidence, not ok
    return False, "manual review needed", True


def _route_result(route: str, routes: set[str]) -> tuple[bool, str, bool]:
    return route in routes, route if route in routes else "route not found", False


def _extract_routes(workspace: Path) -> list[str]:
    routes: list[str] = []
    app_dir = workspace / "app"
    if not app_dir.exists():
        return routes
    pattern = re.compile(
        r"@(?:\w+)\.(get|post|put|delete|patch)\s*\(\s*(['\"])(?P<path>[^'\"]+)\2",
        re.IGNORECASE,
    )
    for path in app_dir.rglob("*.py"):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for match in pattern.finditer(text):
            routes.append(f"{match.group(1).upper()} {match.group('path')}")
    return sorted(set(routes))


def _write_acceptance_checklist(
    run_dir: Path,
    workspace: Path,
    task_id: str,
    acceptance: list[AcceptanceResult],
) -> Path:
    path = run_dir / "acceptance_checklist.md"
    lines = [
        f"# Acceptance Checklist - {task_id}",
        "",
        f"Workspace: `{workspace}`",
        "",
        "Review this file before using the run in the report. Auto-checked items can still be corrected manually.",
        "",
    ]
    for item in acceptance:
        checked = "x" if item.satisfied else " "
        review = "manual review required" if item.review_required else "auto check"
        lines.append(f"- [{checked}] {item.text}")
        lines.append(f"  - id: `{item.item_id}`")
        lines.append(f"  - evidence: {item.evidence}")
        lines.append(f"  - review: {review}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _grep_any(base: Path, needles: list[str]) -> bool:
    if not base.exists():
        return False
    for path in base.rglob("*.py"):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if any(needle in text for needle in needles):
            return True
    return False


def _run_optional_judge(
    *,
    res: MetricResult,
    run_dir: Path,
    workspace: Path,
    repo_root: Path,
    acceptance: list[AcceptanceResult],
    judge_model: str,
) -> None:
    """Keep the old LLM judge available, but outside the default path."""
    judge_needed = [
        {"id": item.item_id, "text": item.text}
        for item in acceptance
        if item.review_required
    ]
    if not judge_needed:
        res.judge_success = False
        return
    try:
        from .judge import call_judge  # imported only for opt-in legacy mode
    except Exception as exc:  # noqa: BLE001
        res.judge_error = f"judge import failed: {exc}"
        res.errors.append(res.judge_error)
        return
    try:
        judge = call_judge(
            workspace=workspace,
            rubric_path=repo_root / "experiments" / "prompts" / "judge_rubric.md",
            checklist_items=judge_needed,
            expected_modules=["app"],
            expected_routes=_expected_routes_for_task(res.task_id),
            judge_model=judge_model,
            out_path=run_dir / "judge.json",
        )
    except Exception as exc:  # noqa: BLE001
        res.judge_error = f"judge call failed: {exc}"
        res.errors.append(res.judge_error)
        return
    res.judge_success = judge.success
    res.judge_error = judge.error


def _expected_routes_for_task(task_id: str) -> list[str]:
    if task_id != "task-1-todo-crud":
        return []
    return [
        "POST /api/v1/todos",
        "GET /api/v1/todos",
        "GET /api/v1/todos/{todo_id}",
        "PUT /api/v1/todos/{todo_id}",
        "DELETE /api/v1/todos/{todo_id}",
    ]


def _sum_docs_bytes(workspace: Path) -> int:
    total = 0
    for name in ("REQUIREMENTS.md", "AGENTS.md"):
        path = workspace / name
        if path.exists():
            total += path.stat().st_size
    docs_dir = workspace / "docs"
    if docs_dir.exists():
        for path in docs_dir.rglob("*.md"):
            total += path.stat().st_size
    return total
