"""Evaluate one pilot experiment run and write metrics.json."""

from __future__ import annotations

import argparse
import traceback
from pathlib import Path

from lib.logger import get_logger
from lib.metrics import evaluate_run, write_failure_metrics

logger = get_logger(__name__)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="evaluate.py",
        description="Evaluate one experiment run and always produce metrics.json.",
    )
    parser.add_argument("--run-dir", required=True, type=Path)
    parser.add_argument("--ws", required=True, type=Path)
    parser.add_argument("--task", required=True)
    parser.add_argument("--cond", required=True, choices=["C0", "C1", "C2", "C3", "C4"])
    parser.add_argument("--model", required=True)
    parser.add_argument("--reasoning-effort", default="default")
    parser.add_argument(
        "--agent",
        default="codex",
        choices=["cursor", "codex", "aider", "copilot", "antigravity", "custom", "manual"],
    )
    parser.add_argument("--rep", required=True, type=int)
    parser.add_argument("--repo-root", required=True, type=Path)
    parser.add_argument(
        "--use-judge",
        action="store_true",
        help="Opt in to the legacy LLM judge. Disabled by default for pilot mode.",
    )
    parser.add_argument(
        "--judge-model",
        default="sonnet",
        help="Legacy judge model name, only used with --use-judge.",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    args.run_dir.mkdir(parents=True, exist_ok=True)
    logger.info(
        "evaluate start: run=%s agent=%s model=%s cond=%s rep=%d task=%s judge=%s",
        args.run_dir,
        args.agent,
        args.model,
        args.cond,
        args.rep,
        args.task,
        args.use_judge,
    )

    if not args.ws.exists():
        write_failure_metrics(
            run_dir=args.run_dir,
            task_id=args.task,
            condition=args.cond,
            model=args.model,
            reasoning_effort=args.reasoning_effort,
            rep=args.rep,
            agent=args.agent,
            errors=[f"workspace does not exist: {args.ws}"],
        )
        logger.error("workspace does not exist: %s", args.ws)
        return 1

    try:
        result = evaluate_run(
            run_dir=args.run_dir,
            workspace=args.ws,
            task_id=args.task,
            condition=args.cond,
            model=args.model,
            reasoning_effort=args.reasoning_effort,
            rep=args.rep,
            repo_root=args.repo_root,
            agent=args.agent,
            use_judge=args.use_judge,
            judge_model=args.judge_model,
        )
    except Exception as exc:  # noqa: BLE001
        write_failure_metrics(
            run_dir=args.run_dir,
            task_id=args.task,
            condition=args.cond,
            model=args.model,
            reasoning_effort=args.reasoning_effort,
            rep=args.rep,
            agent=args.agent,
            errors=[f"evaluate crashed: {exc}", traceback.format_exc()],
        )
        logger.exception("evaluate crashed: %s", exc)
        return 1

    logger.info(
        "evaluate done: build=%s tests=%d/%d requirements=%d/%d elapsed=%.2f",
        result.build_success,
        result.test_pass_count,
        result.test_total_count,
        result.requirements_satisfied_count,
        result.requirements_total_count,
        result.elapsed_seconds,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
