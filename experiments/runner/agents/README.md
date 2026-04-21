# Agent Adapters — 공통 규약

본 디렉터리에는 실험 runner 가 호출하는 **CLI 에이전트 어댑터**들이 있습니다.
단일 모델/에이전트로 독립 실행할 수 있도록 표준화된 인터페이스를 따릅니다.

## 왜 어댑터인가

- Cursor 한 곳에 종속되지 않도록, 각 구독(Cursor / Copilot / OpenAI Codex / Aider 등)의 잔여 토큰을 **분산 소진**하며 동일 실험을 반복한다.
- 여러 모델을 한 번에 돌리면 토큰 비용 통제/환경 통제가 어려우므로, 실험 1회는 **하나의 agent × 하나의 model** 만 사용한다.
- 새 CLI 가 생겨도 어댑터 1개만 추가하면 됨.

## 파일 목록

| 파일 | 에이전트 | 기본 호출 형태 |
|---|---|---|
| `cursor.ps1` | Cursor CLI | `cursor-agent -p --force --model <M> --output-format stream-json "<prompt>"` |
| `codex.ps1` | OpenAI Codex CLI | `codex exec --model <M> --json "<prompt>"` |
| `aider.ps1` | Aider | `aider --model <M> --yes --no-pretty --message-file <prompt.txt>` |
| `copilot.ps1` | GitHub Copilot CLI (실험적) | `gh copilot suggest -t shell "<prompt>"` (제한적) |
| `custom.ps1` | 임의 CLI 템플릿 | 사용자가 `-AgentCommand` 로 주입 |
| `manual.ps1` | 수동(워크스페이스만 준비 → 사람이 대화형 채팅으로 실행) | 사용자 입력 대기 → 사용자가 stream 로그 붙여넣기 |

## 어댑터 인터페이스

모든 어댑터는 아래 파라미터를 받아야 한다.

| 파라미터 | 필수 | 설명 |
|---|---|---|
| `-Workspace`   | Y | 에이전트가 작업할 디렉터리. **현재 디렉터리(cwd)는 이 경로로 설정**한다. |
| `-PromptFile`  | Y | 프롬프트 텍스트가 담긴 파일 (UTF-8). |
| `-Model`       | Y | 모델 식별자 (에이전트별 이름 공간). |
| `-StreamOut`   | Y | stream 로그를 기록할 파일 경로 (JSONL 권장, 어댑터마다 포맷 다를 수 있음). |
| `-MetaOut`     | Y | `meta.json` 출력 경로. 아래 스키마 준수. |
| `-TimeoutSec`  | N | 기본 1800(30분). |
| `-Extra`       | N | 어댑터 고유 옵션(해시테이블). |

### `meta.json` 스키마 (모든 어댑터 공통 출력)

```json
{
  "agent": "cursor",             // enum: cursor | codex | aider | copilot | custom | manual
  "model": "sonnet",
  "started_at": "ISO8601",
  "finished_at": "ISO8601",
  "wall_seconds": 123.4,
  "exit_code": 0,
  "prompt_bytes": 1234,
  "stream_bytes": 56789,
  "agent_steps_hint": 12,        // 어댑터가 알 수 있으면 기록, 아니면 null
  "tokens_hint": { "input": 1000, "output": 2000, "total": 3000 },
  "cost_usd_hint": 0.12,
  "notes": "optional"
}
```

`*_hint` 필드는 어댑터가 "알 수 있을 때" 채우고, 최종 지표 계산은 runner 가 `stream_parser` 로 다시 파싱하여 보정한다.

## 공통 계약

- **실패 처리**: 어댑터는 예외를 던지기보다 `exit_code != 0` 으로 표기하고 `meta.json` 을 반드시 작성한다.
- **대화형 금지**: 어댑터는 **비대화형** 으로만 동작해야 한다. `manual.ps1` 은 예외.
- **stdin/쉘 인자**: 프롬프트가 큰 경우를 감안해 `-PromptFile` 로 받아 파일에서 읽어 파이프로 전달한다.
- **OS**: Windows PowerShell 우선. WSL/Bash 는 향후 확장.
- **cwd 고정**: `Push-Location $Workspace; ... ; Pop-Location` 패턴.

## 호출 예시 (runner 내부)

```powershell
$adapter = "experiments\runner\agents\$AgentName.ps1"
& $adapter -Workspace $wsPath -PromptFile $promptFile -Model $Model `
           -StreamOut $streamPath -MetaOut $metaPath -TimeoutSec 1800
```

## 새 어댑터 추가 절차

1. `agents/<name>.ps1` 작성 (위 인터페이스 준수)
2. `run_experiment.ps1` 의 `ValidateSet` 에 `<name>` 추가
3. `README.md` 표에 한 줄 추가
4. 파일럿 1 회 실행으로 meta.json/stream 포맷 검증
