# 전수조사 — 사용자 결정 필요 항목

> 2026-03-22 전수조사에서 발견. 코드/설계 방향 결정이 필요한 항목들.

## ✅ 해결 완료

| # | 항목 | 처리 |
|---|------|------|
| M-02 | PUT /settings/trading 미구현 | design-001에 "❌ 제거 — broker_credentials.is_mock으로 관리" 반영 |
| M-04 | trade_logs 모델 구조 변경 | design-001 §6 trade_logs 스키마를 실제 코드 기준으로 갱신 |
| M-05 | exponential_backoff 미적용 | design-005 §8에서 제거 (retries 수정 시 함께 처리) |
| L-01 | invites.code VARCHAR(20→32) | design-001에 이미 반영 확인 |
| L-02 | orders.symbol VARCHAR(10→20) | design-001에 이미 반영 확인 |
| L-03 | is_active→is_auto_trading | design-001 §6 갱신 완료 |

## ⬜ 사용자 결정 대기 (3건)

### 1. sentiment_score 미사용 (M-10)
- **문서/DB**: news_articles 테이블에 sentiment_score 컬럼 존재 (default 0.0)
- **현황**: storage.py에서 INSERT 시 이 컬럼에 값을 넣지 않음
- **결정 필요**: 감성 분석 로직을 구현해서 채울 건지, 아니면 컬럼 제거할 건지?

### 2. pre-commit에 mypy 훅 추가 (M-14)
- **현황**: pyproject.toml에 strict mypy 설정이 있으나 pre-commit에 훅 없음
- **결정 필요**: mypy 검사를 pre-commit에 추가할 건지? (속도 영향 있음)

### 3. broker/token_store.py race condition (M-07)
- **현황**: 멀티유저 토큰 갱신 시 race condition 가능성
- **결정 필요**: 검토/수정 필요한지?
