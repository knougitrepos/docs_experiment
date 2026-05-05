# 연구2 파일럿 실행 방법

연구2 기본 실행은 전체 C0-C4 자동화 실험이 아니라 소규모 파일럿이다.

- 비교 조건: C0, C1, C3
- task: task-1-todo-crud
- agent: codex 기본, manual 선택 가능
- 반복 횟수: 기본 1회
- LLM judge: 기본 실행에서 제외
- C4 continual-learning: 기본 실행에서 제외, legacy/optional 경로로만 유지

## 실행 전 확인

PowerShell에서 저장소 루트로 이동한다.

```powershell
cd C:\git\docs_experiment
.\.venv\Scripts\python.exe --version
.\.venv\Scripts\Activate.ps1
```

먼저 실행 계획만 확인한다.

```powershell
.\experiments\runner\run_experiment.ps1 -DryRun
```

기본값으로 실행하면 C0, C1, C3과 task-1-todo-crud만 1회 실행한다.

```powershell
.\experiments\runner\run_experiment.ps1
```

Codex를 쓰지 않고 사람이 데스크탑 Agent에서 직접 작업하려면 manual adapter를 선택한다.

```powershell
.\experiments\runner\run_experiment.ps1 -Agent manual -Model manual
```

## 검증 명령어

저장소 자체의 runner 테스트와 정적 분석은 다음 명령으로 확인한다.

```powershell
pytest -p no:xdist
ruff check .
python experiments/runner/aggregate.py --run-root experiments/results/<RunId>
```

Windows PowerShell에서는 pytest에 반드시 `-p no:xdist`를 사용한다. 이 저장소의 `pytest.ini`에도 같은 옵션을 기본값으로 둔다. 가상환경을 활성화하지 않은 셸에서는 `python` 대신 `.\.venv\Scripts\python.exe`를 사용한다.

## 결과 확인

각 실행은 `experiments/results/<RunId>/` 아래에 저장된다. 연구2 보고서에 사용할 요약은 다음 파일에서 확인한다.

- `summary.csv`
- `report.md`
- 각 run 디렉터리의 `metrics.json`
- 각 run 디렉터리의 `acceptance_checklist.md`

기본 핵심 지표는 `build_success`, `test_pass_count`, `test_total_count`, `requirements_satisfied_count`, `elapsed_seconds`이다. `ruff` 오류 수는 보조 지표로 기록된다.
