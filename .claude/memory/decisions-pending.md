# 미결정 사항 추적

> design-v1.1 전문가 리뷰 + 전략 v2.0 전문가 토론에서 도출.
> **마지막 검토**: 2026-03-14
> **상태**: 3건 미결정 (#14,15,17,20), 6건 신규 확정 (#11,12,13,16,18,19). 새 미결정 사항 발생 시 이 문서에 추가할 것.

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

### ~~11. volume_ratio 최적값~~ → A) 1.5 복원
- **확정일**: 2026-03-14 (모의실전 -35% 결과 기반)
- **반영**: `src/backtest/strategy.py` MomentumParams.volume_ratio, `scripts/live_trader.py` CLI 기본값
- **근거**: 0.5 = 평균의 절반이면 진입 = 사실상 무조건 매수 → 승률 13%, -35% 손실. 1.5로 복원하면 의미 있는 거래량 돌파만 진입
- **향후**: 그리드서치 [1.0, 1.5, 2.0, 2.5]로 최적값 추가 탐색 예정

### ~~12. 익절 방식~~ → C) 혼합 (고정 TP + 트레일링)
- **확정일**: 2026-03-14
- **반영**: `src/backtest/strategy.py` check_exit_signal (trailing_stop_pct + take_profit)
- **근거**: v2.0에서 혼합 방식 구현 완료. peak_price 추적으로 트레일링 스톱 동작. ATR 동적은 Phase 2 추가 예정

### ~~13. 종목 유니버스~~ → 확장 (KOSPI 35 + KOSDAQ 31 = 66종목)
- **확정일**: 2026-03-14 (초기 30 → 66으로 확대)
- **반영**: `scripts/screen_symbols.py` UNIVERSE dict (66종목, 테마별 SECTOR_MAP 추가)
- **근거**: 표본 확대 + 테마 분산. 섹터별 포지션 제한과 함께 사용

### ~~16. 쿨다운 메커니즘~~ → A) 종목별 30분 + 연속 손절 3회 블랙리스트
- **확정일**: 2026-03-14 (모의실전 "고빈도 손절 머신" 패턴 확인)
- **반영**: `scripts/live_trader.py` TradingState에 cooldown/blacklist 추가
- **근거**: 같은 종목 손절 즉시 재매수 반복이 -35% 핵심 원인 중 하나

### ~~18. 테마/섹터 분류~~ → A) 하드코딩 SECTOR_MAP
- **확정일**: 2026-03-14
- **반영**: `scripts/screen_symbols.py` SECTOR_MAP dict
- **근거**: 즉시 적용 가능. Phase 3에서 LLM 동적 테마로 점진 전환. 같은 섹터 최대 1개 포지션 규칙 적용

### ~~19. 스윙 전략 overnight 보유 허용 범위~~ → A) 스윙 overnight 허용 + 갭다운 -3% 즉시 손절 + 보유기간 5일 제한
- **확정일**: 2026-03-14 (PR #142)
- **반영**: `scripts/live_trader.py` 스윙 overnight 보유 + 갭 리스크 처리 + 보유기간 제한
- **근거**: 단타(모멘텀) = 당일 15:15 강제청산, 스윙(평균회귀) = overnight 허용. 갭다운 -3% 즉시 손절로 갭 리스크 통제. 최대 5거래일로 무한 보유 방지.

---

## 현재 미결정 사항

> 형식: 번호, 배경, 선택지, 권장안, 트레이드오프
> **마지막 검토**: 2026-03-14

### 14. LLM 트리거 조건 세부 정의
- **배경**: 현재 "장 전반적 분위기 확인"만 명시. 구체적 트리거 기준 필요
- **선택지**: A) 뉴스 감성 분석 | B) 거시 지표 체크 | C) 섹터 모멘텀 | D) 복합
- **트레이드오프**: 정확도 vs API 비용/지연
- **결정 시점**: 전략 v1.0 백테스트 후 v1.1에서

### 15. 텔레그램 양방향 통신 아키텍처
- **배경**: 현재 단방향(시스템→사용자) 알림만 구현. 최종 목표는 사용자가 텔레그램으로 지시 → LLM이 해석 → 전략 수정/매매 실행
- **선택지**: A) Webhook (서버에 텔레그램이 push) | B) Long Polling (봇이 주기적 확인) | C) 혼합
- **하위 결정**:
  - LLM 모델 선택 (Claude vs GPT, 비용/속도 트레이드오프)
  - 명령 범위 (파라미터 수정만 vs 즉시 매매 포함)
  - 안전장치 (확인 단계 필요 여부, 금액 제한)
- **트레이드오프**: 편의성 vs 보안 리스크 (텔레그램으로 매매 명령은 인증/확인 필수)
- **결정 시점**: Phase 2-3, WebSocket 안정화 후
- **관련 문서**: `design-telegram-bidirectional.md`

### 17. LLM 통합 방식 (Phase 3)
- **배경**: LLM을 매매 시스템에 어떻게 통합할지. 현재 AIEngine._execute_signal이 직접 주문 내는 구조는 위험
- **선택지**:
  - A) **Decision support only** — 장전 브리핑(테마 스코어) + 장후 리뷰(파라미터 제안). LLM 결과로 진입 기준 ±20% 미세조정만 ← **전문가 합의 권장안**
  - B) Shadow mode — LLM 판단을 기록만 하고 실행 안 함 (검증용)
  - C) LLM 게이트키퍼 — 전략 시그널 + LLM 동의 시에만 진입 (과도 의존 우려)
- **하위 결정**: 모델 선택 (Claude Haiku ~$0.3/일 vs GPT-4o-mini), consensus 사용 여부
- **트레이드오프**: 비용/지연 vs 판단 품질. A안이 리스크 최소 + 점진 확장 가능
- **결정 시점**: Phase 2 완료 후, Phase 3 시작 시

### 20. 뉴스/공시 데이터 소스 선정 (Phase 3)
- **배경**: 테마 기반 종목 선정에 실시간 뉴스/공시 데이터 필요
- **선택지**:
  - A) DART OpenAPI + 네이버 금융 크롤링 (무료) ← **비용 최적**
  - B) DART + 한국거래소 정보시스템 + BigKinds (무료, 학술)
  - C) DART + 유료 뉴스 API (Naver News API 등)
  - D) A + B 혼합 (다원화)
- **트레이드오프**: 비용 $0 vs 데이터 품질/실시간성. 네이버 크롤링은 구조 변경 리스크 있음
- **결정 시점**: Phase 3 시작 시
- **관련**: `design-strategy-v2.md` Phase 3, #14 LLM 트리거 조건

---

## TODO (확정되었으나 코드 반영 미완)
- [x] trading.md의 MAX_DAILY_ORDERS 50 → 100으로 통일 (kill_switch.py 기본값 100)
- [x] momentum.py 진입 필터 복구 (PR #125, 2026-03-13)
- [x] volume_ratio 기본값 0.5 → 1.5 복원 (PR #125, 2026-03-13)
- [x] 쿨다운 → 단계적 리스크 관리로 대체 (2연패50%/3연패블랙, PR #131)
- [x] SECTOR_MAP 하드코딩 + 섹터당 1포지션 (PR #124, #131)
- [x] ATR 동적 SL/TP + 변동성 필터 (PR #131)
- [x] kill_switch 통합 (PR #131)
- [x] force_close 15:15 통일 (PR #131, #133)
