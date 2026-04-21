# 참조 문서 구조에 따른 LLM 기반 코드 생성 결과 양상 비교

> 5가지 문서 참조 조건(C0~C4)을 동일 task/프롬프트로 돌려 비교하는 실험 레포.
>
> **한 번의 실행 = 하나의 (agent, model)**. 여러 모델을 한 번에 돌리지 않습니다.
> Cursor / Codex / Aider / Copilot / custom / manual 어댑터를 통해 **각 구독의 잔여 토큰을 분산 소진**하며, 같은 `RunId` 로 묶어 한 run 으로 병합 집계합니다.

## 실험 조건 (C0~C4)

| ID | 이름 | 제공 문서 | 비고 |
|---|---|---|---|
| C0 | Bare | 없음 | baseline |
| C1 | SingleReq | `REQUIREMENTS.md` 단일 파일 | |
| C2 | Split | requirements + architecture + api + db | |
| C3 | StructuredDocs | `docs/` 계층 + 루트 `AGENTS.md` | |
| C4 | ContinualDocs | C3 + `continual-learning` 플러그인 | rep 당 task-1→2→3 연속 실행 |

## 지원 에이전트 어댑터

| Agent   | 기본 호출                                                                           | 인증 |
|---------|-------------------------------------------------------------------------------------|---|
| `cursor`  | `cursor-agent -p --force --model <M> --output-format stream-json`                   | `CURSOR_API_KEY` |
| `codex`   | `codex exec --model <M> --json`                                                      | `OPENAI_API_KEY` |
| `aider`   | `aider --model <M> --yes --no-pretty --no-stream --no-auto-commits --message-file …` | provider 환경변수 |
| `copilot` | `gh copilot suggest -t shell "…"` (정보성, 보통 `manual` 권장)                      | `gh auth login` |
| `custom`  | `-CustomCmd '<template>'` 로 임의 CLI 주입                                            | 사용자 책임 |
| `manual`  | 워크스페이스만 준비, 사용자가 IDE 대화형 에이전트로 직접 작업                          | 해당 IDE |

자세한 규약은 `experiments/runner/agents/README.md`.

## 빠른 시작

### 0) 준비

```powershell
# 레포 클론 후
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# 사용할 에이전트만 설치 (예: Cursor CLI)
irm 'https://cursor.com/install?win32=true' | iex
$env:CURSOR_API_KEY = "sk-..."

# 또는 Aider (다양한 공급자 지원)
pip install aider-chat
$env:OPENAI_API_KEY = "sk-..."
```

### 1) 파일럿: 단일 에이전트 × 단일 모델

```powershell
# Cursor sonnet 으로 C0/C1만 1회씩 task-1 만 (파이프라인 무결성 검증)
.\experiments\runner\run_experiment.ps1 `
    -Agent cursor -Model sonnet `
    -Conditions "C0,C1" -Repeats 1 -Tasks "task-1-todo-crud"
```

### 2) Phase 1 풀런 — 여러 구독 잔여 크레딧으로 분산 소진

```powershell
# 공통 RunId 로 묶기
$id = Get-Date -Format 'yyyyMMdd_HHmmss'

# (a) Cursor Pro 잔여분
.\experiments\runner\run_experiment.ps1 -RunId $id -Agent cursor -Model sonnet  -Repeats 3
.\experiments\runner\run_experiment.ps1 -RunId $id -Agent cursor -Model gpt-5   -Repeats 3

# (b) Aider 로 OpenAI 잔여 크레딧 소진
$env:OPENAI_API_KEY = "sk-..."
.\experiments\runner\run_experiment.ps1 -RunId $id -Agent aider -Model "openai/gpt-4o-mini" -Repeats 3

# (c) Codex CLI 로 Anthropic 크레딧 등
.\experiments\runner\run_experiment.ps1 -RunId $id -Agent codex -Model "gpt-5-codex" -Repeats 3

# (d) Copilot GUI 는 수동 모드로
.\experiments\runner\run_experiment.ps1 -RunId $id -Agent manual -Model "copilot-gui-claude" -Repeats 1 -Conditions C1

# 교차 집계 (마지막 호출 시점에 자동 갱신되지만, 수동도 가능)
python .\experiments\runner\aggregate.py --run-root .\experiments\results\$id
```

결과: `experiments/results/<RunId>/`

```
<RunId>/
├─ cursor/sonnet/   summary.csv + report.md   (agent/model 범위)
├─ cursor/gpt-5/    ...
├─ aider/openai_gpt-4o-mini/ ...
├─ codex/gpt-5-codex/ ...
├─ summary.csv       (교차 집계)
└─ report.md         (agent × model × condition pivot)
```

### 3) 매트릭스만 미리 확인 (Dry run)

```powershell
.\experiments\runner\run_experiment.ps1 -Agent cursor -Model sonnet -DryRun
```

### 4) Quota/시간 예산 감시 (별도 터미널)

```powershell
.\experiments\runner\monitor_quota.ps1 `
    -RunRoot .\experiments\results\20260421_140000 `
    -TimeBudgetMinutes 180 -FailureThreshold 5
```

`.stop` 파일이 생기면 runner 가 다음 iter 전에 중단합니다.

## 8개 지표

| # | 지표 | 출처 |
|---|---|---|
| 1 | 요구사항 충족률 | `acceptance.<task>.yaml` 체크리스트 × 자동판정 + LLM judge |
| 2 | 테스트 통과율 | `pytest --json-report` |
| 3 | 빌드 성공 여부 | `pip check` + `import app` smoke |
| 4 | 설계-구현 일치도 | `architecture.md` vs 실제 라우트/모듈 diff (judge) |
| 5 | 정적 분석 오류 수 | `ruff check --output-format=json` + `mypy` |
| 6 | 재프롬프트 횟수 | stream.jsonl user turn count |
| 7 | 수동 수정 횟수 (대체) | `apply_failed / retry / error` 이벤트 수 |
| 8 | 전체 작업 시간 | wall clock + agent steps + tokens (+ cost) |

## 폴더 구조

```
docs_experiment/
├─ docs/                       (계획서/요구사항/설계 문서)
├─ experiments/
│  ├─ conditions/C0..C4/setup.ps1
│  ├─ prompts/                 (seed_prompt + acceptance*.yaml + judge_rubric)
│  ├─ runner/
│  │  ├─ run_experiment.ps1    오케스트레이터
│  │  ├─ evaluate.py           1 run 평가
│  │  ├─ aggregate.py          run_root 집계
│  │  ├─ monitor_quota.ps1     시간/실패율 감시
│  │  ├─ agents/               Cursor/Codex/Aider/Copilot/custom/manual
│  │  └─ lib/                  judge / metrics / stream_parser / logger
│  ├─ results/<RunId>/…
│  └─ ws/<agent>-<model>-<cond>-rep<N>/
├─ requirements.txt
├─ .gitignore
└─ README.md
```

## 참고 문헌

- ETH Zurich AGENTbench 요약: https://www.infoq.com/news/2026/03/agents-context-file-value-review/
- Cursor Headless CLI: https://cursor.com/docs/cli/headless
- Cursor Worktrees: https://cursor.com/docs/configuration/worktrees
- OpenAI Codex CLI: https://github.com/openai/codex
- Aider: https://aider.chat
- SWE-bench: https://www.swebench.com/SWE-bench/
- Aider SWE-bench harness: https://github.com/Aider-AI/aider-swe-bench
- Cursor plugin `continual-learning`
- Cursor plugin `cli-for-agents`

## 주의

- `num_workers=0` 기본, pytest `-p no:xdist` (user rule 11: Windows 멀티프로세스 이슈 회피)
- 새 라이브러리 추가 시 `requirements.txt` 갱신 (user rule 2)
- git 커밋/푸시는 반드시 사용자 동의 후 (user rule 6)
