# 미결정 사항 추적

> design-v1.1 전문가 리뷰에서 도출. Phase 1 구현 중 모두 확정됨.
> **마지막 검토**: 2026-03-05
> **상태**: 전체 확정 완료. 새 미결정 사항 발생 시 이 문서에 추가할 것.

---

## 확정 완료

### 1. AES-256 암호화 키 관리 방안 → A) `.env` 파일
- **확정일**: 2026-03-04 (Phase 1 계획 수립 시)
- **반영**: `src/utils/crypto.py` (Fernet 기반), `.env.example` (FERNET_KEY)
- **근거**: 가족 규모 시스템, 단순성 우선. macOS Keychain은 플랫폼 종속.
- **관련 ADR**: ADR-013 (기술 스택 — Fernet)

### 2. Phase 1 프로세스 통신 방식 → A) 단일 프로세스
- **확정일**: 2026-03-04
- **반영**: `src/main.py` (FastAPI + 트레이딩 엔진 통합)
- **근거**: MVP 속도, API 레이트 리밋이 병목이므로 멀티프로세스 이점 없음
- **관련 ADR**: ADR-004 (프로세스 분리 — Phase 2에서), ADR-014 논의 1 (asyncio vs multiprocessing)

### 3. JWT Refresh Token 저장 방식 → A) httpOnly cookie
- **확정일**: 2026-03-04
- **반영**: `src/utils/jwt.py`, `src/api/v1/auth.py`
- **근거**: 단순, XSS 안전, 가족 규모에서 Redis/DB 불필요
- **관련 ADR**: ADR-007

### 4. 2FA(TOTP) 정책 → Phase 1 생략
- **확정일**: 2026-03-04
- **반영**: User 모델에 totp_secret 컬럼은 유지 (Phase 2 대비)
- **근거**: 모의투자만 사용하는 Phase 1에서 2FA는 과잉. 실거래 전환 시 추가
- **Phase 2 할 일**: 실거래 모드 전환 시 2FA 필수로 변경

### 5. 일일 주문 한도 → C) 사용자별 설정 가능 (기본값 100)
- **확정일**: 2026-03-04
- **반영**: `src/trading/kill_switch.py` (max_daily_orders 매개변수), `src/models/strategy.py`
- **근거**: 사용자마다 전략 빈도가 다름. 기본 100은 보수적+유연
- **관련**: trading.md 50건 → 100건으로 통일 필요 (TODO)

### ~~6. mypy strict 정책~~ → B) 점진적 strict
- **확정일**: 2026-03-04
- **반영**: `pyproject.toml` [tool.mypy], `.claude/rules/python.md`

### 7. Broker 추상화 시점 → A) Phase 1부터 Protocol 정의 + KiwoomClient만 구현
- **확정일**: 2026-03-04
- **반영**: `src/broker/base.py` (BrokerClient Protocol), `src/broker/kiwoom.py` (구현)
- **근거**: Protocol 정의 자체는 오버헤드 거의 없음. 인터페이스 문서화 역할
- **관련 ADR**: ADR-001

### 8. 프론트엔드 배포 위치 → A) 로컬 Docker 올인원
- **확정일**: 2026-03-04
- **반영**: design-v1.1 섹션 13 (Docker Compose)
- **근거**: $0 비용, 단일 인프라 관리

### 9. CORS 허용 도메인 → C) 환경변수 설정
- **확정일**: 2026-03-04
- **반영**: `src/main.py` (CORS middleware), `.env.example` (CORS_ORIGINS)
- **근거**: 개발/운영 환경별 유연한 설정

### ~~10. Python 버전~~ → B) Python 3.12
- **확정일**: 2026-03-04
- **반영**: `pyproject.toml`, `CLAUDE.md`, CI

---

## 현재 미결정 사항

> 없음. 새 미결정 사항 발생 시 아래에 추가할 것.
> 형식: 번호, 배경, 선택지, 권장안, 트레이드오프

---

## TODO (확정되었으나 코드 반영 미완)
- [ ] trading.md의 MAX_DAILY_ORDERS 50 → 100으로 통일
