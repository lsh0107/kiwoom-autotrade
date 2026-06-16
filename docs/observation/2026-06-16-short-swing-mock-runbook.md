# Short Swing Mock Run Runbook (PR B 신설)

> **상태**: PR B 머지 후 활성. 본 관찰 (cross_momentum) 과 별도. 모의 한정.
> **목적**: short_swing daily 주문 lifecycle (candidate → order → submitted/filled → trade_logs → graceful 종료) 을 모의에서 직접 확인. cross_momentum weekly 주기 관찰만으로는 진입/체결 코드 경로가 검증되지 않아 마련.

## 0. 안전 불변식

- `settings.is_mock_trading=True` 강제 (strategy 레이어에서 `RuntimeError`로 hard fail).
- `KIWOOM_IS_MOCK=false` 환경변수 금지.
- `cross_momentum` 보유 종목 매도 **금지** (자체 `ShortSwingPosition` row 없으면 매도 후보 미발동 — `short_swing_exit.py:175`).
- `ai_hedge` boost_sell / review_sell 자동 매도 **연결 없음** (validator 수용만, 자동 소비 미개방).
- `outputs/regime/<DATE>/` 산출물 (실계좌 금액 포함) **커밋 금지** (.gitignore).

## 1. 사전 조건 (manual)

- 6/16 또는 직전 영업일 기준 `daily_candles` fresh → `uv run python scripts/preflight_data_freshness.py` PASS.
- 동일 일자 `outputs/regime/<DATE>/regime_report.json` 존재 → daily regime dry-run 후 자동 생성됨.
- backend / postgres 컨테이너 healthy.
- `data/.kill_switch` / `data/.trader.pid` 없음.

## 2. preflight + dry-run (read-only)

```bash
# 단독 dry-run (DB write 0, broker order 0). 라이브 가동 전 안전 확인용.
bash scripts/run_short_swing_mock.sh   # 기본 30 분 가동
# 또는
DRY_RUN=1 bash scripts/run_short_swing_mock.sh   # preflight + dry-run 만, 실가동 skip
```

스크립트 단계:

1. `data/.kill_switch` / `data/.trader.pid` 부재 확인
2. `scripts/preflight_data_freshness.py` (PR A) PASS
3. `strategy_runtime` baseline 캡쳐 (cross_momentum 보존 확인)
4. `orders` / `trade_logs` / `llm_decisions` baseline + idle in transaction
5. `scripts/short_swing_dryrun.py` (read-only)
6. (DRY_RUN=0 일 때) `short_swing.enabled=true` 적용 + trap 으로 종료 시 false 복구
7. `timeout ${DURATION_SEC}s uv run python scripts/live_trader.py --auto` (기본 1800 초)
8. 사후 검증: orders/trade_logs delta + cross_momentum 보유 매도 0 확인

## 3. regime overlay 정책 (PR B 초기, mock-only)

| regime           | allow_new_entry | max_new_entries_override |
|------------------|-----------------|---------------------------|
| risk_off         | False           | 0 (차단)                  |
| bull_overheat    | True            | 1 (과열 제한)             |
| volatile_bull    | True            | None (기본)               |
| structural_bull  | True            | None (기본)               |
| neutral / 미상   | True            | None (기본)               |

- 정책은 `src/trading/short_swing_regime.py:regime_overlay_decision`.
- 데이터 누적 전이라 보수적. live_trader 가동 데이터 누적 후 재조정.

## 4. 종료 / rollback

- 정상: `timeout --signal=INT` 가 SIGINT 송신 → live_trader graceful shutdown.
- 비정상: 사용자가 직접 Ctrl-C 또는 `kill -INT $(cat data/.trader.pid)`.
- trap 으로 `short_swing.enabled=false` 자동 복구.
- 잔여 PID/lock 정리는 스크립트 종료 시 자동 (PID 가 죽었으면 파일 제거).

## 5. 사후 결과 정리 (PR C 영역)

장중 mock run 종료 후 다음 문서를 새로 작성한다:

- `docs/observation/<DATE>-short-swing-mock-result.md` (public-safe)
  - 실행 시각 / 사이클 수 / orders Δ / trade_logs Δ / llm_decisions Δ
  - skip reason 분포 (개수, 비율)
  - regime overlay 적용 흔적 (regime / allow / override / actual skip)
  - cross_momentum 보유 매도 0 확인 (`short_swing_positions` 생성된 row 만)
  - 발견된 문제 (있으면)

> public summary 에는 실계좌 금액 / 보유 평가액 / allowed_cash 등 금융 정보 **미포함**. 비공개 산출물은 `outputs/short_swing/<DATE>/` (gitignored) 에 둔다 (필요 시 추가).

## 6. 금지

- `is_mock_trading=False` 또는 `KIWOOM_IS_MOCK=false` 가동.
- `short_swing` ownership / sell authority 변경 (PR 3 영역, 보류).
- `boost_sell` / `review_sell` 자동 소비 연결.
- `outputs/regime/`, `outputs/short_swing/` 산출물 커밋.
- 본 관찰 (cross_momentum) plan §8/§9 절차와 혼동.

## 7. 참조

- 본 관찰: `docs/observation/2026-06-01-mock-live-trader-observation-plan.md` (v0.12, cross_momentum 영역)
- daily regime dry-run: `docs/observation/regime-daily-dryrun-routine.md`
- PR A (stale guard): #555 / #556
