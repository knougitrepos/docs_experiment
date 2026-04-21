"""aggregate.py — 여러 run 의 metrics.json 을 summary.csv 와 report.md 로 집계.

디렉터리 구조 (run_experiment.ps1 산출):
    results/<run_id>/<agent>/<model>/<cond>/rep<N>/<task>/metrics.json

Usage:
    python aggregate.py --run-root results/20260421_140000
    python aggregate.py --run-root results/20260421_140000 --scope cursor/sonnet
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

import pandas as pd  # type: ignore[import-untyped]

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from lib.logger import get_logger  # noqa: E402

logger = get_logger(__name__)


# ------------------------------------------------------------
# 1) metrics.json 수집
# ------------------------------------------------------------
METRIC_FIELDS = [
    "agent", "task_id", "condition", "model", "rep",
    "requirements_fulfillment",
    "test_pass_rate",
    "build_success",
    "design_alignment",
    "static_errors_total",
    "reprompt_count",
    "manual_fix_proxy",
    "wall_seconds",
    "agent_steps",
    "total_tokens",
    "total_cost_usd",
    "coverage_percent",
    "pytest_passed",
    "pytest_failed",
    "pytest_total",
    "judge_success",
    "input_docs_bytes",
]


def _scan_metrics(run_root: Path, scope: str | None) -> list[dict[str, Any]]:
    """run_root 하위에서 metrics.json 을 모두 수집.

    scope: "<agent>" 또는 "<agent>/<model>" prefix 로 제한.
    """
    rows: list[dict[str, Any]] = []
    base = run_root
    if scope:
        base = run_root / scope
    if not base.exists():
        logger.warning("scope root not found: %s", base)
        return rows

    for p in base.rglob("metrics.json"):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001
            logger.warning("skip unreadable %s: %s", p, exc)
            continue
        # 필드 flatten
        row = {k: data.get(k) for k in METRIC_FIELDS}
        # static_errors breakdown 추가
        brk = data.get("static_errors_breakdown") or {}
        row["ruff_errors"] = brk.get("ruff", 0)
        row["mypy_errors"] = brk.get("mypy", 0)
        row["_metrics_path"] = str(p)
        rows.append(row)
    logger.info("collected %d metrics.json under %s", len(rows), base)
    return rows


# ------------------------------------------------------------
# 2) summary.csv / report.md 작성
# ------------------------------------------------------------
_GROUP_KEYS = ["agent", "model", "condition", "task_id"]
_NUMERIC = [
    "requirements_fulfillment",
    "test_pass_rate",
    "design_alignment",
    "static_errors_total",
    "ruff_errors",
    "mypy_errors",
    "reprompt_count",
    "manual_fix_proxy",
    "wall_seconds",
    "agent_steps",
    "total_tokens",
    "coverage_percent",
    "input_docs_bytes",
]
_BOOLEAN = ["build_success", "judge_success"]


def _write_summary_csv(rows: list[dict[str, Any]], out: Path) -> pd.DataFrame:
    df = pd.DataFrame(rows)
    if df.empty:
        logger.warning("no rows; summary.csv will be empty header only")
        df = pd.DataFrame(columns=METRIC_FIELDS)
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out, index=False, encoding="utf-8-sig")
    logger.info("wrote %s (%d rows)", out, len(df))
    return df


def _aggregate_table(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    grouped = df.groupby(_GROUP_KEYS, dropna=False)

    agg_spec: dict[str, Any] = {}
    for c in _NUMERIC:
        if c in df.columns:
            agg_spec[c] = ["mean", "std", "count"]
    for c in _BOOLEAN:
        if c in df.columns:
            agg_spec[c] = [lambda s: float((s == True).sum()) / max(len(s), 1)]  # noqa: E712

    agg = grouped.agg(agg_spec)
    # flatten column multiindex
    agg.columns = [
        f"{col}_{stat}" if not callable(stat) else f"{col}_rate"
        for col, stat in agg.columns
    ]
    agg = agg.reset_index()
    return agg


def _render_report(run_root: Path, df: pd.DataFrame, out: Path, scope: str | None) -> None:
    lines: list[str] = []
    lines.append(f"# Experiment Aggregate Report — {run_root.name}")
    lines.append("")
    if scope:
        lines.append(f"**Scope**: `{scope}`")
    lines.append(f"**Total runs collected**: {len(df)}")
    lines.append("")

    if df.empty:
        lines.append("_No runs found. Make sure metrics.json files exist._")
        out.write_text("\n".join(lines), encoding="utf-8")
        return

    # 2.1 agent / model 리스트
    agents = sorted(df["agent"].dropna().unique().tolist())
    models = sorted(df["model"].dropna().unique().tolist())
    conds  = sorted(df["condition"].dropna().unique().tolist())
    tasks  = sorted(df["task_id"].dropna().unique().tolist())
    lines.append(f"- agents   : {', '.join(agents) or '-'}")
    lines.append(f"- models   : {', '.join(models) or '-'}")
    lines.append(f"- conditions: {', '.join(conds) or '-'}")
    lines.append(f"- tasks    : {', '.join(tasks) or '-'}")
    lines.append("")

    # 2.2 조건별 평균 (agent/model 고정 관점)
    lines.append("## 1. 조건(Cx) × task 평균 — 핵심 지표")
    lines.append("")
    key_cols = ["agent", "model", "condition", "task_id"]
    value_cols = [
        "requirements_fulfillment",
        "test_pass_rate",
        "design_alignment",
        "static_errors_total",
        "reprompt_count",
        "wall_seconds",
        "total_tokens",
    ]
    value_cols = [c for c in value_cols if c in df.columns]
    if value_cols:
        pivot = (
            df.groupby(key_cols)[value_cols]
            .agg(["mean", "std"])
            .round(3)
        )
        lines.append(_df_to_md(pivot.reset_index()))
        lines.append("")

    # 2.3 조건 heatmap (mean of requirements_fulfillment)
    lines.append("## 2. 요구사항 충족률 히트맵 (agent/model × condition, task 평균)")
    lines.append("")
    if {"requirements_fulfillment"}.issubset(df.columns):
        heat = (
            df.groupby(["agent", "model", "condition"])["requirements_fulfillment"]
            .mean()
            .unstack("condition")
            .round(3)
        )
        lines.append(_df_to_md(heat.reset_index()))
        lines.append("")

    # 2.4 H1 (계층화 효과) 간이 검증: C2 vs C3 mean(req)
    lines.append("## 3. 가설 간이 검증")
    lines.append("")
    mean_by_cond = df.groupby("condition")[value_cols].mean().round(3)
    lines.append("### H1: 계층화/분할이 요구사항 충족률을 높이는가?")
    if "requirements_fulfillment" in mean_by_cond.columns:
        v = mean_by_cond["requirements_fulfillment"].to_dict()
        lines.append("")
        for c in ["C0", "C1", "C2", "C3", "C4"]:
            if c in v:
                lines.append(f"- {c}: {v[c]:.3f}")
        lines.append("")

    lines.append("### H2: 문서가 늘수록 재프롬프트 ↓, agent_steps ↑ 경향?")
    if {"reprompt_count", "agent_steps"}.issubset(df.columns):
        v = df.groupby("condition")[["reprompt_count", "agent_steps"]].mean().round(3)
        lines.append("")
        lines.append(_df_to_md(v.reset_index()))
        lines.append("")

    lines.append("### H3: C4 의 task-2/3 에서 재교정 감소 여부 (C3 대비)")
    if "condition" in df.columns and "task_id" in df.columns:
        sub = df[df["condition"].isin(["C3", "C4"])]
        if not sub.empty and "manual_fix_proxy" in sub.columns:
            v = (
                sub.groupby(["condition", "task_id"])["manual_fix_proxy"]
                .mean()
                .round(3)
                .reset_index()
            )
            lines.append("")
            lines.append(_df_to_md(v))
            lines.append("")

    # 2.5 운영 통계
    lines.append("## 4. 운영 통계 (비용/시간)")
    lines.append("")
    ops_cols = [c for c in ["wall_seconds", "total_tokens", "total_cost_usd", "input_docs_bytes"]
                if c in df.columns]
    if ops_cols:
        v = df.groupby(["agent", "model"])[ops_cols].sum().round(3).reset_index()
        v["hours"] = (v["wall_seconds"] / 3600).round(2) if "wall_seconds" in v.columns else 0
        lines.append(_df_to_md(v))
        lines.append("")

    # 2.6 원시 데이터 포인터
    lines.append("## 5. 원시 데이터")
    lines.append("")
    lines.append(f"- summary.csv 위치: `{out.parent / 'summary.csv'}`")
    lines.append(f"- run_root: `{run_root}`")
    lines.append("- 개별 run 디렉터리에 `metrics.json`, `stream.jsonl`, `pytest.log` 등이 있습니다.")
    lines.append("")

    out.write_text("\n".join(lines), encoding="utf-8")
    logger.info("wrote %s", out)


def _df_to_md(df: pd.DataFrame) -> str:
    """pandas DataFrame 을 GFM 마크다운 표로 변환."""
    if df.empty:
        return "_(empty)_"
    try:
        return df.to_markdown(index=False)
    except Exception:
        # tabulate 없을 때 fallback
        cols = list(df.columns)
        lines = ["| " + " | ".join(map(str, cols)) + " |",
                 "| " + " | ".join(["---"] * len(cols)) + " |"]
        for _, row in df.iterrows():
            lines.append("| " + " | ".join(str(row[c]) for c in cols) + " |")
        return "\n".join(lines)


# ------------------------------------------------------------
# 3) CLI
# ------------------------------------------------------------
def _parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        prog="aggregate.py",
        description="Aggregate metrics.json files under a run_root into summary.csv + report.md",
    )
    ap.add_argument("--run-root", required=True, type=Path,
                    help="run output root (e.g. experiments/results/20260421_140000)")
    ap.add_argument("--scope", default=None,
                    help="optional prefix to limit scan (e.g. cursor/sonnet)")
    ap.add_argument("--out-dir", type=Path, default=None,
                    help="output directory for summary.csv + report.md. "
                         "default: <run-root>[/<scope>]")
    return ap.parse_args()


def main() -> int:
    args = _parse_args()
    if not args.run_root.exists():
        logger.error("run-root not found: %s", args.run_root)
        return 2
    out_dir = args.out_dir
    if out_dir is None:
        out_dir = args.run_root if not args.scope else (args.run_root / args.scope)
    out_dir.mkdir(parents=True, exist_ok=True)

    rows = _scan_metrics(args.run_root, args.scope)
    df = _write_summary_csv(rows, out_dir / "summary.csv")
    _render_report(args.run_root, df, out_dir / "report.md", args.scope)

    # cross-scope 집계 (run_root 하위 전부)
    if args.scope:
        logger.info("also writing cross-scope aggregate under run_root")
        all_rows = _scan_metrics(args.run_root, None)
        all_df = _write_summary_csv(all_rows, args.run_root / "summary.csv")
        _render_report(args.run_root, all_df, args.run_root / "report.md", scope=None)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
