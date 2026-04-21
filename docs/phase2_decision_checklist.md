# Phase 2 착수 결정 체크리스트 (Brownfield / SWE-bench)

> Phase 1 (Greenfield — FastAPI TODO 3 task × 5 조건 × 3 반복) 의 결과를 바탕으로,
> **Phase 2 (Brownfield — SWE-bench Lite 기반)** 에 착수할지 결정하는 기준 문서.
>
> 목표: Phase 1 에서 관찰된 "문서 구조 효과" 가 **기존 코드베이스 수정** 시나리오에서도 재현/확장되는지 검증.

## A. 착수 판단 기준 (모두 YES 여야 진행)

### A1. Phase 1 파이프라인이 안정 동작하는가?

- [ ] 전 (agent, model) 조합에서 `metrics.json` 누락이 **5% 미만**
- [ ] `aggregate.py` 가 **에러 없이** `summary.csv`/`report.md` 생성
- [ ] `monitor_quota.ps1` 의 `.stop` 트리거가 의도된 시점에만 발동
- [ ] `stream.jsonl` 이 모든 어댑터에서 파싱 가능 (`parse_stream` 의 unknown event < 2%)

### A2. 가설에 **의미 있는 방향성** 이 관찰되는가?

"의미 있는" = agent/model 당 조건 간 Δ가 표준편차의 **1σ 이상** 이거나, 부트스트랩 95% CI 하한이 0 초과.

- [ ] **H1 (계층화 효과)**: C2 이상에서 요구사항 충족률 개선 (Δ ≥ 1σ) — 최소 2개 (agent, model) 에서 확인
- [ ] **H2 (재프롬프트 ↓, steps ↑)**: 방향성 일관 — 최소 2개 (agent, model) 에서 확인
- [ ] **H3 (C4 continual-learning 효과)**: task-2/3 에서 manual_fix_proxy 감소 — 방향성만 확인되어도 OK

*(모두 충족이 이상적이지만, 1개 만 확실히 충족되어도 Phase 2 진입은 가능. 단, 보고서에 어떤 가설을 focus 할지 적기.)*

### A3. 비용 여력이 있는가?

Phase 2 는 Brownfield 수정 시나리오라 Phase 1 대비 평균 **1.5~2x 토큰** 을 소비합니다.

- [ ] 각 구독의 월 한도 기준, **Phase 1 풀런 사용량의 2배 이상** 의 여유가 있다
- [ ] `monitor_quota.ps1` 에 `TimeBudgetMinutes` 를 Phase 1 기준 **1.5배** 로 설정할 수 있다

### A4. Brownfield 평가 프레임워크의 준비 상태

- [ ] **SWE-bench Lite** 데이터셋 로드 가능 (`pip install datasets` + `HuggingFaceH4/SWE-bench_Lite` 또는 원본)
- [ ] **swebench** 평가 하네스 설치 가능 (Docker 필요) — Windows 에서는 WSL2 권장
- [ ] 선별 이슈 N 개(권장 15~30)의 저장소/버전 호환성 사전 확인

## B. Phase 2 설계 변경 사항

### B1. 조건 매핑

Greenfield 의 C0~C4 를 Brownfield 에 맞게 **해석** 합니다.

| 조건 | Greenfield | Brownfield(SWE-bench) |
|---|---|---|
| C0 | 아무 문서 없음 | 이슈 설명만, 저장소 docs/ 폴더 삭제 상태 |
| C1 | REQUIREMENTS.md 1개 | 이슈 설명 + FAIL_TO_PASS 테스트 리스트 |
| C2 | requirements + arch + api + db | 이슈 + 저장소 기존 README/CONTRIBUTING/ARCHITECTURE |
| C3 | + adr + AGENTS.md | C2 + 저장소 AGENTS.md (없으면 agents.md 가이드 자동 생성) |
| C4 | + continual-learning | C3 + `continual-learning` 활성화, 연속 이슈 3개를 한 세션에서 수정 |

### B2. 평가 지표 수정

| # | Phase 1 | Phase 2 변경 |
|---|---|---|
| 1 요구사항 충족률 | YAML 체크리스트 | **resolved rate** (PASS_TO_PASS + FAIL_TO_PASS 통과율; SWE-bench 공식) |
| 2 테스트 통과율 | `pytest --cov` | 저장소 테스트 러너 사용 (swebench harness) |
| 3 빌드 성공 | `pip check` | 저장소의 build/install 스크립트 성공 여부 |
| 4 설계-구현 일치도 | architecture.md vs routes | ARCHITECTURE.md (있으면) vs diff 파일 목록 |
| 5 정적 분석 | ruff/mypy | 저장소 권장 도구 (black, flake8, eslint 등) |
| 6 재프롬프트 | 동일 | 동일 |
| 7 수동 수정 대체 | 동일 | 동일 |
| 8 작업 시간 | 동일 | 동일 |

### B3. 어댑터 재활용

`agents/*.ps1` 는 그대로 사용. Phase 2 에서는 `experiments/conditions_swebench/C0..C4/setup.ps1` 를 별도 작성.

### B4. 실험 축 크기 예시

```
Phase 2 pilot : 1 모델(sonnet) × 5 조건 × 1 반복 × 10 이슈 = 50 run
Phase 2 full  : 3 모델 × 5 조건 × 3 반복 × 15 이슈 = 675 run  (총 예산 재검토 필수)
```

## C. 진입 결정 판정

아래 중 하나를 체크.

- [ ] **진입**: A1~A4 충족, B1~B4 문서화 완료 → Phase 2 스캐폴드(`experiments/conditions_swebench/`) 추가 브랜치 생성
- [ ] **보류**: A1~A2 중 하나라도 미충족 → Phase 1 결함 수정 후 재실험 (실험계획서 §8 일정 조정)
- [ ] **축소**: A3 만 미충족 → Phase 2 pilot 만 (10 이슈 × 1 모델) 수행, full 은 다음 분기로 연기
- [ ] **중단**: 가설 H1~H3 가 모두 통계적 유의성 미달 → 원인 분석 보고서 작성 후 프로젝트 종료 or 주제 피벗

## D. 체크리스트 작성자

- 작성자: _____
- 작성일: YYYY-MM-DD
- 근거 문서: `experiments/results/<run_id>/report.md`, `docs/보고서_중간분석_<YYYYMMDD>_v1.md`
- 검토자(선택): _____

---

## 부록 — 참고문헌

- **SWE-bench** (Jimenez et al., 2024): *SWE-bench: Can Language Models Resolve Real-World GitHub Issues?*  
  <https://www.swebench.com/SWE-bench/>
- **Aider SWE-bench harness**: <https://github.com/Aider-AI/aider-swe-bench>
- **SWE-bench Lite**: 저비용 서브셋 (300 issues across 12 repos).
- **AGENTbench (ETH)** — AGENTS.md 유/무 효과 연구 (2026.03, InfoQ 요약).
