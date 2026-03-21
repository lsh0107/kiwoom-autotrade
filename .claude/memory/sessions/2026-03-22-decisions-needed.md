# 전수조사 — 사용자 결정 필요 항목

> 2026-03-22 전수조사에서 발견. 코드/설계 방향 결정이 필요한 항목들.

## 1. PUT /settings/trading 미구현 (M-02)
- **문서**: design-001에 "모의/실거래 전환 설정" 엔드포인트 명시
- **현황**: 구현 안 됨. DB의 `broker_credentials.is_mock` 필드로 관리 중
- **결정 필요**: 별도 엔드포인트 구현할 건지, 아니면 설계 문서에서 제거할 건지?

## 2. trade_logs 모델 구조 변경 미기록 (M-04)
- **문서**: design-001은 `(action, detail, ip_address)` 구조
- **현황**: 코드는 `(event_type, symbol, side, price, quantity, message, details, is_mock)`
- **결정 필요**: ADR로 기록할 건지? 아니면 design-001만 갱신하면 되는지?

## 3. Strategy 모델 `is_active` → `is_auto_trading` 필드명 변경 (L-03)
- **문서**: design-001은 `is_active`
- **현황**: 코드는 `is_auto_trading` + `kill_switch_active` 추가
- **결정 필요**: design-001 갱신만 하면 되는지?

## 4. Airflow exponential_backoff (M-05)
- **문서**: design-005 §8에 exponential_backoff 전략 언급
- **현황**: 어떤 DAG에도 미적용
- **결정 필요**: 실제 적용할 건지, 문서에서 삭제할 건지?

## 5. sentiment_score 미사용 (M-10)
- **문서/DB**: news_articles 테이블에 sentiment_score 컬럼 존재 (default 0.0)
- **현황**: storage.py에서 INSERT 시 이 컬럼에 값을 넣지 않음
- **결정 필요**: 감성 분석 로직을 구현해서 채울 건지, 아니면 컬럼 제거할 건지?

## 6. pre-commit에 mypy 훅 추가 (M-14)
- **현황**: pyproject.toml에 strict mypy 설정이 있으나 pre-commit에 훅 없음
- **결정 필요**: mypy 검사를 pre-commit에 추가할 건지? (속도 영향 있음)

## 7. invites.code VARCHAR(20→32), orders.symbol VARCHAR(10→20) (L-01/L-02)
- **현황**: design-001과 실제 코드 차이
- **결정 필요**: design-001을 코드 기준으로 갱신하면 되는지? (코드가 맞는 게 맞을 것)
