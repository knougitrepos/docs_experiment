# Judge Rubric — 채점 지침

> 본 rubric 은 LLM-judge 가 **acceptance checklist의 비자동(automated=false) 항목**과
> **설계-구현 일치도(지표 #4)**를 채점할 때 사용합니다.

## 1. 입출력 계약

- Judge 에게 주어지는 입력:
  - `TASK_ID`
  - `워크스페이스 파일 목록 + 각 파일 내용 (요약 가능, 단 핵심 모듈은 원문)`
  - `acceptance checklist 의 비자동 항목 리스트 (id, text)`
  - `설계 문서 (architecture.md, api.md, db.md 가 있는 경우)`
- Judge 의 출력 형식 (JSON only):

```json
{
  "checklist": [
    { "id": "qual_layering", "score": 1, "reason": "app/api, app/services, app/repositories 모두 존재" }
  ],
  "design_alignment": {
    "modules_expected": ["app/api", "app/services", "app/repositories", "app/models", "app/schemas", "app/core"],
    "modules_missing": [],
    "routes_expected": ["POST /api/v1/todos", "GET /api/v1/todos/{id}"],
    "routes_missing": [],
    "score": 0.95,
    "reason": "..."
  }
}
```

## 2. 채점 원칙

- 각 checklist 항목은 0 또는 1 로만 채점. 애매하면 0.
- `design_alignment.score` = 1 - (missing_modules + missing_routes) / (total_modules + total_routes), 범위 [0,1].
- `reason` 은 1문장 이내.
- **근거 없는 추측은 배제**. 실제 파일/함수가 존재하는지 검증.

## 3. Judge 모델 고정

- 항상 `sonnet` (또는 `claude-3.7-sonnet`)로 실행.
- `--model sonnet` 로 `cursor-agent -p` 호출.
- temperature 는 기본값 (외부 제어 불가).
- 20% 샘플은 사람이 수동 재검수 (`docs/보고서_중간분석_*.md` 에 기록).

## 4. 호출 규약

```bash
cursor-agent -p --force --model sonnet --output-format json \
    "$(cat experiments/prompts/judge_rubric.md) \n\n WORKSPACE: ... \n CHECKLIST: ... \n" \
    > judge_result.json
```

`experiments/runner/evaluate.py` 가 위 호출을 래핑합니다.
