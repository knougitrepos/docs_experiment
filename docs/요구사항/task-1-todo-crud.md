# Task 1 — TODO CRUD (SQLite + Pydantic v2)

## 배경

개인용 TODO 목록을 관리하는 REST API를 구현한다. 첫 task는 CRUD 기본 동작과 테스트 환경 셋업에 초점을 둔다.

## 기능 요구사항 (FR)

- **FR-1.1** `POST /api/v1/todos` — 새 TODO 생성. `title`(1..200) 필수, `description`(선택), `completed`(기본 false).
- **FR-1.2** `GET /api/v1/todos/{todo_id}` — 단건 조회. 없으면 404 + `code=TODO_NOT_FOUND`.
- **FR-1.3** `GET /api/v1/todos` — 전체 목록 조회. (task-1에서는 필터 없음, 배열 반환 허용)
- **FR-1.4** `PUT /api/v1/todos/{todo_id}` — 업데이트. 최소 1개 필드 변경.
- **FR-1.5** `DELETE /api/v1/todos/{todo_id}` — 삭제. 204.
- **FR-1.6** `GET /health` — `{"status":"ok"}` 반환.

## 비기능 요구사항 (NFR)

- **NFR-1.1** Python 3.11+, FastAPI 0.110+.
- **NFR-1.2** SQLAlchemy 2.x + SQLite (`data.db`).
- **NFR-1.3** Pydantic v2 (`model_validate`).
- **NFR-1.4** 테스트 커버리지 ≥ 70%. (`pytest-cov --cov=app`)
- **NFR-1.5** ruff 에러 0, mypy 에러 ≤ 3.
- **NFR-1.6** 응답에 `created_at`/`updated_at` ISO8601.
- **NFR-1.7** 프로젝트 실행: `uvicorn app.main:app` 단일 명령.
- **NFR-1.8** Windows에서 pytest는 `-p no:xdist` 기본 (num_workers=0).

## 디렉터리 제약

- 소스는 `app/` 하위, 테스트는 `tests/` 하위.
- 세부 레이어 분할은 `docs/architecture.md` 권장을 따른다 (존재하는 조건에서만).

## 데이터 모델

- `todos` 테이블: `id`, `title`, `description`, `completed`, `created_at`, `updated_at`.
  - task-1에서는 `user_id` 컬럼 없음 (task-2에서 추가).

## 수용 기준 (Acceptance Criteria — test 가능한 것만)

- [ ] `pytest`가 실패 없이 통과하고 커버리지 ≥ 70%.
- [ ] `ruff check .` 에러 0.
- [ ] `mypy app` 에러 ≤ 3.
- [ ] `uvicorn`으로 서버가 기동되고 `/health`가 200.
- [ ] `POST → GET → PUT → DELETE` 시나리오가 통합 테스트로 검증됨.
- [ ] 404 시 `{"detail": "...", "code": "TODO_NOT_FOUND"}` 형식.
- [ ] 422 시 FastAPI 기본 유효성 오류 응답.

## 범위 외 (Out of Scope)

- 인증 (task-2), 페이지네이션 (task-3).
