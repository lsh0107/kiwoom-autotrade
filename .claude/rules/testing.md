# Testing Rules

> 기능 추가/변경 시 테스트 코드 우선 원칙. 커버리지 85%+ 미만 시 PR 금지.

## 핵심 규칙 (MANDATORY)

1. **코드 변경 PR 에는 관련 테스트 반드시 포함**. 테스트 없는 코드 변경은 reviewer 가 REQUEST_CHANGES.
2. **버그 수정 시 재발 방지 테스트 필수** — 재현 테스트 작성 → 수정 → 테스트 통과 확인.
3. **외부 API 호출은 반드시 mock** (respx / unittest.mock). CI 에서 실제 키움 / 외부 서버 호출 금지.
4. **전체 회귀가 오래 걸리면** 타겟 테스트 먼저 → push → 머지 전에 CI 의 전체 회귀 확인.

## 테스트 범위 매트릭스

| 변경 유형 | 최소 테스트 요구 |
|---|---|
| 비즈니스 로직 (전략 / risk gate / 사이징 / reconcile) | unit test 필수 |
| API endpoint 추가/변경 | endpoint test (TestClient + auth_client 픽스처) 필수 |
| 주문 / 체결 / 취소 / 권한 상태 전이 | 상태 전이 테스트 필수 (시작 → 분기마다 → 종료) |
| broker (`src/broker/`) 변경 | mock 기반 unit test + 토큰 재발급 / rate limit / 에러코드 분기 |
| alembic 마이그레이션 | upgrade + downgrade 동작 + 데이터 보존 확인 |
| 의존성 변경 (`pyproject.toml`) | import + 기본 호환 smoke test |
| frontend 변경 | vitest 또는 browser QA (테스트 가능한 경우) |
| 문서 / 설정 전용 (`.md` / `.yml` 일부) | 테스트 불필요. diff 검토만 |
| 리팩터링 (동작 변경 없음) | 기존 테스트 통과 확인 |

## 명령

```bash
uv run pytest -q                          # 전체 회귀
uv run pytest tests/api/test_<scope>.py   # 타겟 테스트
uv run pre-commit run --all-files         # lint/format/secret/bandit
```

## CI

- GitHub Actions: Pytest (커버리지 85%+) / Ruff Lint & Format / Secret Detection / TruffleHog / Dependency Audit / CodeQL / Bandit / Python SAST.
- 모든 항목 pass 후에만 머지.
- 일부 SAST 가 skipping 으로 표시되는 경우 = 해당 path 변경 없음 (정상).

## trading / order / reconcile 변경 시 (특별 규칙)

- 자금 / 체결 정합성 영향 → 회귀 테스트 + 사용자 review OK 후 머지.
- mock 모드에서 dry-run + orders / trade_logs 영향 확인.
- broker holdings 가 source of truth 이므로 DB orders 적분 단독 사용 회귀 금지.
- fake balance / fake order success fallback 도입 금지.

## AI hedge ingestion 변경 시

- `/api/v1/decisions/drafts` 와 `apply_universe_decisions` / `mark_decisions_applied` 의 회귀 테스트 유지.
- `ai_hedge` context auto-approval 제외 (#464) 회귀.
- applied 마킹은 실 universe / 매수·매도 발생 기준 (#466) 회귀.
- `block_buy` 소비 동작 회귀 (PR E_DESIGN §5.2 — source/status gate 변경 시 block_buy 제외).

## 안티패턴

| 안티패턴 | 올바른 접근 |
|---|---|
| "나중에 테스트 추가" | PR 에 포함 |
| 테스트 없이 "로컬에서 확인했다" | 로컬 + 자동화 둘 다 |
| CI 에서 실제 외부 API 호출 | mock + fixture |
| 커버리지 85% 미만으로 머지 | 신규 코드 path 에 테스트 추가 후 머지 |
| 단일 e2e 1개로 모든 분기 커버 시도 | 분기별 unit + 핵심 path 1개 e2e |

## 참조

- `.claude/rules/python.md` — Python 스타일 / type hint
- `.claude/rules/trading.md` — 트레이딩 안전
- `.claude/rules/frontend.md` — Next.js / 컴포넌트 테스트
- `.claude/rules/airflow.md` — DAG 테스트
