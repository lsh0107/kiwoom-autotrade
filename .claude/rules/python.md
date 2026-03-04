---
paths:
  - "**/*.py"
  - "**/*.pyi"
---

# Python 코딩 규칙

## 버전 및 도구
- Python 3.12
- 패키지 관리: Poetry
- 린터/포매터: Ruff (설정: `pyproject.toml`)
- 타입 체크: mypy (점진적 strict, SQLAlchemy 모듈 예외)
- 테스트: pytest + pytest-asyncio

## 코드 스타일

### 네이밍
- 변수/함수: `snake_case`
- 클래스: `PascalCase`
- 상수: `UPPER_SNAKE_CASE`
- private: `_single_leading_underscore`
- 모듈: `snake_case.py`

### Type Hints
```python
# 모든 함수에 type hint 필수
def get_stock_price(symbol: str, market: str = "KRX") -> float:
    ...

# Optional은 명시적으로
def find_order(order_id: str) -> Order | None:
    ...

# 컬렉션은 구체적으로
def get_portfolio() -> dict[str, Position]:
    ...
```

### Docstring
```python
def place_order(
    symbol: str,
    quantity: int,
    price: float,
    order_type: OrderType = OrderType.LIMIT,
) -> OrderResult:
    """주문을 실행합니다.

    Args:
        symbol: 종목 코드 (예: "005930")
        quantity: 주문 수량
        price: 주문 가격
        order_type: 주문 유형 (기본값: 지정가)

    Returns:
        주문 실행 결과

    Raises:
        InsufficientFundsError: 잔고 부족 시
        InvalidOrderError: 유효하지 않은 주문 시
    """
```

### Import 순서
```python
# 1. 표준 라이브러리
import asyncio
from datetime import datetime

# 2. 서드파티
import httpx
from pydantic import BaseModel

# 3. 로컬
from src.api.client import KiwoomClient
from src.config import settings
```

## 아키텍처 패턴

### 설정 관리
```python
# pydantic-settings 사용
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    """앱 레벨 설정 (사용자별 API 키는 DB에서 관리)"""
    database_url: str
    jwt_secret_key: str
    is_mock_trading: bool = True  # 기본값: 모의투자

    model_config = SettingsConfigDict(env_file=".env")

# 사용자별 키움 API 키는 broker_credentials 테이블에서 AES-256 암호화 저장/로드
```

### 에러 처리
```python
# 커스텀 예외 계층 구조
class TradingError(Exception): ...
class APIError(TradingError): ...
class OrderError(TradingError): ...
class InsufficientFundsError(OrderError): ...
```

### 비동기 패턴
```python
# httpx async client 사용
async with httpx.AsyncClient() as client:
    response = await client.get(url, headers=headers)
```

## 테스트
- 테스트 파일: `tests/test_*.py`
- 픽스처: `tests/conftest.py`
- API 호출은 반드시 mock 처리
- 최소 커버리지: 85% (ADR-016, 85% 미만 커밋/PR 금지)
