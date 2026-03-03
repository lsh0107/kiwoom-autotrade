# 프로젝트 상태

## 현재 단계: 초기 설정

### 완료
- [x] .claude/ 설정 구성
- [x] 프로젝트 구조 설계
- [x] 증권사 REST API 리서치 (키움 + 한투 + LS증권) → `.claude/memory/research-broker-api.md`
- [ ] 기본 API 클라이언트 구현
- [ ] 인증/토큰 관리
- [ ] 시세 조회 기능
- [ ] 주문 실행 기능
- [ ] 포트폴리오 관리
- [ ] 투자 전략 엔진
- [ ] 알림 시스템
- [ ] 스케줄러/자동화

### 기술 스택 (확정)
- Python 3.11+
- httpx (비동기 HTTP)
- pydantic (데이터 모델)
- pydantic-settings (설정 관리)

### 기술 스택 (미정 → 리서치 완료, 확정 대기)
- DB: SQLite vs PostgreSQL
- 스케줄러: APScheduler vs 자체 구현
- 알림: Telegram vs Slack vs Email
- UI: **Web (FastAPI Backend + Next.js Frontend)** ← 리서치 결과 확정 방향
- 배포: Vercel (Frontend) + VPS Docker (Backend) ← 리서치 결과 확정 방향
- 실시간: WebSocket (FastAPI native)
- 인증: JWT + OAuth 2.0
- 상세: `.claude/memory/research-web-architecture.md` 참조
