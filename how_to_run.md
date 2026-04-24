# Phase 1 Agent Notebook 실행 방법

이 문서는 현재 사용하는 세 에디터/agent인 Codex, Cursor, Antigravity로 Phase 1 실험을 실행하는 방법을 정리한다.

핵심 원칙은 하나다.

```text
한 번의 실험은 하나의 agent + 하나의 model + 하나의 reasoning/mode 조합으로 실행한다.
```

따라서 Codex, Cursor, Antigravity를 같은 노트북에서 섞지 말고, 아래 전용 노트북 중 하나를 선택해서 실행한다.

| 대상 | 노트북 | 실행 성격 |
|---|---|---|
| Codex CLI | `output/jupyter-notebook/phase1-codex-run.ipynb` | 자동 실행 |
| Cursor CLI | `output/jupyter-notebook/phase1-cursor-run.ipynb` | 자동 실행 |
| Antigravity GUI | `output/jupyter-notebook/phase1-antigravity-run.ipynb` | 수동/반자동 실행 |

## 1. 공통 준비

Windows PowerShell 환경을 기준으로 한다.

1. repo 루트로 이동한다.

```powershell
cd C:\git\docs_experiment
```

2. Python 가상환경이 있는지 확인한다.

```powershell
.\.venv\Scripts\python.exe --version
```

3. 노트북은 JupyterLab, VS Code Notebook, Cursor Notebook 등 원하는 노트북 실행 환경에서 열 수 있다.

```powershell
.\.venv\Scripts\python.exe -m pip install jupyterlab
.\.venv\Scripts\python.exe -m jupyter lab
```

4. 각 노트북은 위에서부터 순서대로 실행한다.

```text
00 Configuration
01 Environment Preflight
02 Agent/Model Guard
03 DryRun
04 Full Run
05 Aggregate
06 Review Results
```

기본값은 비용과 시간을 막기 위해 `RUN_FULL_RUN = False`다. `03 DryRun`까지 성공한 뒤 실제 실행할 때만 `RUN_FULL_RUN = True`로 바꾼다.

기본 실행 규모는 다음과 같다.

```text
5 conditions x 3 repeats x 3 tasks = 45 runs
```

## 2. Codex 실행

사용 파일:

```text
output/jupyter-notebook/phase1-codex-run.ipynb
```

기본 설정:

```python
AGENT = "codex"
MODEL = "gpt-5.4-mini"
REASONING_EFFORT = "low"
AGENT_EXTRA_ARGS = "--ephemeral"
```

실행 흐름:

1. `01 Environment Preflight`를 실행해 Python, `.venv`, requirements 설치 상태를 확인한다.
2. `02 Agent/Model Guard`를 실행한다.
3. guard는 `codex --version`, `codex debug models`, 실제 `codex exec` 최소 호출을 확인한다.
4. `03 DryRun`으로 45 run 매트릭스와 결과 경로를 확인한다.
5. 실제 실행하려면 `RUN_FULL_RUN = True`로 바꾸고 `04 Full Run`을 실행한다.
6. 실행 후 `05 Aggregate`, `06 Review Results`를 실행한다.

Codex는 노트북에서 모델과 reasoning을 실제 CLI 호출로 검증한다. 즉 catalog에 보이는지만 확인하지 않고, 현재 계정으로 실제 실행 가능한지도 확인한다.

## 3. Cursor 실행

사용 파일:

```text
output/jupyter-notebook/phase1-cursor-run.ipynb
```

기본 설정:

```python
AGENT = "cursor"
MODEL = "sonnet"
REASONING_EFFORT = "default"
```

실행 흐름:

1. Cursor CLI가 설치되어 있어야 한다.
2. `cursor-agent`가 PATH에서 실행 가능해야 한다.
3. `01 Environment Preflight`를 실행한다.
4. `02 Agent/Model Guard`를 실행한다.
5. guard는 `cursor-agent --version`, `cursor-agent --help`, 실제 짧은 `cursor-agent` 호출을 확인한다.
6. `03 DryRun`으로 매트릭스를 확인한다.
7. 실제 실행하려면 `RUN_FULL_RUN = True`로 바꾸고 `04 Full Run`을 실행한다.
8. 실행 후 `05 Aggregate`, `06 Review Results`를 실행한다.

현재 PC에서 `cursor-agent`가 PATH에 없으면 `02 Agent/Model Guard`에서 중단된다. 이 경우 Cursor CLI 설치 또는 PATH 설정을 먼저 해야 한다.

Cursor의 모델명은 Cursor CLI가 받는 이름을 그대로 사용한다. 예를 들어 `sonnet`, `gpt-5`, `composer`처럼 Cursor 환경에서 지원되는 모델명을 넣는다.

## 4. Antigravity 실행

사용 파일:

```text
output/jupyter-notebook/phase1-antigravity-run.ipynb
```

기본 설정:

```python
AGENT = "antigravity"
MODEL = "gemini-3-pro-preview"
REASONING_EFFORT = "default"
AGENT_EXTRA_ARGS = "Mode=agent Launch=true"
ANTIGRAVITY_MODE = "agent"
CONFIRM_ANTIGRAVITY_MODEL_SELECTED = False
```

Antigravity는 Codex/Cursor와 다르다. 현재 확인된 Antigravity CLI는 `chat --mode`는 제공하지만 안정적인 `--model` 옵션을 노출하지 않는다. 따라서 노트북의 `MODEL` 값은 실험 기록 라벨이고, 실제 모델 선택은 Antigravity UI에서 직접 맞춰야 한다.

실행 흐름:

1. `01 Environment Preflight`를 실행한다.
2. `02 Agent/Model Guard`를 실행한다.
3. guard는 `antigravity --version`, `antigravity chat --help`를 확인한다.
4. `03 DryRun`으로 매트릭스를 확인한다.
5. Antigravity UI에서 노트북의 `MODEL`과 같은 모델을 직접 선택한다.
6. Antigravity UI에서 `ANTIGRAVITY_MODE`와 같은 모드 또는 가장 가까운 모드를 선택한다.
7. 설정 셀에서 `CONFIRM_ANTIGRAVITY_MODEL_SELECTED = True`로 바꾼다.
8. 실제 실행하려면 `RUN_FULL_RUN = True`로 바꾸고 `04 Full Run`을 실행한다.
9. 각 run마다 adapter가 workspace와 prompt 파일 경로를 보여준다.
10. Antigravity에서 해당 workspace를 열고 prompt 내용을 실행한다.
11. 작업이 끝나면 노트북/터미널 쪽에서 Enter를 눌러 runner가 평가 단계로 넘어가게 한다.
12. 모든 run이 끝나면 `05 Aggregate`, `06 Review Results`를 실행한다.

Antigravity 결과는 `agent=antigravity`, `model=<노트북 MODEL 값>`으로 기록된다. 보고서에서는 이 값을 “Gemini 단독 성능”이 아니라 “Antigravity 환경에서 해당 모델을 선택한 end-to-end 수행 결과”로 해석해야 한다.

## 5. 결과 위치

결과는 기본적으로 아래 구조에 저장된다.

```text
experiments/results/<RunId>/<agent>/<model>[/reasoning-<effort>]/
```

예시:

```text
experiments/results/phase1-codex-20260424_140000/codex/gpt-5.4-mini/reasoning-low/
experiments/results/phase1-cursor-20260424_140000/cursor/sonnet/
experiments/results/phase1-antigravity-20260424_140000/antigravity/gemini-3-pro-preview/
```

주요 파일:

| 파일 | 의미 |
|---|---|
| `runs.csv` | run 매트릭스와 실행 상태 |
| `summary.csv` | aggregate 후 핵심 지표 요약 |
| `report.md` | aggregate 후 텍스트 보고서 |
| `stream.jsonl` | agent 실행 출력 또는 manual placeholder |
| `agent.meta.json` | adapter 실행 메타데이터 |
| `run.meta.json` | runner 실행 메타데이터 |
| `metrics.json` | 평가 지표 |

## 6. 어떤 노트북을 어디서 실행해야 하나

노트북 자체는 반드시 해당 에디터 안에서만 열 필요는 없다. JupyterLab, VS Code Notebook, Cursor Notebook 어디서 열어도 된다.

다만 실제 agent 실행 방식은 다르다.

| 노트북 | 노트북을 여는 곳 | 실제 agent 실행 |
|---|---|---|
| Codex 노트북 | 아무 Jupyter 환경 가능 | 노트북이 `codex exec`를 자동 호출 |
| Cursor 노트북 | 아무 Jupyter 환경 가능 | 노트북이 `cursor-agent`를 자동 호출 |
| Antigravity 노트북 | 아무 Jupyter 환경 가능 | 사용자가 Antigravity GUI에서 직접 실행 |

즉 “각각의 노트북을 각각 해당 에디터에서 실행해야 하냐”에 대한 답은 다음과 같다.

```text
Codex/Cursor는 노트북을 어디서 열든 CLI가 실행되면 된다.
Antigravity는 노트북은 어디서 열어도 되지만, 실제 작업은 Antigravity UI에서 해야 한다.
```

## 7. 실행 전 체크리스트

Codex:

```text
codex --version 성공
codex debug models 성공
노트북 02 Agent/Model Guard 성공
03 DryRun 성공
RUN_FULL_RUN=True로 변경
```

Cursor:

```text
cursor-agent --version 성공
노트북 02 Agent/Model Guard 성공
03 DryRun 성공
RUN_FULL_RUN=True로 변경
```

Antigravity:

```text
antigravity --version 성공
노트북 02 Agent/Model Guard 성공
03 DryRun 성공
Antigravity UI에서 모델 선택 완료
Antigravity UI에서 모드 선택 완료
CONFIRM_ANTIGRAVITY_MODEL_SELECTED=True로 변경
RUN_FULL_RUN=True로 변경
```

## 8. 비용과 중단

Full Run은 실제 agent/model 호출을 수행하므로 비용과 quota를 사용한다.

노트북에는 quota monitor 명령을 출력하는 셀이 있다. 자동으로 백그라운드 실행하지 않는다. 필요하면 별도 PowerShell 터미널에서 출력된 명령을 실행한다.

실험 중단은 run root 아래 `.stop` 파일을 만드는 방식으로 처리한다.

```powershell
New-Item -ItemType File experiments\results\<RunId>\.stop
```

runner는 다음 iteration 전에 `.stop` 파일을 감지하고 중단한다.
