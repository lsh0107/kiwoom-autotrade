# 프로젝트 상태

## 현재 단계: Phase 1 (MVP 구현 중)

### 완료
- [x] .claude/ 설정 구성
- [x] 프로젝트 구조 설계
- [x] 증권사 REST API 리서치 (키움 + 한투 + LS증권) -> `.claude/memory/research-broker-api.md`
- [x] 시스템 설계 v1.1 확정 -> `.claude/memory/design-v1.1.md`
- [x] 아키텍처 결정 기록 (ADR-001~012) -> `.claude/memory/architecture.md`
- [x] 보안 3단계 방어 구축 (Claude 훅 + pre-commit + GitHub Actions)
- [x] 브랜치 전략 확정 (claude -> feat/* -> dev(PR) -> main(PR))
- [x] 프로젝트 디렉토리 구조 생성 (src/, tests/, scripts/, alembic/, frontend/)
- [x] 보안 훅 검증 및 수정 (시크릿 패턴 강화, .env 읽기 차단, NotebookEdit 추가)
- [x] 활동 로깅 훅 추가 (PostToolUse, 민감정보 마스킹)
- [x] .env.example 모의/실투자 분리 키 반영
- [x] .gitignore 보강 (Node.js, Docker, 활동로그, poetry.lock 커밋)

### 미완료 (Phase 1 MVP — 우선순위 변경 반영)
- [ ] FastAPI 앱 기본 세팅 + DB 연결
- [ ] 키움 모의투자 API 연동 (인증/토큰 관리, BrokerClient 추상화)
- [ ] 시세 조회 (REST)
- [ ] 주문 실행 (매수/매도/취소, 상태 머신)
- [ ] LLM 자동매매 엔진 (실시간 분석 → 매수/매도 판단 → 주문) ← **Phase 5에서 승격**
- [ ] Kill Switch 기본 구현
- [ ] 사용자 인증 (JWT httpOnly cookie + 초대 기반 가입)

### 보류 (Phase 2+)
- [ ] 멀티유저 + 초대 가입 완성
- [ ] 모의 ↔ 실투자 전환 UI
- [ ] Next.js 프론트엔드 UI
- [ ] Docker Compose 배포
- [ ] 텔레그램 알림

### 기술 스택 (확정)
| 계층 | 기술 |
|------|------|
| Backend | FastAPI / Python 3.12 (Uvicorn 1 worker async) |
| Frontend | Next.js 14+ / TypeScript / Tailwind CSS / ShadCN UI |
| DB | PostgreSQL 16 (Docker) |
| ORM | SQLAlchemy 2.0 (async) |
| HTTP | httpx (async) |
| 키움 API | BrokerClient Protocol 래핑 |
| 인증 | JWT httpOnly cookie + Refresh Token + 초대 코드 |
| 스케줄러 | APScheduler |
| 알림 | Telegram Bot |
| 메시지 큐 | Phase 1: asyncio.Queue -> Phase 2: Redis Streams |
| 배포 | 로컬 Mac (Apple Silicon) Docker Compose + Cloudflare Tunnel |
| SSL | Cloudflare Tunnel (자동) |
| CI/CD | GitHub Actions |
| 로깅 | structlog (JSON) |

### 배포 방식
- **서버**: 로컬 Mac (Apple Silicon) + Docker Compose
- **개발**: DB만 Docker, Python/Next.js는 네이티브 (하이브리드)
- **프로덕션**: 전부 Docker Compose
- **외부 접근**: Cloudflare Tunnel (HTTPS 자동, $0/월)
- **비용**: $0/월

### 브랜치 전략
```
claude (base) -> feat/* (기능 개발) -> dev (PR 머지) -> main (PR 머지, 배포)
```

### 참조 문서
- 시스템 설계: `.claude/memory/design-v1.1.md`
- 아키텍처 결정: `.claude/memory/architecture.md`
- 증권사 API 리서치: `.claude/memory/research-broker-api.md`
