# Task 3 — 페이지네이션 + 검색 필터

## 배경

task-2까지의 API에 목록 조회 시 페이지네이션과 검색/필터 기능을 추가한다.

## 기능 요구사항 (FR)

- **FR-3.1** `GET /api/v1/todos`의 쿼리 파라미터:
  - `page: int = 1` (>=1)
  - `size: int = 20` (1..100)
  - `q: str | None` — title/description 부분 일치 (대소문자 무시)
  - `completed: bool | None`
- **FR-3.2** 응답 포맷 변경:
  ```json
  {
    "items": [TodoRead, ...],
    "total": 120,
    "page": 1,
    "size": 20
  }
  ```
- **FR-3.3** `size>100`이면 422. `page<1` / `size<1`도 422.
- **FR-3.4** 결과는 항상 현재 사용자 소유의 TODO만 포함.
- **FR-3.5** 기본 정렬: `updated_at DESC`.

## 비기능 요구사항 (NFR)

- **NFR-3.1** 100만 row 테스트 요구는 없음 (단위 테스트로 충분).
- **NFR-3.2** SQL injection 방지 (ORM 파라미터 바인딩).
- **NFR-3.3** 테스트 커버리지 ≥ 70%.
- **NFR-3.4** ruff 에러 0, mypy 에러 ≤ 3.
- **NFR-3.5** `q` 검색은 SQLite는 `LIKE`, Postgres는 `ILIKE` 호환.

## 수용 기준

- [ ] `?size=150`은 422.
- [ ] `?q=foo`는 title 또는 description에 "foo"를 포함한 todos만 반환 (대소문자 무시).
- [ ] `?completed=true` 필터 정상.
- [ ] `?page=2&size=5` 반환 개수 ≤ 5, `total`은 전체 개수.
- [ ] 다른 사용자 TODO는 결과에 섞이지 않음 (통합 테스트).
- [ ] pytest 커버리지 ≥ 70%.
- [ ] 기본 정렬 `updated_at DESC`.

## 범위 외

- 태그/카테고리, 정렬 옵션 확장은 다루지 않음.
