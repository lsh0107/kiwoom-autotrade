# 한국 증권사 API Rate Limits & 메시지 큐 리서치
> 리서치 날짜: 2026-03-03
> **마지막 검토**: 2026-03-05
> **상태**: 리서치 완료. 결정 사항 반영됨.
>
> **적용된 결정:**
> - 메시지 큐: asyncio.Queue (Phase 1) → Redis Streams (Phase 2 예정) — ADR-005
> - Rate Limiter: aiolimiter 채택 — ADR-013
> - 키움 REST API 사용 (초당 20건, 모의 5건) — `src/broker/kiwoom.py`에 구현
> - 키움 오류코드 `1700` = Rate Limit 초과, `8005` = 토큰 무효 — `docs/kiwoom-rest-api/README.md`에 전체 오류코드 정리
> - WebSocket 실시간 등록 최대 100개 종목 제한 확인 (유튜브 "주식코딩" 채널 + PDF 문서)

## 1. 키움증권 REST API Rate Limits (상세)

### 1A. 키움 REST API (신규 - openapi.kiwoom.com)
키움 REST API는 2025년 3월에 출시된 신규 서비스로, 공식 문서에서 구체적 수치 공개가 제한적임.

| 항목 | 제한 | 비고 |
|------|------|------|
| REST API 호출 | **초당 20건** | 조회+주문 통합 (커뮤니티/라이브러리 소스 기반) |
| WebSocket 동시 구독 | **40종목** (per connection) | kiwoom-restful 문서 기반 |
| WebSocket 연결 수 | **1개** (per connection) | 단일 연결 |
| 실시간 코드 등록 | **100개/그룹** (grp_no) | 여러 그룹 사용 가능 |
| Access Token 유효기간 | **24시간** | 자동 갱신 로직 권장 |
| 미접속 시 자동해지 | **3개월** | 매월 첫영업일 해지 |

### 1B. 키움 Open API+ (레거시 - OCX/Windows 전용)
레거시 API는 더 구체적인 rate limit 정보가 알려져 있음.

| 항목 | 제한 | 비고 |
|------|------|------|
| TR 조회 | **초당 5회** | 시세+관심종목+조건검색 합산 |
| 주문 | **초당 5회** | 국내주식/선물옵션 공통 |
| 시간당 조회 | **1,000회/시간** | 경험적 수치 |
| 조건검색 | **1분당 1회** (조건별) | 실시간 조건검색 수신은 별도 |
| 실시간 조건검색 | **최대 10개** 동시 | |
| SetRealReg | **100종목/1회 호출** | 추가등록(타입1)으로 누적 가능 |

### 1C. 키움 레거시 API 연속조회 페널티 (KOAPY 소스 기반)
KOAPY 라이브러리의 RateLimiter 구현에서 발견된 구체적 수치:

| 패턴 | 대기시간 | 설명 |
|------|----------|------|
| 초당 5회 x 1회 버스트 | **17초** 대기 | 한 번 5/s 조회 후 |
| 초당 5회 x 5연속 버스트 | **90초** 대기 | 연속 5번 5/s 조회 후 |
| 초당 5회 x 10연속 버스트 | **180초** (3분) 대기 | 연속 10번 5/s 조회 후 |
| 총 누적 | **1,000회/시간** | 시간당 제한 |

KOAPY의 Cascading Time Window 구현:
```
18초 창: 최대 5건
90초 창: 최대 25건
180초 창: 최대 50건
3600초 창: 최대 1,000건
```

---

## 2. 한국투자증권 (KIS) API Rate Limits (상세)

### 2A. REST API
| 항목 | 실전투자 | 모의투자 | 비고 |
|------|---------|---------|------|
| 초당 요청 제한 | **20건/초** | **5건/초** | 공식 |
| 에러 코드 | `EGW00201` | `EGW00201` | 유량 초과 시 |
| 실용적 안전 마진 | **15건/초** | **4건/초** | 커뮤니티 권장 |

### 2B. Access Token
| 항목 | 제한 | 비고 |
|------|------|------|
| 유효기간 | **24시간** (익일 07시까지) | |
| 재발급 간격 | **1분당 1회** | 잦은 발급 시 이용 제한 가능 |
| 갱신 가능 주기 | **6시간** | |
| 권장 | 하루 1회 발급, 파일 저장 후 재사용 | |

### 2C. WebSocket
| 항목 | 제한 | 비고 |
|------|------|------|
| 세션당 종목 구독 | **41개** | 핵심 제약 |
| 세션:접속키 | **1:1** | 접속키 1개 = 세션 1개 |
| 무한 연결시도 | **차단** | 2026.02.24 정책 시행 |

### 2D. WebSocket 41종목 제한 우회 (다중 계좌)
- 원리: 1 계좌 = 1 WebSocket 접속키 = 1 세션 = 41종목
- 2계좌 사용 시: 82종목 모니터링 가능
- 구현: KisWebSocketSessionManager로 다중 세션 관리
- 주의: ReentrantLock으로 thread-safe 구독/해제
- 중복 구독 방지: 이미 구독 중인 종목은 재요청하지 않음
- 세션 초기화: 08:59 KST (장 시작 전)

---

## 3. 기타 증권사 Rate Limits (참고)

### 대신증권 크레온 API
| 항목 | 제한 |
|------|------|
| 시세 조회 | **15초당 60건** (4건/초) |
| 실시간 조회 | **최대 400건** |
| 주문 관련 | **15초당 20건** (~1.3건/초) |

### 이베스트 Xing API
| 항목 | 제한 |
|------|------|
| 모의투자 | **초당 10건** |
| 실전투자 | 미공개 |

---

## 4. Kafka vs 대안: 개인 자동매매 시스템용 분석

### 4A. 우리 시스템의 실제 처리량 요구사항
```
최대 API 호출: 20건/초 (KIS) or ~20건/초 (키움 REST)
WebSocket 메시지: 40-100종목의 실시간 체결/호가
내부 이벤트: 매매 시그널, 주문 상태, 포트폴리오 업데이트
총 예상 메시지: 100-500 msg/sec (피크)
```

### 4B. Kafka 리소스 요구사항
| 항목 | 최소 | 권장 |
|------|------|------|
| RAM | **1GB** (Docker 기본) | **8-16GB** |
| CPU | 1 core | 2+ cores |
| 디스크 | 수 GB+ | SSD 권장 |
| JVM Heap | 1GB | **6GB** |
| 추가 필요 | ZooKeeper (또는 KRaft) | 별도 프로세스 |
| Docker 이미지 | ~500MB+ | |

### 4C. Redis 리소스 요구사항
| 항목 | 최소 | 권장 |
|------|------|------|
| RAM | **25-50MB** (기본) | **128MB** |
| CPU | 거의 없음 | 1 core |
| Docker 이미지 | ~30MB (Alpine) | |

### 4D. asyncio.Queue (Python 내장)
| 항목 | 값 |
|------|-----|
| RAM | **~0MB** (Python 프로세스 내) |
| CPU | Python 프로세스와 공유 |
| 외부 의존성 | **없음** |
| 설정/운영 | **제로** |
| 지속성 | 없음 (프로세스 종료 시 소멸) |

### 4E. 비교 분석 결론

| 기준 | Kafka | Redis Streams | Redis Pub/Sub | asyncio.Queue |
|------|-------|---------------|---------------|---------------|
| **처리량** | 100만+/s | 10만+/s | 6천/s | 1만+/s (in-proc) |
| **지연시간** | ms | sub-ms | sub-ms | **us** (마이크로초) |
| **메시지 지속성** | O | O | X | X |
| **메시지 재생** | O | O | X | X |
| **운영 복잡도** | 매우 높음 | 낮음 | 매우 낮음 | **없음** |
| **외부 의존성** | JVM+ZK | Redis server | Redis server | **없음** |
| **RAM 오버헤드** | 1-8GB | 25-128MB | 25-128MB | **0** |
| **분산 지원** | O | O | O | X (단일 프로세스) |
| **에러 복구** | O (replay) | O (ACK) | X | X |
| **학습 곡선** | 높음 | 중간 | 낮음 | **매우 낮음** |

### 4F. 최종 권장사항

**Kafka는 이 프로젝트에 확실히 과도함 (overkill):**
- 우리 최대 처리량: ~500 msg/sec → Kafka 처리 가능량의 0.05%
- RAM 8GB를 메시지 큐에만 사용하는 것은 비합리적
- ZooKeeper/KRaft 관리 부담
- 단일 사용자, 단일 머신 환경에서 분산 시스템 불필요

**권장 아키텍처 (단계별):**

1. **Phase 1 (MVP)**: `asyncio.Queue` 만 사용
   - Python 내장, 제로 설정
   - 우리 규모에 충분한 처리량
   - WebSocket 수신 → Queue → 전략 엔진 → Queue → 주문 실행
   - 단점: 프로세스 다운 시 메시지 소실

2. **Phase 2 (안정화)**: `asyncio.Queue` + SQLite/파일 로깅
   - 주문 이벤트를 SQLite에 기록하여 감사 추적
   - 프로세스 재시작 시 미체결 주문 복구
   - 여전히 외부 의존성 없음

3. **Phase 3 (필요 시)**: Redis Streams 추가
   - 조건: 다중 프로세스/서비스 간 통신 필요 시
   - 조건: 메시지 지속성/재생이 필수적일 때
   - Redis는 이미 캐시/세션 관리 등에도 활용 가능
   - RAM 오버헤드 최소

4. **Phase 4 (절대 필요 없을 가능성 높음)**: Kafka
   - 조건: 수백 개 종목, 다수 전략, 다중 서버 환경
   - 일반 개인 투자자에겐 도달하기 어려운 규모

---

## 5. Rate Limit 핸들링 전략

### 5A. Python Rate Limiter 라이브러리

| 라이브러리 | 알고리즘 | async 지원 | 특징 |
|-----------|---------|-----------|------|
| **aiolimiter** | Leaky Bucket | O | asyncio 네이티브, 경량 |
| **pyrate-limiter** | Leaky Bucket | O (sync도) | SQLite/Redis 백엔드 |
| **limiter** | Token Bucket | O | 데코레이터/컨텍스트 매니저 |
| **asynciolimiter** | Token Bucket | O | 순수 asyncio |
| **throttled-py** | 다중 (Fixed/Sliding/Token/Leaky/GCRA) | O | Redis 백엔드 지원 |

### 5B. 실용적 구현 예시

```python
from aiolimiter import AsyncLimiter

# 키움 REST API: 초당 20건 (안전 마진 적용 → 15건)
kiwoom_limiter = AsyncLimiter(15, 1)

# KIS API: 초당 20건 (안전 마진 적용 → 15건)
kis_limiter = AsyncLimiter(15, 1)

# KIS 모의투자: 초당 5건 (안전 마진 → 4건)
kis_mock_limiter = AsyncLimiter(4, 1)

async def api_call(limiter, func, *args):
    async with limiter:
        return await func(*args)
```

### 5C. kiwoom-restful 내장 Rate Limiting
- Client 레이어에서 자동으로 HTTP 요청 횟수 제한 관리
- "초당 Http 연결/호출 제한 자동관리" 기능 내장
- 별도 rate limiter 구현 불필요 (라이브러리 사용 시)

### 5D. KOAPY Rate Limiter 참고 구현
- 4단계 cascading time window 방식
- 18초/90초/180초/3600초 각각 다른 limit 적용
- 가장 보수적이고 안전한 방식
- 참고: https://koapy.readthedocs.io/

### 5E. Rate Limit 초과 시 처리
```python
# KIS API EGW00201 에러 처리 패턴
async def safe_api_call(func, *args, max_retries=3):
    for attempt in range(max_retries):
        try:
            result = await func(*args)
            if result.get('rt_cd') == '1' and 'EGW00201' in result.get('msg_cd', ''):
                await asyncio.sleep(1)  # 1초 대기 후 재시도
                continue
            return result
        except Exception as e:
            if attempt < max_retries - 1:
                await asyncio.sleep(2 ** attempt)  # exponential backoff
            else:
                raise
```

---

## 6. WebSocket 상세 스펙

### 6A. 키움 REST API WebSocket
| 항목 | 값 |
|------|-----|
| **실시간 등록 종목 상한** | **최대 100개** (핵심 제약) |
| 동시 구독 종목 | **40종목** (per connection) |
| 코드 등록 단위 | **100개/그룹** (grp_no) |
| 데이터 타입 | 주식체결, 호가잔량, 호가, 예상체결, 종목정보 등 |
| 연결 방식 | WSS (TLS) |
| ping/pong | 자동 처리 (kiwoom-restful) |
| 안전 마진 | **95개** 권장 (100개 경계 불안정 방지) |

### 6A-1. 100개 종목 제한 우회 방안 (유튜브 "주식코딩" 채널)
- **LS증권 WebSocket 병행 사용**: 실시간 시세 수신만 LS증권으로 교체 (등록 제한 없음)
- **키움은 주문/계좌/조건검색 전용**: 나머지 기능은 키움 REST API 그대로 유지
- **구현 패턴**: 2개 WebSocket 프로세스 (키움: 조건검색/주문체결, LS: 실시간 시세)
- **Queue 분배**: 실시간 등록/해제는 LS 프로세스에서 처리, 나머지는 키움 프로세스로 재전송
- **주의**: 1,000개+ 종목 동시 트래킹 시 시스템 리소스 부족 가능
- **우리 시스템 적용 여부**: Phase 1에서는 100개 이내로 충분. Phase 2에서 조건검색 종목이 많아지면 검토

### 6B. 한국투자증권 WebSocket
| 항목 | 값 |
|------|-----|
| 동시 구독 종목 | **41종목** (per session) |
| 세션:접속키 | **1:1** |
| 데이터 타입 | 국내주식체결, 국내주식호가, 해외주식체결 등 |
| 연결 방식 | WSS |
| 재연결 | python-kis가 자동 재연결 + 구독 복원 |
| 무한연결시도 차단 | 2026.02.24부터 IP/앱키 차단 |

### 6C. WebSocket Reconnection 전략
```python
# 권장 재연결 패턴
RECONNECT_DELAYS = [1, 2, 4, 8, 16, 30, 60]  # 초

async def reconnect_with_backoff(ws_client):
    for delay in RECONNECT_DELAYS:
        try:
            await ws_client.connect()
            await ws_client.resubscribe_all()  # 기존 구독 복원
            return
        except Exception:
            await asyncio.sleep(delay)
    raise ConnectionError("WebSocket reconnection failed after all retries")
```

### 6D. KIS WebSocket 정상 사용 패턴 (차단 방지)
```
1. 연결 (connect)
2. 종목 구독 (subscribe)
3. 데이터 수신 (receive)
4. 불필요 종목 구독 해제 (unsubscribe)
5. 연결 종료 (disconnect)
```
- 무한 연결/해제 반복 금지
- 정상적인 lifecycle 준수 필요

---

## 7. 핵심 결론 요약

1. **키움 REST API**: 초당 ~20건, WebSocket **최대 100개 종목** (핵심 제약), 40종목/connection
2. **키움 오류코드 `1700`**: Rate Limit 초과 시 반환 — 재시도 로직 필수
3. **KIS API**: 초당 20건(실전)/5건(모의), WebSocket 41종목/세션
3. **Kafka는 확실히 overkill** - 500 msg/sec도 안 되는 규모에 Kafka는 불필요
4. **asyncio.Queue가 MVP에 최적** - 제로 의존성, 충분한 성능
5. **필요 시 Redis Streams로 확장** - 다중 프로세스/지속성 필요 시
6. **Rate limiter**: aiolimiter 또는 라이브러리 내장 기능 활용
7. **WebSocket 재연결**: exponential backoff + 구독 복원 패턴 필수
