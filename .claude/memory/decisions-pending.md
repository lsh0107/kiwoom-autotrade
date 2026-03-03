# 미결정 사항 (사용자 결정 필요)

> design-v1.1 전문가 리뷰에서 도출. 구현 전 확정 필요.

---

## 1. AES-256 암호화 키 관리 방안
- **배경**: 사용자별 키움 API 키를 DB에 AES-256 암호화 저장. 암호화 키(DEK) 관리 필요.
- **선택지**:
  - A) `.env` 파일에 AES 키 저장 (단순, .env 유출 시 전체 복호화 가능)
  - B) macOS Keychain (로컬 Mac 전용, 가장 안전, 플랫폼 종속)
  - C) Docker secrets (컨테이너 내부에서만 접근, 중간 보안)
  - D) 별도 파일 + 파일 권한 제한 (600)
- **현재**: design-v1.1에서 "환경변수(.env)"로 변경됨 (Oracle Vault에서 전환)

## 2. Phase 1 프로세스 통신 방식
- **배경**: FastAPI(프로세스 1) + Trading Engine(프로세스 2) 분리 설계. 하지만 Phase 1은 asyncio.Queue(단일 프로세스 내 전용).
- **선택지**:
  - A) Phase 1에서는 단일 프로세스로 통합 (FastAPI 안에서 트레이딩 엔진 실행)
  - B) 처음부터 2 프로세스 + Unix socket/DB polling으로 통신
  - C) 처음부터 2 프로세스 + Redis pub/sub
- **권장**: A (MVP 빠른 출시 → Phase 2에서 분리)

## 3. JWT Refresh Token 저장 방식
- **배경**: Access Token 30분, Refresh Token 7일 설계.
- **선택지**:
  - A) Refresh Token도 httpOnly cookie (XSS 안전, CSRF 대응 필요)
  - B) DB 테이블(token_whitelist) + httpOnly cookie 조합
  - C) Redis에 저장 (빠른 검증, 서버 재시작 시 로그아웃)
- **권장**: A (단순, 가족 규모에서 충분)

## 4. 2FA(TOTP) 정책
- **배경**: 현재 "선택"으로 설계. 금융 시스템에서는 권장.
- **선택지**:
  - A) 완전 선택 (현재)
  - B) 실거래 모드 전환 시 필수
  - C) 모든 사용자 필수
- **권장**: B (모의투자는 자유롭게, 실거래는 보안 강화)

## 5. 일일 주문 한도
- **배경**: trading.md에 50건, design-v1.1에 100건으로 불일치.
- **선택지**:
  - A) 50건 (보수적)
  - B) 100건
  - C) 사용자별 설정 가능 (기본값 50 또는 100)
- **권장**: C (기본값 100, 사용자가 낮출 수 있게)

## ~~6. mypy strict 정책~~ → 결정됨
- **결정**: B (점진적 strict, SQLAlchemy 모듈 예외)
- **반영**: `pyproject.toml` [tool.mypy], `python.md`

## 7. Broker 추상화 시점
- **배경**: BrokerClient Protocol로 키움/KIS/mock 추상화 설계. MVP에서 필요한가?
- **선택지**:
  - A) Phase 1부터 Protocol 클래스 정의 (확장성 좋지만 개발 느림)
  - B) Phase 1은 키움 전용, 인터페이스 분리만 유지 (Phase 2에서 Protocol)
- **권장**: B

## 8. 프론트엔드 배포 위치
- **배경**: 로컬 Mac Docker로 변경됨. 프론트엔드를 어디서 서빙할지.
- **선택지**:
  - A) 로컬 Docker에서 Next.js도 컨테이너로 (올인원)
  - B) Vercel 무료 (프론트엔드만 별도 배포)
  - C) Cloudflare Pages 무료
- **현재**: design-v1.1에서 A(Docker 컨테이너)로 수정됨

## 9. CORS 허용 도메인
- **배경**: 배포 방식에 따라 달라짐.
- **선택지**:
  - A) Cloudflare Tunnel 도메인만 허용
  - B) localhost + Tunnel 도메인 (개발/운영 겸용)
  - C) 환경변수로 설정 가능하게
- **권장**: C

## ~~10. Python 버전~~ → 결정됨
- **결정**: B (Python 3.12)
- **반영**: `pyproject.toml`, `CLAUDE.md`, `python.md`, CI

---

> 각 항목에 대해 결정 후 이 문서를 업데이트하고, 해당 설계/규칙 문서에 반영할 것.
