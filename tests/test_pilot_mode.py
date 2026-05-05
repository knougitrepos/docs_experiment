from __future__ import annotations

import csv
import json
import shutil
import subprocess
import sys
from pathlib import Path

from experiments.runner.lib.metrics import evaluate_run


REPO_ROOT = Path(__file__).resolve().parents[1]


def _write_task1_acceptance(repo_root: Path) -> None:
    prompt_dir = repo_root / "experiments" / "prompts"
    prompt_dir.mkdir(parents=True)
    (prompt_dir / "acceptance.task-1-todo-crud.yaml").write_text(
        """
task_id: task-1-todo-crud
items:
  - id: todo_create
    text: TODO creation works
  - id: todo_list
    text: TODO list works
  - id: todo_get_one
    text: Single TODO lookup works
  - id: todo_update
    text: TODO update works
  - id: todo_delete
    text: TODO deletion works
  - id: invalid_input_handled
    text: Bad input returns a clear error
""".strip(),
        encoding="utf-8",
    )


def _write_fastapi_workspace(workspace: Path) -> None:
    app_dir = workspace / "app"
    app_dir.mkdir(parents=True)
    (app_dir / "__init__.py").write_text("", encoding="utf-8")
    (app_dir / "main.py").write_text(
        """
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

app = FastAPI()


class TodoWrite(BaseModel):
    title: str = Field(min_length=1)


@app.post("/api/v1/todos", status_code=201)
def create_todo(todo: TodoWrite):
    return todo


@app.get("/api/v1/todos")
def list_todos():
    return []


@app.get("/api/v1/todos/{todo_id}")
def get_todo(todo_id: int):
    raise HTTPException(status_code=404, detail={"code": "TODO_NOT_FOUND"})


@app.put("/api/v1/todos/{todo_id}")
def update_todo(todo_id: int, todo: TodoWrite):
    return todo


@app.delete("/api/v1/todos/{todo_id}", status_code=204)
def delete_todo(todo_id: int):
    return None
""".strip(),
        encoding="utf-8",
    )


def test_evaluate_writes_pilot_metrics_and_acceptance_checklist(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    workspace = tmp_path / "workspace"
    run_dir = tmp_path / "run"
    repo_root.mkdir()
    workspace.mkdir()
    run_dir.mkdir()
    _write_task1_acceptance(repo_root)
    _write_fastapi_workspace(workspace)
    (run_dir / "pytest.json").write_text(
        json.dumps({"summary": {"passed": 5, "failed": 1, "total": 6}}),
        encoding="utf-8",
    )
    (run_dir / "ruff.json").write_text(
        json.dumps([{"code": "F401"}, {"code": "E501"}]),
        encoding="utf-8",
    )
    (run_dir / "run.meta.json").write_text(
        json.dumps({"wall_seconds": 12.34}),
        encoding="utf-8",
    )
    (run_dir / "stream.jsonl").write_text('{"event":"end"}\n', encoding="utf-8")

    result = evaluate_run(
        run_dir=run_dir,
        workspace=workspace,
        task_id="task-1-todo-crud",
        condition="C1",
        model="gpt-5.4-mini",
        rep=1,
        repo_root=repo_root,
        agent="codex",
        reasoning_effort="default",
        use_judge=False,
    )

    metrics = json.loads((run_dir / "metrics.json").read_text(encoding="utf-8"))
    checklist = (run_dir / "acceptance_checklist.md").read_text(encoding="utf-8")
    assert result.requirements_satisfied_count == 6
    assert metrics["build_success"] is True
    assert metrics["test_pass_count"] == 5
    assert metrics["test_total_count"] == 6
    assert metrics["requirements_satisfied_count"] == 6
    assert metrics["elapsed_seconds"] == 12.34
    assert metrics["static_analysis_errors_count"] == 2
    assert "TODO creation works" in checklist
    assert "- [x]" in checklist
    assert not (run_dir / "judge.json").exists()


def test_aggregate_writes_pilot_summary_and_report(tmp_path: Path) -> None:
    run_root = tmp_path / "results" / "pilot"
    for cond, passed in [("C0", 2), ("C1", 4), ("C3", 6)]:
        metrics_dir = run_root / "codex" / "gpt-5.4-mini" / cond / "rep1" / "task-1-todo-crud"
        metrics_dir.mkdir(parents=True)
        (metrics_dir / "metrics.json").write_text(
            json.dumps(
                {
                    "agent": "codex",
                    "model": "gpt-5.4-mini",
                    "reasoning_effort": "default",
                    "condition": cond,
                    "task_id": "task-1-todo-crud",
                    "rep": 1,
                    "build_success": cond != "C0",
                    "test_pass_count": passed,
                    "test_total_count": 6,
                    "requirements_satisfied_count": passed,
                    "requirements_total_count": 6,
                    "elapsed_seconds": 10 + passed,
                }
            ),
            encoding="utf-8",
        )

    proc = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "experiments" / "runner" / "aggregate.py"),
            "--run-root",
            str(run_root),
        ],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert proc.returncode == 0, proc.stderr
    rows = list(csv.DictReader((run_root / "summary.csv").open(encoding="utf-8-sig")))
    report = (run_root / "report.md").read_text(encoding="utf-8")
    assert [row["condition"] for row in rows] == ["C0", "C1", "C3"]
    assert "Research 2 Pilot Condition Comparison" in report
    assert "| C0 " in report
    assert "| C1 " in report
    assert "| C3 " in report


def test_run_experiment_dryrun_defaults_to_research2_pilot(tmp_path: Path) -> None:
    powershell = shutil.which("powershell")
    if powershell is None:
        powershell = shutil.which("pwsh")
    if powershell is None:
        return

    proc = subprocess.run(
        [
            powershell,
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(REPO_ROOT / "experiments" / "runner" / "run_experiment.ps1"),
            "-DryRun",
            "-OutputRoot",
            str(tmp_path / "results"),
            "-RunId",
            "pytest-pilot-dryrun",
        ],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert proc.returncode == 0, proc.stderr
    assert "mode           : pilot" in proc.stdout
    assert "conditions     : C0, C1, C3" in proc.stdout
    assert "tasks          : task-1-todo-crud" in proc.stdout
    assert "repeats        : 1" in proc.stdout
