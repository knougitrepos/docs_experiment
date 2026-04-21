# API Specification — todo-api

> 모든 엔드포인트는 `/api/v1` 하위. JSON in/out.

## 1. Todos (task-1부터)

### 1.1 POST /api/v1/todos

- **설명**: 새 TODO 생성
- **인증**: task-2부터 필수 (Bearer JWT)
- **Request**:
  ```json
  { "title": "string(1..200)", "description": "string|null", "completed": false }
  ```
- **Response 201**:
  ```json
  { "id": 1, "title": "...", "description": "...", "completed": false, "created_at": "ISO8601", "updated_at": "ISO8601" }
  ```
- **Error**: 422 (validation)

### 1.2 GET /api/v1/todos/{todo_id}

- **Response 200**: TodoRead
- **404**: `{ "detail": "Todo not found", "code": "TODO_NOT_FOUND" }`

### 1.3 GET /api/v1/todos

- **Query (task-3부터)**:
  - `page: int = 1 (>=1)`
  - `size: int = 20 (1..100)`
  - `q: str | None` — title/description 부분 일치
  - `completed: bool | None`
- **Response 200**:
  ```json
  { "items": [TodoRead, ...], "total": 120, "page": 1, "size": 20 }
  ```
- **task-1 초기 버전**: 파라미터 없이 배열 반환 가능. task-3에서 반드시 위 스키마로 변경.

### 1.4 PUT /api/v1/todos/{todo_id}

- **Request**: TodoUpdate (전체 필드 선택적, 최소 1개 필드 필요)
- **Response 200**: TodoRead
- **404**: Todo not found

### 1.5 DELETE /api/v1/todos/{todo_id}

- **Response 204**
- **404**: Todo not found

## 2. Auth (task-2부터)

### 2.1 POST /api/v1/auth/register

- **Request**: `{ "username": "3..30", "password": "8..128", "email": "email" }`
- **Response 201**: UserRead (id, username, email, created_at) — 비밀번호는 응답에 없음
- **409**: `{ "detail": "Username already exists", "code": "USERNAME_TAKEN" }`

### 2.2 POST /api/v1/auth/login

- **Request**: `{ "username": "string", "password": "string" }`
- **Response 200**: `{ "access_token": "<jwt>", "token_type": "bearer", "expires_in": 3600 }`
- **401**: `{ "detail": "Invalid credentials", "code": "INVALID_CREDENTIALS" }`

### 2.3 GET /api/v1/auth/me

- **인증**: 필수
- **Response 200**: UserRead

## 3. Users (task-2부터)

### 3.1 GET /api/v1/users/me

- 2.3과 동일하게 현재 사용자 반환 (별칭)

## 4. Health

### 4.1 GET /health

- **Response 200**: `{ "status": "ok" }`

## 5. 에러 코드 집합

| HTTP | code | 의미 |
|---|---|---|
| 401 | INVALID_CREDENTIALS | 로그인 실패 |
| 401 | INVALID_TOKEN | 토큰 만료/위변조 |
| 404 | TODO_NOT_FOUND | TODO 없음 |
| 404 | USER_NOT_FOUND | 유저 없음 |
| 409 | USERNAME_TAKEN | 중복 가입 |
| 422 | VALIDATION_ERROR | Pydantic 검증 실패 (FastAPI 기본) |

## 6. 인증 헤더

- Bearer JWT: `Authorization: Bearer <token>`
- 만료 시 401, `code=INVALID_TOKEN`.

## 7. OpenAPI

- FastAPI가 `/docs` (Swagger), `/redoc`, `/openapi.json` 자동 제공.
