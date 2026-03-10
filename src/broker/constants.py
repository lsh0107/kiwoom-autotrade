"""키움증권 REST API 상수 (API ID, 엔드포인트, 에러 코드)."""

# ── API ID (모의/실거래 동일, URL만 다름) ─────────────

API_IDS: dict[str, str] = {
    "token": "au10001",
    "buy": "kt10000",
    "sell": "kt10001",
    "cancel": "kt10003",
    "quote": "ka10007",  # 시세표성정보 (종목명+현재가+전일종가)
    "daily_price": "ka10086",  # 일별주가
    "orderbook": "ka10004",  # 주식호가
    "balance": "ka10085",  # 계좌수익률 (보유종목 상세)
    "deposit": "kt00001",  # 예수금상세현황 (주문가능현금) — 모의/실거래 모두 지원
    "balance_summary": "kt00018",  # 계좌평가잔고내역 (요약)
    "minute_chart": "ka10080",  # 주식분봉차트조회
    "daily_chart": "ka10081",  # 주식일봉차트조회
}

# ── 엔드포인트 (URL 경로) ────────────────────────────

ENDPOINTS: dict[str, str] = {
    "token": "/oauth2/token",
    "order": "/api/dostk/ordr",
    "market": "/api/dostk/mrkcond",
    "account": "/api/dostk/acnt",
    "chart": "/api/dostk/chart",
}

# ── 주문 조건단가 코드 (cond_uv) ─────────────────────

ORDER_COND_CODES: dict[str, str] = {
    "limit": "0",  # 지정가
    "market": "3",  # 시장가
}

# ── 거래소 구분 ──────────────────────────────────────

DEFAULT_EXCHANGE: str = "KRX"

# ── 키움 에러 코드 ───────────────────────────────────

ERROR_RATE_LIMIT: str = "1700"
ERROR_INVALID_TOKEN: str = "8005"  # noqa: S105

# ── 베이스 URL ───────────────────────────────────────

MOCK_BASE_URL: str = "https://mockapi.kiwoom.com"
REAL_BASE_URL: str = "https://api.kiwoom.com"

# ── 레이트 리밋 / 토큰 갱신 ─────────────────────────

MOCK_RATE_LIMIT: int = 4  # 실제 5/s이나 마진 확보 (429 방지)
REAL_RATE_LIMIT: int = 20
TOKEN_REFRESH_BUFFER_SECONDS: int = 300
