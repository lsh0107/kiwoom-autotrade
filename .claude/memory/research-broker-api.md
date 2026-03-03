# 한국 증권사 REST API 리서치 결과
> 리서치 날짜: 2026-03-03

## 1. 키움증권 REST API (NEW - 2025년 3월 24일 출시)

### 핵심 요약
- **키움증권이 드디어 REST API를 출시함** (2025년 3월 24일)
- 기존 OCX(Open API+)는 Windows 전용이었으나, REST API는 **Mac/Linux/Windows 모두 지원**
- 공식 포털: https://openapi.kiwoom.com

### 지원 범위
- **국내주식만** (ETF/ETN 포함) - 해외주식 미지원
- 매매 주문, 시세 조회, 계좌 조회, 차트 데이터, 조건검색, 랭킹 정보
- WebSocket 실시간 데이터 지원 (호가잔량, 주식체결)
- 모의투자 환경 제공

### Rate Limit
- 조건검색: 시세조회+관심종목조회 합산 **초당 5회**, 조건별 1분당 1회
- 일반 API 호출: 정확한 수치 미공개 (공식 문서 참조 필요)

### 신청 요건
- 키움증권 계좌 필수
- HTS ID 연결 필요
- 홈페이지 > 트레이딩 채널 > 키움 REST API에서 신청
- 모바일 신청 불가
- **3개월 연속 미사용 시 자동 해지**

### 수수료
- 영웅문4 수수료율과 동일 적용
- REST API 출시 기념 이벤트 진행 중 (거래 시 현금 지급)

### 계좌 유형
- 위탁 종합, 중개형ISA, 연금저축, 비과세 종합 계좌 모두 가능

### Python 라이브러리
- **kiwoom-restful** (pip install kiwoom-restful)
  - 버전: 0.2.7 (2025-09-16)
  - Python 3.10+ (3.11+ 권장)
  - 비동기 HTTP + WebSocket
  - 자동 rate limiting 관리
  - MIT 라이선스
  - GitHub: https://github.com/breadum/kiwoom-restful
  - 문서: https://breadum.github.io/kiwoom-restful/latest/api

### 한계점
- **해외주식 거래 불가** (국내주식만)
- 비교적 새로운 서비스 (2025-03 출시)
- 커뮤니티/생태계가 아직 작음 (15 stars)
- AI 코딩 어시스턴트 기능 추가 예정 (2025-04 이후)

---

## 2. 한국투자증권 REST API (KIS Developers) - 가장 성숙한 옵션

### 핵심 요약
- **한국에서 가장 오래되고 성숙한 REST API** (키움보다 훨씬 먼저 출시)
- Mac/Linux/Windows 모두 지원
- 공식 포털: https://apiportal.koreainvestment.com

### 지원 범위 (가장 넓음)
- **국내주식** (KOSPI, KOSDAQ, ETF/ETN)
- **해외주식** (미국 NYSE/NASDAQ, 일본, 중국, 홍콩 등)
- **국내 선물/옵션**
- **해외 선물/옵션**
- **장내채권**
- 주문, 시세, 계좌, 차트, 조건검색, 랭킹, 실시간 등 전 기능

### Rate Limit (구체적)
- **실전투자: 초당 20건** (REST API)
- **모의투자: 초당 5건** (REST API)
- WebSocket: 세션당 **41개 종목** 구독 가능
- 서버 측 sliding window 방식으로 enforcement
- 경계점에서 요청 몰림 시 `EGW00201` 에러 발생 가능

### 인증 방식
- AppKey + AppSecret으로 Access Token 발급
- Access Token은 익일 07시까지 유효
- WebSocket은 별도 접속키 발급

### 모의투자
- **무료** 모의투자 환경 제공
- 별도 모의투자 계좌 신청 필요
- API 사용에 따른 별도 이용료 없음

### Python 라이브러리들
1. **python-kis** (pip install python-kis) -- 추천
   - 버전: 2.1.3, Python 3.11+
   - 256 stars, 83 forks
   - 완벽한 Type Hints
   - WebSocket 자동 재연결
   - 국내+해외주식 통합 인터페이스
   - GitHub: https://github.com/Soju06/python-kis

2. **mojito** (pip install mojito2)
   - 89 stars, 43 forks
   - 국내+미국주식 지원
   - WebSocket 지원 (실시간 체결, 호가, 주문)
   - GitHub: https://github.com/sharebook-kr/mojito
   - WikiDocs 가이드: https://wikidocs.net/book/7845

3. **공식 샘플 코드**
   - GitHub: https://github.com/koreainvestment/open-trading-api
   - Python/Java/Go/Kotlin 예제

---

## 3. LS증권 (구 이베스트투자증권) REST API

### 핵심 요약
- XingAPI (COM/DLL 기반) + 새로운 REST API 지원
- 공식 포털: https://openapi.ls-sec.co.kr
- REST API는 크로스플랫폼 지원

### 특징
- AppKey + AppSecret 기반 인증
- Access Token 매일 갱신 필요 (익일 07시 만료)
- 개발자 콘솔에서 테스트 가능
- 상세 정보 제한적 (키움/한투 대비)

---

## 4. 기타 증권사 API (Windows 전용, 비추천)

| 증권사 | API 이름 | 방식 | 플랫폼 |
|--------|---------|------|--------|
| 대신증권 | CYBOS Plus | COM | Windows only |
| NH투자증권 | QV Open API | DLL | Windows only |
| 유안타증권 | T-Trader | DLL/COM | Windows only |
| 유진투자증권 | Champion | OCX/DLL | Windows only |
| 삼성증권 | - | - | 기관 전용 (유료) |

---

## 5. 최종 비교표

| 항목 | 키움 REST API | 한국투자증권 KIS | LS증권 |
|------|-------------|----------------|--------|
| 출시 | 2025-03 | ~2022 | ~2023 |
| 국내주식 | O | O | O |
| 해외주식 | **X** | **O** (미국,일본,중국,홍콩) | ? |
| 선물/옵션 | X | O | ? |
| 채권 | X | O | ? |
| WebSocket | O | O | ? |
| 모의투자 | O | O (무료) | O |
| REST Rate | 초당 ~5 | 초당 20 (실전) / 5 (모의) | 미공개 |
| WS 종목수 | 100개/그룹 | 41개/세션 | 미공개 |
| Python lib | kiwoom-restful | python-kis, mojito | - |
| 생태계 크기 | 작음 (신규) | 큼 (성숙) | 작음 |
| 계좌 필요 | O | O | O |
| 무료 | O | O | O |
| Mac/Linux | O | O | O |

---

## 6. 결론 및 추천

### Mac/Linux 자동매매 최적의 선택: **한국투자증권 KIS API**

**이유:**
1. **해외주식 지원** - 미국주식 자동매매 가능 (키움은 국내주식만)
2. **성숙한 생태계** - python-kis (256 stars), mojito 등 잘 만들어진 라이브러리
3. **넉넉한 Rate Limit** - 실전 초당 20건
4. **풍부한 문서/예제** - 공식 GitHub, WikiDocs 가이드 다수
5. **무료 모의투자** - 실자금 없이 개발/테스트 가능
6. **전 상품 지원** - 국내주식, 해외주식, 선물옵션, 채권

### 키움 REST API도 고려할 경우
- 국내주식만 거래한다면 키움도 좋은 선택
- 키움은 국내 주식시장 점유율 1위
- 키움 REST API는 새로 나와서 개선 여지가 많음
- 키움+한투 병행도 가능 (국내는 키움, 해외는 한투)

### 프로젝트 전략 제안
1. **Primary**: 한국투자증권 KIS API (python-kis 라이브러리)
2. **Secondary**: 키움 REST API (kiwoom-restful) - 국내주식 보조
3. **추상화 레이어** 구현하여 두 API를 통합 인터페이스로 관리
