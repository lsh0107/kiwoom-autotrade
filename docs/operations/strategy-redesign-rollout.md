---
name: strategy-redesign-rollout
description: 전략 롤아웃 체크리스트 — 누적 폐기 5건(ADR-020) 후 cross-sectional momentum V2 PASS (ADR-021). ADR-022 어댑터 + ADR-023 견고화 완료. ACTIVE_STRATEGY=cross_momentum 설정 후 모의 4주 관찰 시작 가능. (ADR-024: USE_CROSS_MOMENTUM/USE_MULTI_REGIME 환경변수 폐기 → ACTIVE_STRATEGY enum 단일화)
type: operations
status: "ADR-023 견고화 완료 — 모의 4주 관찰 시작 가능"
created: 2026-04-27
updated: 2026-04-28
depends_on:
  - design-015-backtest-engine-integrity
  - design-016-strategy-redesign
  - design-017-risk-microstructure
  - design-018-strategy-rerun
  - design-019-pullback-range-validation
  - design-020-extended-validation
  - design-021-cross-sectional-momentum
  - design-022-cross-momentum-live-adapter
  - design-023-cross-momentum-hardening
---

# 전략 재설계 롤아웃 체크리스트

> **현재 상태 (2026-04-28 갱신 — ADR-023)**:
> - 52주 신고가 일봉 전략 **폐기 확정** (파라미터 20개 조합 전부 0/20 — ADR-018)
> - Pullback/Range/MR 일봉 어댑터 **폐기 확정** (12 combo × 20종목 0/20 — ADR-019)
> - **확장 검증 완료 → 일봉(daily) timeframe Pullback/Range/MR 폐기** (27 combo × 59종목 0/59 — ADR-020). **주봉/이주봉/월봉 timeframe은 별개 검증 대상으로 보존 (옵션 (e))**
> - **ADR-021: Cross-sectional momentum V2 기준 PASS** — top20pct_novol_notrend (2/6 = 33%). 모의 진입 후보 확정.
> - **ADR-022: Cross-momentum live rebalance 어댑터 구현 완료** — 21 신규 + 611 회귀 PASS, 커버리지 85.05%.
> - **ADR-023: 견고화 완료** — rate limit 백오프 + T+2 결제 시뮬레이션 + KRX 공휴일 캘린더. 미해결 위험 4건 전부 해소. 1871 PASS.
> - design-013 multi-regime 배선 완성 (skeleton → 완전, PR #334)
> - **모의투자 가능** — `ACTIVE_STRATEGY=cross_momentum` 설정 후 live_trader 재기동
> - `USE_CROSS_MOMENTUM` / `USE_MULTI_REGIME` 환경변수 **폐기** — ADR-024로 `ACTIVE_STRATEGY` enum으로 단일화됨

## 0. 현재 상태 요약

| 항목 | 상태 | 근거 |
|------|------|------|
| 모의투자 | ✅ **시작 가능** | ADR-023 견고화 완료 (`ACTIVE_STRATEGY=cross_momentum`) |
| 실전 전환 | ⛔ 차단 | 모의 4주 관찰 + 기준 통과 + 사용자 명시적 승인 필요 |
| `USE_MULTI_REGIME` / `USE_CROSS_MOMENTUM` 사용 | ⛔ **폐기** | ADR-024로 `ACTIVE_STRATEGY` enum 단일화. 구 환경변수 사용 금지 |
| 52주 신고가 파라미터 재조정 | ✅ 완료(폐기) | 20 grid × 20종목 전 조합 0% — ADR-018 §2 |
| Pullback/Range/MR walk-forward | ✅ 완료(폐기) | 12 combo × 20종목 전 조합 0% — ADR-019 §3~5 |
| 확장 검증 (60종목, 3년, 27 combo) | ✅ 완료(폐기) | 27 combo × 59종목 전 조합 0%, **일봉 timeframe** 제외 (주봉~월봉은 보존) — ADR-020 |
| **Cross-sectional momentum WF** | ✅ **PASS (ADR-021)** | top20pct_novol_notrend 2/6 (33%) — V2 기준 |
| **Cross-momentum live 어댑터** | ✅ **구현 완료 (ADR-022)** | 21 신규 + 611 회귀 PASS, 커버리지 85.05% |
| **ADR-023 견고화** | ✅ **완료** | rate limit + T+2 + 공휴일 해소, 1871 PASS |

---

## 1단계: 후속 전략 선택 + walk-forward 검증

ADR-021 §9 결정: **Cross-sectional momentum (top20pct_novol_notrend) V2 기준 PASS. 모의 진입 후보 확정.**

> ✅ **옵션 (a) Cross-sectional momentum (ADR-021 PASS)**: top20pct_novol_notrend 2/6 (33%) V2 PASS.  
> 단, ADR-022(live_trader 어댑터) 설계 완료 + 모의 4주 관찰 후 실전 전환.

> 보존 후보 (ADR-021 이후):
> - **(e) 주봉/이주봉/월봉 timeframe Pullback/Range/MR 재검증** — pykrx 일봉 resample, 노이즈/거래비용 비율이 일봉과 본질적으로 다름

### ~~옵션 A: KOSPI 소형/중형주 유니버스로 Pullback/Range/MR 재검증~~ (ADR-020 폐기 확정)

**ADR-020 결과**: KOSPI30+KOSDAQ30 59종목, 3년, 27 combo 확장 검증 → 0/59 폐기 확정.
신호 희소성 가설 기각 (OOS 31% 윈도우 거래 발생). 카테고리 자체 수익 불가 구조 확인.
→ **일봉(daily) timeframe Pullback/Range/MR 재검증 불필요 — 일봉 한정 폐기. 주봉~월봉은 옵션 (e)로 보존.**

상세 결과: [ADR-020](docs/design/design-020-extended-validation.md) §3~6 참조

### Cross-sectional Momentum (ADR-021 PASS)

**ADR-021 결과**: KOSPI100+KOSDAQ100 172종목, 5년, 8 combo WF 실행.  
V2 기준(IR 0.3, IS Sharpe ≤ 0 윈도우 OOS/IS ratio 면제) 재집계 → **top20pct_novol_notrend 2/6 (33%) PASS**.

- best combo OOS Sharpe 평균(6W): 1.61 / best combo OOS Return 평균(6W): +22.5%
- V2 PASS 윈도우: W1(OOS Sharpe 1.22, IR 1.37, +15.8%), W2(OOS Sharpe 3.24, IR 1.75, +40.3%)
- W5·W6 IR 음수: 벤치마크 KOSPI 강세로 절대수익 양수지만 인덱스 underperform — 구조적 한계 인지

→ **모의 진입 후보 확정. ADR-022 어댑터 설계 후 진행.**

상세 결과: [ADR-021](docs/design/design-021-cross-sectional-momentum.md) §6~9 참조

---

## 2단계: 모의투자 재개 — ADR-022 활성화

ADR-022 어댑터 구현 완료. 아래 절차로 즉시 시작 가능.

### 전제 조건 체크리스트

- [x] **Cross-sectional momentum best combo (top20pct_novol_notrend)** — ADR-021 V2 PASS ✅
- [x] **ADR-022 어댑터 구현 완료** — 21 신규 + 611 회귀 PASS, 커버리지 85.05% ✅
- [x] **ADR-023 견고화 완료** — rate limit 백오프 + T+2 결제 시뮬 + KRX 공휴일, 미해결 위험 4건 전부 해소 ✅
- [ ] **모의 4주 관찰** — 아래 기준 모두 달성해야 실전 전환 검토 가능
- [x] `ACTIVE_STRATEGY=cross_momentum` — ADR-024로 `USE_MULTI_REGIME`/`USE_CROSS_MOMENTUM` 폐기, `validate_cross_momentum_exclusivity` 함수 삭제됨
- [ ] T3 리스크 가드레일 모의투자 계좌에서 작동 확인
  - [ ] DrawdownGuard: HWM -5% STOP_BUY 트리거 확인
  - [ ] KillSwitch: SOFT_STOP / HARD_STOP 상태 전이 확인
- [ ] T4 마이크로구조 작동 확인
  - [ ] 시장가 주문 정상 체결 확인 (log 분석)
  - [ ] 09:00~15:30 외 리밸런싱 SKIP 확인

### 모의투자 시작 절차 (ADR-022 + ADR-023)

```bash
# 1. .env에 전략 설정 추가 (ADR-024: USE_CROSS_MOMENTUM 폐기 → ACTIVE_STRATEGY 사용)
echo "ACTIVE_STRATEGY=cross_momentum" >> .env
# USE_CROSS_MOMENTUM, USE_MULTI_REGIME은 ADR-024로 폐기됨 — 사용 금지
# T2_SETTLEMENT=false 확인 (모의는 기본값 False — 백테스트와 동일)

# 2. kill_switch 상태 초기화
# 3. live_trader 재기동 (is_mock_trading=True 확인 필수)
bash scripts/start_trading.sh

# 4. 로그 모니터링 — 월 마지막 거래일 14:55 리밸런싱 확인
tail -f logs/live_trader.log | grep -E "(rebalance|cross_momentum|SELL|BUY|14:55)"
```

> **운영 체크리스트 — 매년 12월 수행**
> - `data/krx_holidays.json`에 다음 해 KRX 공휴일 추가 (KRX 공식 공시, 매년 11~12월 발표)
> - 대체공휴일 포함 여부 확인 후 JSON 편집 + PR + dev→main 배포

### 모의 4주 관찰 기준 (실전 전환 필요조건)

| 지표 | 기준값 | 근거 |
|------|--------|------|
| 4주 누적 수익률 | **양수** | 절대 손실 없음 |
| OOS Sharpe (4주 기준) | **≥ 1.0** | ADR-021 V2 기준 |
| MDD | **≥ -25%** | ADR-021 V2 기준 |
| IR (4주 기준) | **≥ 0.3** | 한국 long-only 실증 기준 |
| 이상 거래 | **0건** | kill_switch 미발동 |
| API 연결 | **오류 0회** | 키움 REST 안정성 |

### 관찰 기간

**권장 4주** (월 1회 리밸런싱 → 최소 1회 실제 실행 포함)

| 주차 | 확인 사항 |
|------|----------|
| 1주 | live_trader 정상 기동 + 스케줄러 등록 로그 확인 |
| **5/29 14:55** | **첫 monthly trigger** — 2026-04-29 모의 시작 기준, 5월 마지막 거래일 14:55 첫 리밸런싱 실행 확인 (14:30 ranking → 14:55 주문) |
| 2~4주 | 누적 PnL 추세 + 가드레일 발동 빈도 |
| 4주 | 위 기준 전부 충족 여부 최종 판단 |

---

## 3단계: 소액 실전 전환 전 최종 확인

모의투자 2~4주 완료 후.

### 필수 확인 사항

- [ ] 모의투자 누적 PnL ≥ 0% (손실 구간 진입 시 차단)
- [ ] 실전 vs 백테스트 성과 비율 ≥ 50%
  - 실전 Sharpe / 백테스트 OOS Sharpe ≥ 0.5
- [ ] MDD 관찰값 ≤ -10% (모의투자 기간 중)
- [ ] 가드레일 비정상 발동 없음 (HARD_STOP 0회)
- [ ] API 연결 안정성 확인 (접속 오류 0회)

### 파라미터 조정 사항 (실거래 강화)

| 파라미터 | 모의투자 | 실거래 |
|----------|----------|--------|
| DRAWDOWN_STOP_BUY_PCT | -5.0% | **-3.0%** |
| DRAWDOWN_FORCE_CLOSE_PCT | -7.0% | **-5.0%** |
| 연속 손절 SOFT_STOP | 3회 | **2회** |
| 일일 주문 SOFT_STOP | 40건 | **20건** |
| max_positions | 3 | **2** (초기) |

### 실전 전환 절차

```bash
# .env에서 MOCK_TRADING=False 설정 (명시적 변경 필요)
# 초기 투자금: 전체 가용 자금의 10~20% (소액 테스트)
# 1주 관찰 후 이상 없으면 점진적 증액
```

---

## 4단계: 중단 조건 (자동 + 수동)

### 자동 중단 (Kill Switch)

| 조건 | 동작 |
|------|------|
| 일일 HWM 드로우다운 -7% | FORCE_CLOSE (전량 청산) |
| 주간 손실 -6% | 투자금 80% 축소 |
| 동일 종목 3회 연속 손절 | SOFT_STOP |
| 10분 PnL -1.5% | SOFT_STOP |

### 수동 중단 — 실전 성과 vs 백테스트 50% 이하

다음 중 하나 발생 시 즉시 실전 중단 → 모의투자 복귀:

- [ ] **실전 누적 수익률 < OOS 기대수익률의 50%** (4주 기준)
- [ ] **실전 MDD > 백테스트 MDD × 1.5** (예: 백테스트 MDD -10% → 실전 -15% 초과)
- [ ] **승률 < 25%** (모의 검증값의 절반 이하)
- [ ] **API 연결 장애 3회 이상** (연속 또는 일간)

### 중단 절차

```bash
# 1. 즉시 전량 청산
# live_trader.py에서 manual kill_switch 활성화

# 2. 포지션 확인
curl -X GET http://localhost:8000/api/v1/orders?status=open

# 3. 원인 분석 후 모의투자 재개 여부 결정
```

---

## 참조 문서

- design-015: 백테스트 엔진 무결성 (slippage/MDD/look-ahead)
- design-016: 전략 재설계 + walk-forward 결과 (52주 신고가 **폐기 확정**)
- design-017: 리스크 가드레일 + 마이크로구조 설계
- design-018: 파라미터 재검증 결과 통합 (ADR-018) + 후속 전략 옵션 분석
- design-019: Pullback/Range/MR walk-forward 결과 + 누적 폐기 4건 패턴 분석 (**ADR-019**)
- design-020: 확장 검증 (KOSPI30+KOSDAQ30 59종목, 3년, 27 combo) + **일봉 timeframe** Pullback/Range/MR 폐기 (주봉~월봉은 보존, **ADR-020**)
- **design-021**: **Cross-sectional momentum V2 PASS** — top20pct_novol_notrend 33%, 모의 진입 후보 (**ADR-021**)
- **design-022**: **Cross-momentum live rebalance 어댑터** — CrossMomentumRebalanceAdapter, 월말 14:55 스케줄러, `ACTIVE_STRATEGY=cross_momentum` (구 `USE_CROSS_MOMENTUM` 환경변수는 ADR-024로 폐기), 안전장치 4종 (**ADR-022**)
- design-013: multi-regime 아키텍처 (배선 완성, cross-momentum 어댑터와 상호배타)
- design-014: live_order_persist — ADR-022 어댑터 주문 DB 기록 경로
- **design-023**: **ADR-023 견고화** — rate limit 백오프 + T+2 결제 시뮬 + KRX 공휴일 캘린더
- `.env.example`: 모의/실거래 전환 설정 키 목록 (`ACTIVE_STRATEGY` enum 포함 — `USE_CROSS_MOMENTUM`/`USE_MULTI_REGIME`은 ADR-024로 폐기)
