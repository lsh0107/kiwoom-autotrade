# 텔레그램 양방향 통신 설계

> **상태**: 활성 — 구현 대기 (Phase 3-8)
> 작성일: 2026-03-11
> 관련: decisions-pending.md #15, design-007-websocket.md
> 전제: 단방향 알림 완료 (PR #101), WebSocket 안정화 후 착수

## 현재 vs 목표

```
[현재 — 단방향]
시스템 → TelegramNotifier.send_*() → 사용자 수신

[목표 — 양방향]
사용자가 텔레그램 메시지 전송
  → Telegram Bot 수신 (webhook/polling)
  → LLM(Claude) 메시지 해석
  → 전략 파라미터 수정 or 즉시 매매 명령
  → 실행 결과 텔레그램 회신
```

## 아키텍처

```
┌─────────────┐     ┌──────────────────┐     ┌─────────────┐
│  사용자      │────→│  Telegram Bot    │────→│  명령 파서   │
│  (텔레그램)  │←────│  (webhook/poll)  │←────│  (LLM)      │
└─────────────┘     └──────────────────┘     └──────┬──────┘
                                                     │
                                              ┌──────▼──────┐
                                              │  명령 실행기  │
                                              │  - 전략 수정  │
                                              │  - 즉시 매매  │
                                              │  - 상태 조회  │
                                              └──────┬──────┘
                                                     │
                                              ┌──────▼──────┐
                                              │  기존 시스템  │
                                              │  - OrderSvc  │
                                              │  - Strategy  │
                                              │  - KillSwitch│
                                              └─────────────┘
```

## 사용 시나리오 (예시)

| 사용자 입력 | LLM 해석 | 실행 |
|------------|----------|------|
| "삼성전자 비중 줄여" | 005930 포지션 축소 | 일부 매도 주문 |
| "손절 -1%로 바꿔" | stop_loss 파라미터 변경 | 전략 설정 업데이트 |
| "오늘 매매 중지" | Kill Switch 수동 발동 | 봇 정지 |
| "현재 보유 뭐야?" | 포트폴리오 조회 | 잔고 조회 → 회신 |
| "거래량 기준 좀 낮춰" | volume_ratio 하향 | 파라미터 업데이트 |
| "내일부터 평균회귀만" | 모멘텀 전략 비활성화 | 전략 on/off |

## 구현 단계

### Step 1: 텔레그램 수신 인프라
- **파일**: `src/notification/telegram.py` (수정)
  - `TelegramCommandHandler` 클래스 추가
  - Webhook 또는 Long Polling으로 사용자 메시지 수신
  - 인증: chat_id 화이트리스트 (허용된 사용자만)
- **파일**: `src/notification/commands.py` (신규)
  - 명령 enum 정의 (QUERY, MODIFY_STRATEGY, EXECUTE_ORDER, CONTROL_BOT)

### Step 2: LLM 명령 해석기
- **파일**: `src/ai/telegram_interpreter.py` (신규)
  - 자연어 → 구조화된 명령 변환
  - Claude API 호출 (system prompt에 가능한 명령 + 현재 포트폴리오 상태 주입)
  - 모호한 명령 → 확인 질문 생성
- **안전장치**: 매매 명령은 반드시 확인 단계 거침
  ```
  사용자: "삼성전자 다 팔아"
  봇: "삼성전자(005930) 50주 전량 매도하시겠습니까? (Y/N)"
  사용자: "Y"
  봇: "매도 주문 실행됨. 체결 시 알림 드리겠습니다."
  ```

### Step 3: 명령 실행기
- **파일**: `src/notification/executor.py` (신규)
  - 파싱된 명령 → 기존 서비스 호출
  - OrderService, Strategy, KillSwitch 등과 연동
  - 실행 결과 → 텔레그램 회신

### Step 4: WebSocket 연동
- WebSocket 실시간 데이터 + 텔레그램 명령 통합
- 사용자가 "삼성전자 지금 얼마야?" → WebSocket 실시간가 즉시 회신

## 안전장치 (MANDATORY)

| 항목 | 규칙 |
|------|------|
| 인증 | chat_id 화이트리스트, 미등록 사용자 무시 |
| 매매 확인 | 즉시 매매 명령은 반드시 Y/N 확인 후 실행 |
| 금액 제한 | 텔레그램 경유 주문은 1회 최대 금액 제한 |
| 킬스위치 | 기존 Kill Switch 규칙 동일 적용 |
| 감사 로그 | 모든 텔레그램 명령 + LLM 해석 결과 DB 기록 |
| 모의투자 우선 | is_mock_trading=True 기본값 유지 |

## 의존성

| 전제 조건 | 상태 |
|----------|------|
| 단방향 알림 완료 | ✅ PR #101 |
| WebSocket 안정화 | ✅ PR #106~#110 완료 |
| ai/engine.py 테스트 85%+ | ✅ tests/ai/ 10+ 테스트 파일 |
| LLM shadow mode 검증 | ❌ 미시작 |

## 미결정 사항

→ decisions-pending.md #15 참조
- Webhook vs Long Polling
- LLM 모델 선택
- 명령 범위 (조회/파라미터만 vs 매매 포함)
- 확인 단계 UX
