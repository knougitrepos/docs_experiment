"""8개 지표 계산.

지표 번호는 `docs/실험계획서_20260421_v1.md` §6.3 와 일치:
    (1) 요구사항 충족률
    (2) 테스트 통과율
    (3) 빌드 성공 여부
    (4) 설계-구현 일치도
    (5) 정적 분석 오류 수
    (6) 재프롬프트 횟수
    (7) 수동 수정 횟수
    (8) 전체 작업 시간 (wall_sec + agent_steps + tokens)

`evaluate_run` 가 이 모듈의 단일 엔트리포인트다.
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

from .judge import JudgeResult, call_judge
from .logger import get_logger
from .stream_parser import StreamStats, parse_stream

logger = get_logger(__name__)

_ACCEPTANCE_GLOB = "acceptance.{task}.yaml"


@dataclass
class MetricResult:
    # 식별 정보
    agent: str = ""
    task_id: str = ""
    condition: str = ""
    model: str = ""
    reasoning_effort: str = "default"
    rep: int = 0

    # --- 8 지표 ---
    requirements_fulfillment: float = 0.0     # (1) 0..1
    test_pass_rate: float = 0.0               # (2) 0..1 (passed/total)
    build_success: bool = False               # (3)
    design_alignment: float = 0.0             # (4) 0..1
    static_errors_total: int = 0              # (5)
    static_errors_breakdown: dict[str, int] = field(default_factory=dict)
    reprompt_count: int = 0                   # (6)
    manual_fix_proxy: int = 0                 # (7) apply_failed/retry/error events
    wall_seconds: float = 0.0                 # (8)
    agent_steps: int = 0                      # (8)
    total_tokens: int = 0                     # (8)
    total_cost_usd: float = 0.0               # (8)

    # 보조 정보
    coverage_percent: float = 0.0
    pytest_passed: int = 0
    pytest_failed: int = 0
    pytest_errors: int = 0
    pytest_total: int = 0
    checklist_scores: dict[str, int] = field(default_factory=dict)
    judge_success: bool = False
    judge_error: str | None = None
    errors: list[str] = field(default_factory=list)
    input_docs_bytes: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ------------------------------------------------------------
# 개별 지표 계산 helpers
# ------------------------------------------------------------
def _read_pytest_json(run_dir: Path) -> tuple[float, int, int, int, int, float]:
    """pytest --json-report 결과 파싱.

    반환: (pass_rate, passed, failed, errors, total, coverage_percent)
    """
    p = run_dir / "pytest.json"
    if not p.exists():
        logger.warning("pytest.json not found: %s", p)
        return 0.0, 0, 0, 0, 0, 0.0
    try:
        data = json.loads(p.read_text(encoding="utf-8", errors="replace"))
    except json.JSONDecodeError as exc:
        logger.exception("pytest.json parse failed: %s", exc)
        return 0.0, 0, 0, 0, 0, 0.0

    summary = data.get("summary", {}) or {}
    passed = int(summary.get("passed", 0) or 0)
    failed = int(summary.get("failed", 0) or 0)
    errors = int(summary.get("error", 0) or summary.get("errors", 0) or 0)
    total = int(summary.get("total", passed + failed + errors) or 0)
    rate = (passed / total) if total else 0.0

    cov = 0.0
    # coverage 는 pytest-cov 가 summary에 넣지 않을 수 있음 → log 파싱 보강
    cov_log = run_dir / "pytest.log"
    if cov_log.exists():
        text = cov_log.read_text(encoding="utf-8", errors="replace")
        m = re.search(r"TOTAL\s+\d+\s+\d+\s+(\d+)%", text)
        if m:
            cov = float(m.group(1))
    return rate, passed, failed, errors, total, cov


def _read_ruff_count(run_dir: Path) -> int:
    p = run_dir / "ruff.json"
    if not p.exists():
        return 0
    try:
        data = json.loads(p.read_text(encoding="utf-8", errors="replace"))
        if isinstance(data, list):
            return len(data)
        if isinstance(data, dict):
            return int(data.get("errors", 0) or 0)
    except json.JSONDecodeError:
        logger.warning("ruff.json not parseable")
    return 0


def _read_mypy_count(run_dir: Path) -> int:
    p = run_dir / "mypy.txt"
    if not p.exists():
        return 0
    text = p.read_text(encoding="utf-8", errors="replace")
    # "Found N errors in M files"
    m = re.search(r"Found\s+(\d+)\s+error", text)
    if m:
        return int(m.group(1))
    return sum(1 for line in text.splitlines() if ": error:" in line)


def _try_build(ws: Path, run_dir: Path) -> bool:
    """``python -m pip check`` 을 빌드 대용 검증으로 사용.

    실제로 패키지화된 프로젝트가 아닐 수 있으므로, 의존성 해결 + 임포트 smoke 로 판정.
    """
    log = run_dir / "build.log"
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "pip", "check"],
            capture_output=True, text=True, encoding="utf-8", cwd=str(ws), timeout=120,
        )
        log.write_text(
            f"# pip check\nexit={proc.returncode}\n"
            f"---stdout---\n{proc.stdout}\n---stderr---\n{proc.stderr}\n",
            encoding="utf-8",
        )
        pip_ok = proc.returncode == 0
    except Exception as exc:  # noqa: BLE001
        logger.exception("pip check failed: %s", exc)
        pip_ok = False

    # import smoke: app 패키지가 import 되는가
    smoke_ok = False
    try:
        proc = subprocess.run(
            [sys.executable, "-c", "import app; print('ok')"],
            capture_output=True, text=True, encoding="utf-8",
            cwd=str(ws), timeout=60,
            env={**os.environ, "PYTHONPATH": str(ws)},
        )
        smoke_ok = proc.returncode == 0 and "ok" in (proc.stdout or "")
        with log.open("a", encoding="utf-8") as fh:
            fh.write(f"\n# import smoke\nexit={proc.returncode}\n{proc.stdout}\n{proc.stderr}\n")
    except Exception as exc:  # noqa: BLE001
        logger.warning("import smoke failed: %s", exc)

    return pip_ok and smoke_ok


def _extract_routes(ws: Path) -> list[str]:
    """app/ 하위에서 @router.<method>() 또는 @app.<method>() 선언을 rg 스타일로 추출."""
    routes: list[str] = []
    app_dir = ws / "app"
    if not app_dir.exists():
        return routes
    pat = re.compile(
        r"@(?:\w+)\.(get|post|put|delete|patch)\s*\(\s*(['\"])(?P<path>[^'\"]+)\2",
        re.IGNORECASE,
    )
    for root, _dirs, files in os.walk(app_dir):
        for f in files:
            if not f.endswith(".py"):
                continue
            try:
                text = (Path(root) / f).read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            for m in pat.finditer(text):
                routes.append(f"{m.group(1).upper()} {m.group('path')}")
    return sorted(set(routes))


def _load_acceptance(repo_root: Path, task_id: str) -> list[dict[str, Any]]:
    p = repo_root / "experiments" / "prompts" / f"acceptance.{task_id}.yaml"
    if not p.exists():
        logger.warning("acceptance yaml not found: %s", p)
        return []
    data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    return list(data.get("items", []) or [])


def _automated_check_from_results(
    cid: str,
    task_id: str,  # noqa: ARG001
    *,
    pytest_pass_rate: float,
    coverage: float,
    ruff_count: int,
    mypy_count: int,
    routes_found: set[str],
    stream: StreamStats,
    ws: Path,
) -> int | None:
    """자동 판정 가능한 id 는 0/1, 아니면 None (judge 에 위임)."""
    # 공통
    if cid == "nfr_pytest_pass":
        return int(pytest_pass_rate >= 0.999)
    if cid == "nfr_coverage_70":
        return int(coverage >= 70.0)
    if cid == "nfr_ruff_clean":
        return int(ruff_count == 0)
    if cid == "nfr_mypy_low":
        return int(mypy_count <= 3)
    if cid == "nfr_ruff_mypy":
        return int(ruff_count == 0 and mypy_count <= 3)

    # task-1
    if cid == "fr_crud_post":
        return int("POST /api/v1/todos" in routes_found)
    if cid == "fr_crud_get_one":
        return int(any(r.startswith("GET /api/v1/todos/") for r in routes_found))
    if cid == "fr_crud_list":
        return int("GET /api/v1/todos" in routes_found)
    if cid == "fr_crud_put":
        return int(any(r.startswith("PUT /api/v1/todos/") for r in routes_found))
    if cid == "fr_crud_delete":
        return int(any(r.startswith("DELETE /api/v1/todos/") for r in routes_found))
    if cid == "fr_health":
        return int("GET /health" in routes_found)
    if cid == "qual_timestamps":
        return int(_grep_any(ws, ["created_at", "updated_at"]))
    if cid == "qual_error_format":
        return int(_grep_any(ws, ["TODO_NOT_FOUND"]))

    # task-2
    if cid == "fr_register":
        return int("POST /api/v1/auth/register" in routes_found)
    if cid == "fr_login":
        return int("POST /api/v1/auth/login" in routes_found)
    if cid == "fr_me":
        return int("GET /api/v1/auth/me" in routes_found)
    if cid == "fr_users_me":
        return int("GET /api/v1/users/me" in routes_found)
    if cid == "fr_todos_protected":
        return int(_grep_any(ws, ["Depends(get_current_user", "HTTPException(status_code=401", "INVALID_TOKEN"]))
    if cid == "fr_ownership" and "task-3" in task_id:
        return int(_grep_any(ws, ["user_id ==", "== current_user.id"]))
    if cid == "fr_ownership":
        return int(_grep_any(ws, ["user_id ==", "todo.user_id"]))
    if cid == "nfr_hidden_hash":
        return int(_grep_not(ws, ["hashed_password"], scope_glob="app/schemas"))
    if cid == "qual_error_codes":
        return int(_grep_any(ws, ["INVALID_TOKEN", "TODO_NOT_FOUND", "INVALID_CREDENTIALS"]))

    # task-3
    if cid == "fr_params":
        return int(_grep_any(ws, ["page:", "size:", " q:", "completed:"], scope_glob="app/api"))
    if cid == "fr_response_shape":
        return int(_grep_any(ws, ["items", "total", "page", "size"], scope_glob="app/schemas"))
    if cid == "fr_size_cap":
        return int(_grep_any(ws, ["le=100", "<= 100", "max_length=100"]))
    if cid == "fr_page_min":
        return int(_grep_any(ws, ["ge=1", ">= 1"]))
    if cid == "fr_q_filter":
        return int(_grep_any(ws, ["ilike", "lower(", ".contains("]))
    if cid == "fr_completed_filter":
        return int(_grep_any(ws, ["completed ==", "== completed"]))
    if cid == "fr_sort":
        return int(_grep_any(ws, ["order_by", "updated_at.desc"]))


    # NOTE: stream 기반 증거가 필요한 nfr 는 여기 확장 가능
    _ = stream
    return None


def _grep_any(ws: Path, needles: list[str], scope_glob: str | None = None) -> bool:
    """scope 내 py 파일에서 needle 하나라도 있으면 True."""
    base = ws / scope_glob if scope_glob else ws
    base = base if base.exists() else ws
    for root, _dirs, files in os.walk(base):
        for f in files:
            if not f.endswith(".py"):
                continue
            try:
                text = (Path(root) / f).read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            if any(n in text for n in needles):
                return True
    return False


def _grep_not(ws: Path, needles: list[str], scope_glob: str | None) -> bool:
    """scope 내 py 파일에서 needle 모두 없으면 True (즉 '없어야 할 문자열 부재'를 검증)."""
    return not _grep_any(ws, needles, scope_glob=scope_glob)


def _sum_docs_bytes(ws: Path) -> int:
    total = 0
    for name in ("REQUIREMENTS.md", "AGENTS.md"):
        p = ws / name
        if p.exists():
            total += p.stat().st_size
    docs = ws / "docs"
    if docs.exists():
        for root, _dirs, files in os.walk(docs):
            for f in files:
                if f.lower().endswith(".md"):
                    total += (Path(root) / f).stat().st_size
    return total


# ------------------------------------------------------------
# 엔트리포인트
# ------------------------------------------------------------
def evaluate_run(
    *,
    run_dir: Path,
    workspace: Path,
    task_id: str,
    condition: str,
    model: str,
    rep: int,
    repo_root: Path,
    agent: str = "cursor",
    reasoning_effort: str = "default",
    use_judge: bool = True,
    judge_model: str = "sonnet",
) -> MetricResult:
    """단일 run 을 평가해 MetricResult 를 반환하고 metrics.json 으로 저장."""
    res = MetricResult(
        agent=agent, task_id=task_id, condition=condition,
        model=model, reasoning_effort=reasoning_effort, rep=rep,
    )

    # 0) meta 에서 wall_sec
    meta_path = run_dir / "run.meta.json"
    if meta_path.exists():
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8-sig"))
            res.wall_seconds = float(meta.get("wall_seconds") or 0.0)
        except Exception as exc:  # noqa: BLE001
            res.errors.append(f"meta read: {exc}")

    # 1) pytest
    (res.test_pass_rate,
     res.pytest_passed,
     res.pytest_failed,
     res.pytest_errors,
     res.pytest_total,
     res.coverage_percent) = _read_pytest_json(run_dir)

    # 2) ruff + mypy → 지표 5
    ruff_n = _read_ruff_count(run_dir)
    mypy_n = _read_mypy_count(run_dir)
    res.static_errors_total = ruff_n + mypy_n
    res.static_errors_breakdown = {"ruff": ruff_n, "mypy": mypy_n}

    # 3) build
    res.build_success = _try_build(workspace, run_dir)

    # 4) stream 파싱 → 지표 6,7,8 일부
    stream = parse_stream(run_dir / "stream.jsonl")
    res.reprompt_count = max(stream.user_turns - 1, 0)  # 최초 프롬프트 제외
    res.manual_fix_proxy = stream.retry_events + stream.error_events
    res.agent_steps = stream.tool_calls
    res.total_tokens = stream.total_tokens
    res.total_cost_usd = stream.total_cost_usd

    # 5) routes + acceptance checklist 자동 판정 + judge
    routes = set(_extract_routes(workspace))
    items = _load_acceptance(repo_root, task_id)

    auto_scores: dict[str, int] = {}
    judge_needed: list[dict[str, Any]] = []
    for item in items:
        cid = item.get("id")
        if not cid:
            continue
        val = _automated_check_from_results(
            cid=cid,
            task_id=task_id,
            pytest_pass_rate=res.test_pass_rate,
            coverage=res.coverage_percent,
            ruff_count=ruff_n,
            mypy_count=mypy_n,
            routes_found=routes,
            stream=stream,
            ws=workspace,
        )
        if val is None:
            judge_needed.append(item)
        else:
            auto_scores[cid] = int(val)

    judge: JudgeResult = JudgeResult(success=True)
    if use_judge and judge_needed:
        rubric_path = repo_root / "experiments" / "prompts" / "judge_rubric.md"
        judge = call_judge(
            workspace=workspace,
            rubric_path=rubric_path,
            checklist_items=judge_needed,
            expected_modules=[
                "app/api", "app/services", "app/repositories",
                "app/models", "app/schemas", "app/core",
            ],
            expected_routes=_expected_routes_for_task(task_id),
            judge_model=judge_model,
            out_path=run_dir / "judge.json",
        )
        res.judge_success = judge.success
        res.judge_error = judge.error

    # 병합 채점
    total_w = 0.0
    got_w = 0.0
    for item in items:
        cid = item.get("id")
        w = float(item.get("weight", 0.0) or 0.0)
        total_w += w
        score = auto_scores.get(cid)
        if score is None:
            score = int(judge.checklist.get(cid, 0))
        res.checklist_scores[cid] = int(score)
        got_w += w * score

    res.requirements_fulfillment = (got_w / total_w) if total_w else 0.0
    res.design_alignment = float(judge.design_alignment_score)

    # 6) 입력 문서 바이트(조건별 컨텍스트 크기)
    res.input_docs_bytes = _sum_docs_bytes(workspace)

    # 저장
    out = run_dir / "metrics.json"
    out.write_text(json.dumps(res.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info(
        "evaluated %s/%s/%s rep=%d: req=%.2f tests=%.2f static=%d",
        task_id, condition, model, rep,
        res.requirements_fulfillment, res.test_pass_rate, res.static_errors_total,
    )
    return res


def _expected_routes_for_task(task_id: str) -> list[str]:
    base = [
        "POST /api/v1/todos",
        "GET /api/v1/todos/{todo_id}",
        "GET /api/v1/todos",
        "PUT /api/v1/todos/{todo_id}",
        "DELETE /api/v1/todos/{todo_id}",
        "GET /health",
    ]
    if "task-2" in task_id or "task-3" in task_id:
        base += [
            "POST /api/v1/auth/register",
            "POST /api/v1/auth/login",
            "GET /api/v1/auth/me",
            "GET /api/v1/users/me",
        ]
    return base
