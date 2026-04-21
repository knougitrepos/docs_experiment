# ADR 0001 — 기술 스택 선정

- 상태: Accepted
- 날짜: 2026-04-21

## 맥락

LLM 코드 생성 실험 대상을 Python 생태계 FastAPI로 한다.

## 결정

- 언어: **Python 3.11+**
- 웹: **FastAPI**
- ORM: **SQLAlchemy 2.x** (sync)
- DB: **SQLite** (dev/test), PostgreSQL 호환 스키마
- 인증: **JWT** (python-jose + passlib/bcrypt)
- 테스트: **pytest** + pytest-cov + httpx
- 품질: **ruff** + **mypy**

## 근거

- Python은 LLM이 가장 잘 생성하는 언어 중 하나 → 조건 간 생성 실패가 과소 될 가능성 있으나, 본 실험의 변수는 "문서 구조"이므로 생성 품질의 baseline은 높게 두는 것이 분산을 줄인다.
- FastAPI는 타입 힌트·Pydantic·OpenAPI 자동 생성 덕분에 "설계-구현 일치도"를 측정하기 적합.
- SQLite는 in-process로 테스트 격리가 쉬워 CI/로컬 재현성에 유리.

## 대안과 반대 의견

- Node.js/Express — 테스트 자동화 복잡성 ↑
- Django — 관례가 강해 LLM이 편향될 수 있음
- Go — LLM 성능이 Python 대비 약간 낮음

## 영향

- `requirements.txt` 고정
- Windows `num_workers>0` 이슈 회피(user rule 11) — `-p no:xdist` 기본
