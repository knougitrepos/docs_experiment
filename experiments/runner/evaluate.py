"""evaluate.py — 단일 run 평가 진입점.

runner 가 1 회 run 이 끝난 직후 호출. 입력으로 받은 run_dir 의 산출물을 토대로
lib.metrics.evaluate_run 을 실행하고 metrics.json 을 생성한다.

Usage:
    python evaluate.py --run-dir <path> --ws <path> --task <id> --cond C0 \
                       --model sonnet --agent cursor --rep 1 \
                       --repo-root <repo>
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import traceback
from pathlib import Path

# sibling import
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from lib.logger import get_logger  # noqa: E402
from lib.metrics import evaluate_run  # noqa: E402

logger = get_logger(__name__)


def _parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        prog="evaluate.py",
        description="Evaluate a single experiment run and produce metrics.json",
    )
    ap.add_argument("--run-dir", required=True, type=Path,
                    help="run output directory (contains stream.jsonl, pytest.json, ...)")
    ap.add_argument("--ws", required=True, type=Path,
                    help="target workspace path (contains generated app/ + tests/)")
    ap.add_argument("--task", required=True,
                    help="task id (e.g. task-1-todo-crud)")
    ap.add_argument("--cond", required=True, choices=["C0", "C1", "C2", "C3", "C4"],
                    help="condition")
    ap.add_argument("--model", required=True, help="model name (adapter-specific)")
    ap.add_argument("--agent", default="cursor",
                    choices=["cursor", "codex", "aider", "copilot", "custom", "manual"],
                    help="agent adapter that produced the run")
    ap.add_argument("--rep", required=True, type=int, help="repetition index (1-based)")
    ap.add_argument("--repo-root", required=True, type=Path,
                    help="repo root (for acceptance yaml / rubric lookup)")
    ap.add_argument("--no-judge", action="store_true",
                    help="skip LLM judge call (auto-only scoring)")
    ap.add_argument("--judge-model", default=os.environ.get("JUDGE_MODEL", "sonnet"),
                    help="judge model (default sonnet or $JUDGE_MODEL)")
    return ap.parse_args()


def main() -> int:
    args = _parse_args()
    logger.info(
        "evaluate start: run=%s agent=%s model=%s cond=%s rep=%d task=%s",
        args.run_dir, args.agent, args.model, args.cond, args.rep, args.task,
    )

    if not args.run_dir.exists():
        logger.error("run-dir does not exist: %s", args.run_dir)
        return 2
    if not args.ws.exists():
        logger.error("workspace does not exist: %s", args.ws)
        return 2

    try:
        res = evaluate_run(
            run_dir=args.run_dir,
            workspace=args.ws,
            task_id=args.task,
            condition=args.cond,
            model=args.model,
            rep=args.rep,
            repo_root=args.repo_root,
            agent=args.agent,
            use_judge=not args.no_judge,
            judge_model=args.judge_model,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("evaluate_run crashed: %s", exc)
        # 최소한의 실패 스텁을 남긴다(집계가 깨지지 않도록)
        fallback = {
            "agent": args.agent,
            "task_id": args.task,
            "condition": args.cond,
            "model": args.model,
            "rep": args.rep,
            "requirements_fulfillment": 0.0,
            "test_pass_rate": 0.0,
            "build_success": False,
            "design_alignment": 0.0,
            "static_errors_total": 0,
            "reprompt_count": 0,
            "manual_fix_proxy": 0,
            "wall_seconds": 0.0,
            "agent_steps": 0,
            "total_tokens": 0,
            "errors": [f"evaluate crash: {exc}"],
            "traceback": traceback.format_exc(),
        }
        (args.run_dir / "metrics.json").write_text(
            json.dumps(fallback, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return 1

    logger.info(
        "evaluate done: req=%.2f tests=%.2f design=%.2f static=%d",
        res.requirements_fulfillment, res.test_pass_rate,
        res.design_alignment, res.static_errors_total,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
