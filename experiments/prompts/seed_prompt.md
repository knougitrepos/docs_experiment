# 요청

아래 `TASK_ID` 가 가리키는 요구사항 명세에 따라 Python FastAPI 프로젝트를 구현/확장해 주세요.

- 모든 요구사항(FR, NFR)을 충족해야 합니다.
- 테스트 코드(`tests/`)를 함께 작성해 주세요.
- 품질 게이트:
  - `pytest --cov=app -p no:xdist` 가 통과하며 커버리지 >= 70%
  - `ruff check .` 에러 0
  - `mypy app` 에러 <= 3
- Windows 환경이므로 `num_workers > 0` 관련 멀티프로세스 설정은 피해 주세요.
- `.env` 또는 시크릿은 커밋하지 마세요.
- 새 라이브러리는 반드시 `requirements.txt`에 추가해 주세요.

# 워크스페이스에서 이미 제공된 문서

현재 워크스페이스에 존재하는 문서만 참고하세요. (다른 외부 검색은 최소화하세요.)

- 최소: `REQUIREMENTS.md`(해당 task의 요구사항)
- 조건에 따라 추가로 다음 중 일부 또는 전체가 제공될 수 있습니다:
  - `docs/architecture.md`
  - `docs/api.md`
  - `docs/db.md`
  - `docs/adr/*.md`
  - `AGENTS.md` (전역 지침)

# 출력

- 코드는 `app/` 및 `tests/` 하위에 작성
- 실행 후 `pytest`, `ruff`, `mypy` 가 모두 위 품질 게이트를 만족해야 합니다.
- 완료되면 짧게 변경 요약을 한글로 출력해 주세요.

# TASK_ID

`<TASK_ID>` (러너가 실행 시점에 구체 task 이름으로 치환합니다. 예: `task-1-todo-crud`)
