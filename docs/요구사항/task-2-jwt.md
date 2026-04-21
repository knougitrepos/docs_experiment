# Task 2 — JWT 인증 + 사용자 관리

## 배경

task-1에서 만든 TODO API에 사용자 개념과 JWT 인증을 추가한다. 각 사용자는 자신의 TODO만 보고/수정할 수 있다.

## 기능 요구사항 (FR)

- **FR-2.1** `POST /api/v1/auth/register` — 가입. `username`(3..30), `password`(8..128), `email` 필수.
  - 중복 시 409 + `code=USERNAME_TAKEN`.
- **FR-2.2** `POST /api/v1/auth/login` — 로그인. 성공 시 `{ "access_token", "token_type":"bearer", "expires_in": 3600 }`.
  - 실패 시 401 + `code=INVALID_CREDENTIALS`.
- **FR-2.3** `GET /api/v1/auth/me` — 현재 사용자 정보.
- **FR-2.4** `GET /api/v1/users/me` — FR-2.3 별칭.
- **FR-2.5** **기존 todos 엔드포인트 전부 JWT 보호**. 인증 없으면 401 + `code=INVALID_TOKEN`.
- **FR-2.6** 사용자는 자기 소유 TODO만 조회/수정/삭제 가능 (타 소유면 404 반환으로 정보 은닉).

## 비기능 요구사항 (NFR)

- **NFR-2.1** 비밀번호는 bcrypt (`passlib[bcrypt]`).
- **NFR-2.2** JWT: HS256, `JWT_SECRET` env 필수. `JWT_EXPIRE_MINUTES` 기본 60.
- **NFR-2.3** `todos.user_id` NOT NULL로 마이그레이션. task-2 시작 시 DB 초기화 허용.
- **NFR-2.4** 테스트 커버리지 ≥ 70%.
- **NFR-2.5** ruff 에러 0, mypy 에러 ≤ 3.
- **NFR-2.6** 회원가입 응답에 `hashed_password`가 **절대 노출되지 않음**.

## 데이터 모델 변경

- `users` 테이블 추가 (컬럼: `id`, `username` UK, `email` UK, `hashed_password`, `created_at`, `updated_at`).
- `todos.user_id` 컬럼 추가 (FK users.id, NOT NULL).
- 기존 todo 데이터는 폐기해도 됨.

## 수용 기준

- [ ] 가입 → 로그인 → /auth/me 시나리오 통합 테스트 통과.
- [ ] 로그인 없이 /todos 접근 시 401 + `INVALID_TOKEN`.
- [ ] 다른 유저의 TODO ID로 접근 시 404.
- [ ] 가입 응답에 `hashed_password` 없음 (스키마 테스트).
- [ ] pytest 커버리지 ≥ 70%.

## 범위 외

- 페이지네이션 (task-3).
