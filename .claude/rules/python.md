---
paths:
  - "**/*.py"
  - "**/*.pyi"
---

# Python 코딩 규칙

## 도구
- Python 3.12 / Poetry / Ruff / mypy (점진적 strict) / pytest + pytest-asyncio

## 스타일
- 변수/함수: `snake_case`, 클래스: `PascalCase`, 상수: `UPPER_SNAKE_CASE`
- 모든 함수에 type hint 필수 (`Order | None` 형식, Optional 미사용)
- docstring 한글, Google 스타일 (Args/Returns/Raises)
- import 순서: 표준 → 서드파티 → 로컬 (Ruff가 자동 정렬)

## 아키텍처
- 설정: pydantic-settings (`BaseSettings`, `.env` 로드)
- 에러: 커스텀 예외 계층 (`TradingError` → `APIError` / `OrderError`)
- 비동기: `httpx.AsyncClient`, `SQLAlchemy async session`

## 테스트
- 파일: `tests/test_*.py`, 픽스처: `tests/conftest.py`
- API 호출 반드시 mock (respx)
- 커버리지 85%+ (미만 시 커밋/PR 금지)
