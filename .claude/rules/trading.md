---
paths:
  - "src/trading/**"
  - "src/api/**"
  - "src/strategy/**"
  - "src/portfolio/**"
  - "src/broker/**"
---

# 트레이딩 시스템 보안 및 안전 규칙

## 절대 규칙 (위반 시 즉시 중단)

### 1. 자격 증명
- API 키, 시크릿은 절대 소스코드에 포함 금지
- `.env` 파일 또는 환경변수로만 관리
- 로그에 자격 증명 출력 금지 (마스킹 필수)

### 2. 주문 안전장치
```python
# 모든 주문 함수에 반드시 포함
MAX_ORDER_AMOUNT = 1_000_000  # 1회 최대 주문 금액 (원)
MAX_DAILY_ORDERS = 100         # 일일 최대 주문 횟수 (사용자별 설정 가능, 기본값 100, decisions-pending.md #5 확정)
REQUIRED_CONFIRMATION = True   # 주문 전 확인 필수

# 실거래 전환 시 별도 플래그 필요
IS_MOCK_TRADING = True  # 기본값: 모의투자
```

### 3. 실거래/모의투자 구분
- 기본값은 항상 모의투자 (is_mock_trading=True)
- 실거래 전환은 명시적 설정 변경 + 확인 절차 필요
- 실거래 모드에서는 주문 전 2중 확인
- 모의투자 API URL과 실거래 API URL 분리 관리

## API 사용 규칙

### 키움 REST API
- 요청 제한: 초당 최대 요청 수 준수 (rate limiting)
- 토큰 만료 관리: access token 자동 갱신
- 에러 응답 처리: 키움 에러코드별 적절한 처리
- 장 운영시간 확인: 장 마감 후 주문 방지

### 데이터 처리
- 시세 데이터는 항상 타임존 명시 (Asia/Seoul)
- 금액은 정수(원) 단위로 처리 (부동소수점 회피)
- 종목코드 유효성 검증 필수

## 로깅 규칙
```python
# 주문 관련은 반드시 로깅
logger.info("주문 실행", extra={
    "symbol": symbol,
    "quantity": quantity,
    "price": price,
    "order_type": order_type,
    "is_mock": settings.is_mock_trading,
})

# 민감 정보 마스킹
logger.debug("API 호출", extra={
    "app_key": mask_string(app_key),  # "abc***xyz"
})
```

## 백업 및 복구
- 포트폴리오 상태는 주기적으로 로컬 저장
- 주문 이력은 별도 DB/파일로 보존
- 비정상 종료 시 미체결 주문 확인 로직 필수
