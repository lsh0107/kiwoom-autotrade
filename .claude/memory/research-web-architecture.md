# Web Architecture Research - 2026-03-03

## 연구 주제: 주식 자동매매 웹 애플리케이션 아키텍처

### 1. Vercel Frontend + Docker Backend 연결 가능성
- **결론: 완전히 가능**
- Vercel에 배포된 Next.js 프론트엔드는 외부 Docker 백엔드에 HTTP/WebSocket으로 연결 가능
- CORS 설정 필수: Access-Control-Allow-Origin에 Vercel 도메인 명시
- OPTIONS preflight 핸들러 필수
- Next.js API Routes를 프록시로 활용 가능 (CORS 우회)

### 2. 추천 아키텍처
```
[Vercel - Next.js Frontend]
        |
        | HTTPS / WSS
        v
[VPS/Cloud - Nginx Reverse Proxy]
        |
        v
[Docker - FastAPI Backend]
        |
        ├── REST API (주문, 조회)
        ├── WebSocket (실시간 시세)
        └── Scheduler (자동매매 전략)
               |
               v
        [키움 REST API / WebSocket]
```

### 3. 배포 옵션 비교
| 옵션 | 비용 | 장점 | 단점 |
|------|------|------|------|
| AWS EC2/ECS | $10-50/월 | 안정적, 확장성 | 복잡한 설정 |
| GCP Cloud Run | $0-20/월 | 서버리스, 자동 스케일링 | 콜드 스타트 |
| VPS (Vultr/DO) | $5-10/월 | 저렴, 심플 | 직접 관리 필요 |
| 홈 서버 | 전기세만 | 완전 제어 | 고정IP 필요, 안정성 |

### 4. 인증/보안
- JWT + OAuth 2.0 조합 권장
- 단기 Access Token + 장기 Refresh Token 패턴
- IP 화이트리스트로 API 키 보호
- Rate Limiting 필수

### 5. 참고 오픈소스 프로젝트
- DariusLukasukas/stocks (Next.js 14 + Yahoo Finance)
- marketcalls/trading-dashboard (React + Tailwind)
- koreainvestment/open-trading-api (한국투자 공식 예제)
- stock-price-calculator/tradingbot (키움 자동매매)

### 6. 기술 스택 결정 (제안)
- **Frontend**: Next.js 14+ / React / Tailwind CSS / Shadcn UI
- **Backend**: FastAPI / Python 3.11+ / Uvicorn
- **실시간**: WebSocket (FastAPI native)
- **인증**: JWT (PyJWT) + OAuth2 (FastAPI Security)
- **DB**: PostgreSQL (Docker) 또는 SQLite (경량)
- **배포**: Vercel (Frontend) + VPS Docker (Backend)
- **역방향 프록시**: Nginx + Let's Encrypt SSL
