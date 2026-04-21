# AGENTS.md — Global Instructions for Target Project

> 이 파일은 **실험 대상(target) 프로젝트**에서 에이전트가 따라야 할 전역 지침입니다.
> 조건 C3, C4 에서만 워크스페이스에 배치됩니다. C0/C1/C2는 이 파일을 보지 못합니다.

## 1. 프로젝트 개요

- 이름: `todo-api`
- 목적: 개인용 TODO를 관리하는 REST API 서버
- 언어: Python 3.11+
- 웹 프레임워크: FastAPI
- DB: SQLAlchemy 2.x + SQLite (개발), PostgreSQL 호환성 유지
- 인증: JWT (python-jose)

## 2. 명령어 치트시트 (Commands)

```bash
# 의존성 설치
pip install -r requirements.txt

# 개발 서버
uvicorn app.main:app --reload

# 테스트 (Windows: num_workers 문제 회피 위해 xdist 비활성)
pytest --cov=app --cov-report=term-missing -p no:xdist

# 린트
ruff check .
ruff format --check .

# 타입체크
mypy app

# 빌드 (파이썬 패키지가 아니어도 의존성 해결 검증)
python -m pip check
```

## 3. 코드 스타일 (Code Style)

- **함수형보다 의존성 주입 선호**: FastAPI `Depends`로 DB 세션/현재 사용자 주입.
- Pydantic v2 `model_validate` 패턴 사용, `BaseSettings`로 env 관리.
- **snake_case**: 모듈/함수/변수. **PascalCase**: 클래스, Pydantic 모델.
- **타입 힌트 필수** (Python 3.11+ 문법): `list[int]`, `str | None`.
- Docstring은 한국어로 작성 가능 (Google 스타일).
- **주석 원칙**: 코드가 설명 못하는 "왜"만 적는다. `# Import the module` 같은 불필요 주석 금지.
- **에러 처리**: `HTTPException`으로 HTTP 에러 매핑. 내부 로직은 도메인 예외 사용.
- **로그**: `logging.getLogger(__name__)`로 모듈별 로거. 에러는 반드시 `logger.exception()`.

## 4. 아키텍처 원칙 (Architecture)

- **레이어**:
  - `app/api/` — 라우터 (HTTP 표현 계층만)
  - `app/services/` — 비즈니스 로직
  - `app/repositories/` — DB 접근 (SQLAlchemy)
  - `app/models/` — SQLAlchemy ORM 모델
  - `app/schemas/` — Pydantic 스키마
  - `app/core/` — 설정, 보안, DB 엔진
- **금지**: 라우터에서 ORM 직접 조작, 서비스에서 HTTPException 발생
- **의존성 방향**: api → services → repositories → models. 역방향 import 금지.

## 5. 테스트 규칙 (Tests)

- 경로: `tests/` (app 미러 구조)
- httpx `AsyncClient` + `pytest-asyncio`
- 각 테스트는 독립적인 SQLite in-memory DB 사용 (fixture)
- **커버리지 목표**: ≥70%, 신규 코드는 ≥80%
- **Windows 이슈**: `pytest -p no:xdist` 기본. multiprocessing 미사용.

## 6. 보안

- 비밀은 반드시 `.env` 또는 환경변수. 코드에 하드코딩 금지.
- 비밀번호는 `passlib[bcrypt]`로 해싱.
- JWT 시크릿은 `JWT_SECRET` env로 분리.

## 7. 변경 원칙

- 모든 스키마 변경은 `app/schemas/` + `docs/api.md` 동시 갱신.
- 모든 DB 모델 변경은 `docs/db.md` 갱신 + Alembic 마이그레이션(선택).
- 아키텍처 변경 시 `docs/adr/NNNN-*.md` 추가.

## 8. 금지 사항 (Do NOT)

- 테스트 없이 기능 merge.
- `requirements.txt` 없이 새 라이브러리 추가.
- `.env` / 시크릿 파일 커밋.
- 프린트 디버깅 (`print` → `logger`).
- `from fastapi import *`와 같은 와일드카드 import.

## 9. Learned User Preferences

> 이 섹션은 `continual-learning` 플러그인이 자동으로 채웁니다 (C4 조건).
> 사람이 수기로 건드리지 마세요.

<!-- continual-learning:preferences:start -->
<!-- continual-learning:preferences:end -->

## 10. Learned Workspace Facts

<!-- continual-learning:facts:start -->
<!-- continual-learning:facts:end -->
