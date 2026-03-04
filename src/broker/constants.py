"""키움증권 REST API 상수 (엔드포인트, tr_id 매핑)."""

# ── 모의투자 tr_id ────────────────────────────────────

MOCK_TR_IDS: dict[str, str] = {
    "buy": "VTTC0802U",
    "sell": "VTTC0801U",
    "cancel": "VTTC0803U",
    "balance": "VTTC8434R",
    "quote": "FHKST01010100",
    "orderbook": "FHKST01010200",
    "daily_price": "FHKST01010400",
}

# ── 실거래 tr_id ──────────────────────────────────────

REAL_TR_IDS: dict[str, str] = {
    "buy": "TTTC0802U",
    "sell": "TTTC0801U",
    "cancel": "TTTC0803U",
    "balance": "TTTC8434R",
    "quote": "FHKST01010100",
    "orderbook": "FHKST01010200",
    "daily_price": "FHKST01010400",
}

# ── API 경로 ──────────────────────────────────────────

ENDPOINTS: dict[str, str] = {
    "token": "/oauth2/tokenP",
    "quote": "/uapi/domestic-stock/v1/quotations/inquire-price",
    "orderbook": "/uapi/domestic-stock/v1/quotations/inquire-asking-price-exp-ccn",
    "daily_price": "/uapi/domestic-stock/v1/quotations/inquire-daily-price",
    "order": "/uapi/domestic-stock/v1/trading/order-cash",
    "cancel": "/uapi/domestic-stock/v1/trading/order-rvsecncl",
    "balance": "/uapi/domestic-stock/v1/trading/inquire-balance",
}

# ── 기타 상수 ─────────────────────────────────────────

# 주문 유형 코드 (키움 API)
ORDER_TYPE_CODES: dict[str, str] = {
    "limit": "00",  # 지정가
    "market": "01",  # 시장가
}

# 레이트 리밋 (초당 요청 수)
MOCK_RATE_LIMIT: int = 5
REAL_RATE_LIMIT: int = 20

# 토큰 갱신 여유 시간 (초) - 만료 5분 전 갱신
TOKEN_REFRESH_BUFFER_SECONDS: int = 300

# 모의투자 URL
MOCK_BASE_URL: str = "https://openapivts.koreainvestment.com:29443"

# 실거래 URL
REAL_BASE_URL: str = "https://openapi.koreainvestment.com:9443"
