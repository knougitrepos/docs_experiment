"""LLM-judge 래퍼.

``cursor-agent -p --force --model <judge-model> --output-format json`` 를
subprocess 로 호출하여, acceptance checklist 의 비-자동 항목과 설계-구현 일치도를 채점한다.

Judge 호출 실패 시, 자동 항목만으로 부분 점수를 반환하고 에러를 남긴다.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .logger import get_logger

logger = get_logger(__name__)

_JUDGE_MODEL_DEFAULT = "sonnet"
_JUDGE_TIMEOUT_SEC = 600


@dataclass
class JudgeResult:
    checklist: dict[str, int] = field(default_factory=dict)  # id -> 0/1
    reasons: dict[str, str] = field(default_factory=dict)
    design_alignment_score: float = 0.0
    modules_missing: list[str] = field(default_factory=list)
    routes_missing: list[str] = field(default_factory=list)
    raw_output: str = ""
    success: bool = False
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "checklist": self.checklist,
            "reasons": self.reasons,
            "design_alignment_score": self.design_alignment_score,
            "modules_missing": self.modules_missing,
            "routes_missing": self.routes_missing,
            "success": self.success,
            "error": self.error,
        }


def _collect_workspace_summary(ws: Path, max_bytes: int = 40_000) -> str:
    """workspace 의 핵심 파일만 골라 judge 에게 투입할 요약 텍스트를 만든다.

    과도한 컨텍스트 누출을 막기 위해 파일 목록 + 상위 몇 개 모듈만 원문 포함.
    """
    lines: list[str] = []
    if not ws.exists():
        return "(workspace not found)"

    # 1) 파일 목록
    tree: list[str] = []
    for root, dirs, files in os.walk(ws):
        # 제외 디렉터리
        dirs[:] = [
            d for d in dirs
            if d not in {".git", "__pycache__", ".venv", ".mypy_cache", ".ruff_cache", ".pytest_cache"}
        ]
        rel = Path(root).relative_to(ws)
        for f in files:
            tree.append(str(rel / f).replace("\\", "/"))
    tree.sort()
    lines.append("# Workspace file tree")
    lines.append("```")
    for p in tree[:200]:
        lines.append(p)
    if len(tree) > 200:
        lines.append(f"... (and {len(tree) - 200} more)")
    lines.append("```")

    # 2) 주요 파일 원문 (app/, tests/ 상위)
    important = [
        p for p in tree
        if p.startswith("app/") or p in {
            "REQUIREMENTS.md", "requirements.txt", "pyproject.toml",
        }
    ][:30]

    buf: list[str] = []
    budget = max_bytes
    for rel in important:
        ap = ws / rel
        try:
            content = ap.read_text(encoding="utf-8", errors="replace")
        except Exception as exc:  # noqa: BLE001
            buf.append(f"\n### {rel}\n(error: {exc})")
            continue
        chunk = content[:4000]
        piece = f"\n### {rel}\n```\n{chunk}\n```"
        if len(piece) > budget:
            piece = piece[:budget] + "\n...[truncated]\n"
        buf.append(piece)
        budget -= len(piece)
        if budget <= 0:
            break

    lines.append("\n# Key files (truncated)")
    lines.extend(buf)
    return "\n".join(lines)


def _build_prompt(
    rubric: str,
    workspace_summary: str,
    checklist_items: list[dict[str, Any]],
    expected_modules: list[str],
    expected_routes: list[str],
) -> str:
    payload = {
        "checklist": [
            {"id": c["id"], "text": c["text"]}
            for c in checklist_items
            if not c.get("automated", True)
        ],
        "expected_modules": expected_modules,
        "expected_routes": expected_routes,
    }
    return (
        rubric
        + "\n\n# 채점 대상\n"
        + "```json\n" + json.dumps(payload, ensure_ascii=False, indent=2) + "\n```\n\n"
        + "# 워크스페이스 요약\n" + workspace_summary
        + "\n\n# 출력\nJSON 한 개만 출력하세요. 설명 문장 포함 금지."
    )


def _extract_json(text: str) -> dict | None:
    """judge 가 JSON 외 텍스트를 섞어 반환하면 첫 JSON 오브젝트만 추출."""
    # 코드펜스 안
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass
    # 맨 밖 중괄호
    try:
        start = text.index("{")
        end = text.rindex("}")
        return json.loads(text[start : end + 1])
    except (ValueError, json.JSONDecodeError):
        return None


def call_judge(
    *,
    workspace: Path,
    rubric_path: Path,
    checklist_items: list[dict[str, Any]],
    expected_modules: list[str],
    expected_routes: list[str],
    judge_model: str = _JUDGE_MODEL_DEFAULT,
    out_path: Path | None = None,
) -> JudgeResult:
    """cursor-agent 로 judge 모델을 1회 호출하고 결과를 파싱."""
    result = JudgeResult()
    rubric = rubric_path.read_text(encoding="utf-8") if rubric_path.exists() else ""
    ws_summary = _collect_workspace_summary(workspace)
    prompt = _build_prompt(
        rubric=rubric,
        workspace_summary=ws_summary,
        checklist_items=checklist_items,
        expected_modules=expected_modules,
        expected_routes=expected_routes,
    )

    if shutil.which("cursor-agent") is None:
        result.error = "cursor-agent not in PATH"
        logger.warning(result.error)
        return result

    try:
        proc = subprocess.run(
            [
                "cursor-agent",
                "-p",
                "--force",
                "--model",
                judge_model,
                "--output-format",
                "json",
                prompt,
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=_JUDGE_TIMEOUT_SEC,
        )
    except subprocess.TimeoutExpired as exc:
        result.error = f"judge timeout: {exc}"
        logger.error(result.error)
        return result
    except Exception as exc:  # noqa: BLE001
        result.error = f"judge invocation failed: {exc}"
        logger.exception(result.error)
        return result

    result.raw_output = proc.stdout or ""
    if out_path is not None:
        out_path.write_text(result.raw_output, encoding="utf-8")
    if proc.returncode != 0:
        result.error = f"judge exit {proc.returncode}: {proc.stderr[:200]}"
        logger.error(result.error)
        return result

    parsed = _extract_json(result.raw_output)
    if parsed is None:
        result.error = "no JSON in judge output"
        logger.error(result.error)
        return result

    for item in parsed.get("checklist", []) or []:
        cid = str(item.get("id", ""))
        score = int(bool(item.get("score", 0)))
        if cid:
            result.checklist[cid] = score
            if (r := item.get("reason")):
                result.reasons[cid] = str(r)[:500]

    da = parsed.get("design_alignment", {}) or {}
    result.design_alignment_score = float(da.get("score", 0.0) or 0.0)
    result.modules_missing = list(da.get("modules_missing", []) or [])
    result.routes_missing = list(da.get("routes_missing", []) or [])
    result.success = True
    return result
