# AI Hedge Fund Integration Handoff

작성일: 2026-05-19

이 문서는 `ai-hedge-fund-lab` 한국장 proposal layer를 `kiwoom-autotrade`의 기존 `/decisions` 승인 플로우에 붙이기 위한 인계 문서다.

## 결론

AI hedge 쪽은 직접 주문하지 않는다. `buy/sell/hold` proposal을 만들고, 그것을 `llm_decisions` pending draft로 넘긴다. 실제 주문은 기존 `kiwoom-autotrade`의 사용자 승인, live_trader, risk gate, broker path를 그대로 탄다.

```text
ai-hedge-fund-lab/kr/ai-hedge-fund
→ proposal JSON
→ decision draft JSON
→ POST /api/v1/decisions/drafts
→ llm_decisions pending
→ /decisions 사용자 승인
→ 기존 live_trader/risk/broker path
```

## 관련 경로

| 경로 | 역할 |
| --- | --- |
| `/Users/sanghyuklee/individual/stock/ai-hedge-fund-lab` | US 원본 + 한국장 AI hedge lab |
| `/Users/sanghyuklee/individual/stock/ai-hedge-fund-lab/kr/ai-hedge-fund` | 한국장 proposal 생성 패키지 |
| `/Users/sanghyuklee/individual/stock/kiwoom-autotrade-codex-ai-hedge-ingestion` | Codex가 만든 별도 worktree |
| `/Users/sanghyuklee/individual/stock/kiwoom-autotrade` | 기존 trading app 원본 작업트리 |

## AI Hedge Lab 현재 상태

구현 완료:

- static sample input → proposal JSON
- local `kiwoom-autotrade` read-only API → input payload
- input payload → safe proposal JSON
- proposal JSON → Kiwoom `LLMDecision` draft JSON
- deterministic technical signal
- deterministic risk gate
- stale daily candle 차단
- position limit 초과 시 추가 매수 차단
- `short/cover` 거부
- 직접 broker order 호출 없음

주요 산출물:

| 파일 | 내용 |
| --- | --- |
| `ai-hedge-fund-lab/samples/kr/input.example.json` | 정적 샘플 입력 |
| `ai-hedge-fund-lab/samples/kr/proposal.generated.json` | 정적 샘플 proposal 출력 |
| `ai-hedge-fund-lab/samples/kr/input.kiwoom.generated.json` | local Kiwoom read-only API 기반 입력 |
| `ai-hedge-fund-lab/samples/kr/proposal.kiwoom.generated.json` | local Kiwoom 기반 proposal 출력 |
| `ai-hedge-fund-lab/samples/kr/decision_drafts.kiwoom.generated.json` | `llm_decisions` pending draft용 JSON |

검증:

```bash
cd /Users/sanghyuklee/individual/stock/ai-hedge-fund-lab/kr/ai-hedge-fund
PYTHONPATH=src python -m unittest discover -s tests -v
PYTHONPATH=src python -m compileall -q src
```

마지막 확인 결과:

- 15 tests OK
- compile OK
- generated JSON parse OK
- direct order endpoint 검색 결과 없음

## Kiwoom Autotrade 연동 브랜치

별도 worktree:

```text
/Users/sanghyuklee/individual/stock/kiwoom-autotrade-codex-ai-hedge-ingestion
```

브랜치:

```text
codex/ai-hedge-decisions-ingestion
```

커밋:

```text
9c1f78c feat(decisions): ingest AI hedge decision drafts
```

추가된 API:

```http
POST /api/v1/decisions/drafts
```

기능:

- AI hedge draft JSON 리스트를 받는다.
- `llm_decisions` row를 생성한다.
- 생성 status는 항상 `pending`.
- 주문 생성 없음.
- 승인 처리 없음.
- broker 호출 없음.

허용 `decision_type`:

- `symbol_bias`
- `universe_adjust`
- `strategy_param_hint`

검증/차단:

- `status="approved"` 또는 `status="applied"` 주입 차단
- `symbol_bias.content.symbol`은 한국 6자리 종목코드만 허용
- `symbol_bias.content.bias`는 제한된 값만 허용
- 빈 draft list 거부
- 인증 없는 요청 거부

## Kiwoom 연동 브랜치 검증 결과

실행한 명령:

```bash
cd /Users/sanghyuklee/individual/stock/kiwoom-autotrade-codex-ai-hedge-ingestion

DATABASE_URL=postgresql+asyncpg://test:test@localhost/test \
  uv run pytest tests/api/test_decisions.py -q

DATABASE_URL=postgresql+asyncpg://test:test@localhost/test \
  uv run pytest tests/trading/test_llm_decision_loader.py -q

uv run ruff check src/api/v1/decisions.py tests/api/test_decisions.py
```

결과:

- `tests/api/test_decisions.py`: 17 passed
- `tests/trading/test_llm_decision_loader.py`: 49 passed
- Ruff: pass
- `git diff --check`: pass

## 원격 push 상태

로컬 커밋은 완료됐지만 remote push는 실패했다.

시도한 명령:

```bash
git push -u origin codex/ai-hedge-decisions-ingestion
```

실패 이유:

```text
Permission to lsh0107/kiwoom-autotrade.git denied to PeterCplat.
HTTP 403
```

즉 코드 문제가 아니라 현재 GitHub 인증 계정 권한 문제다.

## 다음 액션

1. GitHub push 권한 해결
2. 아래 worktree에서 push

```bash
cd /Users/sanghyuklee/individual/stock/kiwoom-autotrade-codex-ai-hedge-ingestion
git push -u origin codex/ai-hedge-decisions-ingestion
```

3. PR 생성
4. Actions 확인
5. merge 후 local backend rebuild/restart
6. end-to-end QA

## End-to-End QA 항목

1. AI lab에서 Kiwoom input 생성

```bash
cd /Users/sanghyuklee/individual/stock/ai-hedge-fund-lab/kr/ai-hedge-fund
PYTHONPATH=src python -m korea_ai_hedge.kiwoom_input \
  --base-url http://localhost:8000 \
  --email "$KIWOOM_AUTOTRADE_EMAIL" \
  --password "$KIWOOM_AUTOTRADE_PASSWORD" \
  --symbols 005930,000660 \
  --days 30 \
  --strategy-budget-krw 5000000 \
  --output ../../samples/kr/input.kiwoom.generated.json
```

2. proposal 생성

```bash
PYTHONPATH=src python -m korea_ai_hedge.cli \
  --input ../../samples/kr/input.kiwoom.generated.json \
  --output ../../samples/kr/proposal.kiwoom.generated.json
```

3. decision draft 생성

```bash
PYTHONPATH=src python -m korea_ai_hedge.exports.kiwoom_decision_export \
  --input ../../samples/kr/proposal.kiwoom.generated.json \
  --output ../../samples/kr/decision_drafts.kiwoom.generated.json
```

4. `/api/v1/decisions/drafts`로 POST
5. DB에 `pending` row 생성 확인
6. `/decisions` UI에 표시 확인
7. approve 시 `status=approved`, `applied_at=null` 확인
8. ingestion 과정에서 `orders` row가 생성되지 않는지 확인
9. live_trader가 기존 `symbol_bias.block_buy`를 후보 제외로만 반영하는지 확인

## 주의점

- 이 연동은 AI가 주문하는 기능이 아니다.
- `decision_drafts` ingestion은 pending review queue를 만드는 기능이다.
- `boost_buy`, `review_sell`은 현재 loader에서 실질 주문 신호로 소비되지 않는다.
- 현재 loader가 실제로 적용하는 핵심은 `symbol_bias.block_buy` 후보 제외다.
- 매수/매도 자동 실행까지 확장하려면 별도 설계와 risk gate가 필요하다.

