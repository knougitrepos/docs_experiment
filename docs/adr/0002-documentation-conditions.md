# ADR 0002 — 실험 조건(C0~C4) 설계

- 상태: Accepted
- 날짜: 2026-04-21

## 맥락

문서 참조 방식의 영향을 측정하려면 단순히 "있음/없음"으로 나누지 않고 **계층적 스펙트럼**으로 놓아야 한다. 선행 연구(ETH AGENTbench)는 유/무 이분법이었다.

## 결정

- C0 **Bare**: 문서 0.
- C1 **SingleReq**: `requirements.md` 단일 파일.
- C2 **Split**: `requirements.md` + `architecture.md` + `api.md` + `db.md`.
- C3 **StructuredDocs**: C2 + `docs/` 계층(ADR, 진행상황) + 루트 `AGENTS.md`.
- C4 **ContinualDocs**: C3 + `continual-learning` 플러그인 자동 유지.

## 근거

- C1 → C2로의 비약은 "분할이 유용한가?" 검증.
- C2 → C3로의 비약은 "전역 지침(AGENTS.md)이 추가 가치가 있는가?" 검증.
- C3 → C4로의 비약은 "자동 유지 메커니즘이 연속 task에서 효과적인가?" 검증.

## 영향

- `conditions/C0..C4/setup.ps1`이 이 정의를 그대로 반영.
- 공정성 통제: 프롬프트(seed_prompt.md)는 모든 조건에서 동일.
