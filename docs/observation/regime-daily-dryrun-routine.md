# Regime daily dry-run 루틴 (6/15 본 관찰 전)

> **목적**: 6/15 본 관찰 전까지 **매일** 실제 데이터로 R3(regime report) + R4(mixed
> allocation dry-run) 을 실행해 regime / 전략 판단을 갱신한다. **거래는 0**, 전략
> 판단만 매일 업데이트. 6/15 preflight 에서 regime 추이를 근거로 live_trader 가동
> 여부를 재판단한다.
>
> **read-only 불변식**: orders / trade_logs / llm_decisions / strategy_runtime 변경 0,
> idle in transaction 0, broker order call 0, decision POST 0.

## 2계층 출력 (금융정보 보호)

| 계층 | 경로 | 내용 | git |
|---|---|---|---|
| **private** | `outputs/regime/<DATE>/` | R3/R4 산출물 (실계좌 현금·보유평가·종목별 평가액·allowed_cash 포함) | **커밋 금지** (`.gitignore` 의 `/outputs/regime/`) |
| **public-safe** | `docs/observation/<DATE>-regime-dryrun-summary.md` | regime label/confidence/flags, action 카운트, boost_sell 자동소비=0, DB delta=0, sleeve enabled/budget_pct(비율) | 커밋 가능 |

> public summary 는 `scripts/regime_summary_public.py` 가 allowlist 방식으로 안전
> 필드만 추출하고 `assert_no_financials` 로 누출을 차단한다. **실계좌 현금/보유평가/
> 종목별 수량·평가액/allowed_cash·notional 은 절대 문서에 쓰지 않는다.**

## 절차

### 1. 입력 생성 (lab + kiwoom read-only)

- **R3 입력** (`regime_overlay_input.actual.json`) — ai-hedge-fund-lab 산출:
  - Naver/KRX 지수 데이터(read-only)로 `score_korea_market_regime` → regime timeline
  - proposal 생성 + `apply_regime_overlay` → overlay items
  - 산출: `ai-hedge-fund-lab/outputs/proposals/<DATE>/proposal.generated.json`,
    `kr/ai-hedge-fund/experiments/bias_report_<DATE>.{json,md}` 등
- **R4 입력** (`allocation_input.actual.json`) — kiwoom read-only:
  - 로컬 backend balance read-only (broker get_balance, **주문 아님**)
  - `strategy_runtime` read-only (psql select)
  - regime label(위 R3) + 위 값으로 R4 입력 조립
- 두 입력 JSON 은 `outputs/regime/<DATE>/` (private) 에 둔다.

### 2. 실행

```bash
bash scripts/run_daily_regime_dryrun.sh <DATE> \
  outputs/regime/<DATE>/regime_overlay_input.actual.json \
  outputs/regime/<DATE>/allocation_input.actual.json
```

스크립트가 수행:
1. DB before snapshot (orders/trade_logs/llm_decisions/strategy_runtime, read-only)
2. R3 → `outputs/regime/<DATE>/regime_report.{json,md}` (private)
3. R4 → `outputs/regime/<DATE>/allocation_dry_run.{json,md}` (private)
4. DB after snapshot + **delta 검증** (전부 0 아니면 exit 1)
5. `db_verify.json` (private)
6. public-safe 요약 → `docs/observation/<DATE>-regime-dryrun-summary.md`

### 3. 커밋

- **public summary 만** `git add docs/observation/<DATE>-regime-dryrun-summary.md`.
- `outputs/regime/<DATE>/` 는 gitignore 라 자동 제외. **절대 `git add -f` 하지 말 것.**

## 6/15 preflight 연계

- 매일 summary 가 쌓이면 regime 추이(예: risk_off 지속 여부)를 본다.
- 6/15 본 관찰 preflight 에서 regime 이 계속 risk_off 면 live_trader 가동을 보류/재판단.
- regime 이 structural_bull 로 안정되면 §관찰 plan 의 가동 조건과 함께 판단.

## 금지

- live_trader 실행 금지 (본 루틴은 dry-run 도구만).
- short_swing / multi_regime enabled 변경 금지. strategy_runtime 변경 금지.
- risk_off 대응 로직 변경 금지 (본 루틴은 판단 갱신, 매매 로직 변경 아님).
- PR 2b/3 (total-equity budget / ownership / sell authority) 시작 금지 — 6/15 이후.
- `outputs/regime/` 실계좌 수치 커밋 금지.
