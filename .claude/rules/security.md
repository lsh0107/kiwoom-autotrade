# Security Rules

> 금융 거래 시스템. 보안은 최우선.

## 절대 규칙

- API 키 / 비밀번호 / 토큰 / 시크릿 **소스코드 포함 금지** — `.env` (gitignored) 또는 DB 암호화 저장
- **자격 증명 / 토큰을 argv 로 자식 프로세스에 전달 금지** — env / keychain 사용 (참고: `ai-hedge-fund-lab` PR E1.7 보안 보강)
- 로그 / 에러 메시지에 **민감 정보 출력 금지** — `_mask()` 등 마스킹 헬퍼 사용
- HTTPS 필수 (외부 API) + **timeout 필수**
- 커밋 전 `pre-commit run --all-files` (bandit / TruffleHog / Secret Detection 포함) 통과
- 기본 모의투자 (`is_mock_trading=True`). 실거래 전환은 사용자 명시 + 2중 확인

## 민감정보 저장소

| 환경 | 저장 위치 |
|---|---|
| 로컬 | `.env` (gitignored) |
| 서버 (배포 시) | OS secret manager / docker secret / mounted file |
| CI / GitHub Actions | GitHub Secrets + OIDC |
| DB | `BrokerCredential` 등 암호화 컬럼 (`encrypted_app_key`, `encrypted_app_secret`) + `decrypt()` 사용 |

## 외부 API 호출 (broker, 데이터, 알림)

- httpx `AsyncClient` 사용 시 `timeout=httpx.Timeout(read, connect)` 명시.
- 토큰 재발급 / rate limit / 에러코드 분기는 `src/broker/kiwoom.py::_request` 참조.
- **endpoint 레벨 fail-fast** — 외부 hang 가능성 있는 경로 (`/account/balance` PR #482 모델) 는 `asyncio.wait_for(...)` 로 wrap 후 504 / 502 매핑.
- **fake fallback 금지** — balance / order 실패를 가짜 정상 값으로 대체하지 않음. 실패는 명시적 5xx 또는 raise.

## 주문 / 거래 안전

- 1회 최대 주문 금액 / 일일 최대 주문 횟수 / 사용자별 한도 적용
- 장 운영시간 외 주문 방지
- 가격제한폭 (±30%) 검증
- kill switch 진행 시 모든 주문 정지

## AI hedge ingestion

- `ai_hedge` context 결정은 **auto-approval 대상에서 제외** (#464). 사용자 manual approve 만 거침.
- decisions POST → 사용자 승인 → 기존 live_trader / risk gate / broker 호출 순서. **AI hedge 가 broker order API 를 직접 호출하지 않음**.
- AI hedge live consumption (PR E2) 는 본 repo 에서 별도 PR. **feature flag 기본 OFF 머지** 정책 (`docs/ai-hedge/PR_E_DESIGN.md` §5.1).

## 로깅

- 주문 관련 반드시 로깅 (symbol, quantity, price, is_mock)
- 민감 정보 마스킹 (`_mask()` in kiwoom.py 패턴 따르기)
- 토큰 / 비밀번호 / 자격 증명 값 자체를 로그 / 응답 / 에러 메시지에 포함하지 않음
- 구조화 로깅 (structlog) 사용. `credential_id` / `is_mock` / `elapsed_sec` 같은 안전한 메타데이터는 OK

## gitignore 필수 항목

```
.env
.env.*
*.local.json
.claude/settings.local.json
.claude/memory/         # 세션 메모리 (PII 포함 가능)
*.tfstate
credentials*
secrets*
```

## 보안 도구

```bash
uv run bandit -r src/ -ll                # Python static analysis
uv run pre-commit run --all-files        # 통합 검사 (Secret / TruffleHog / Bandit / Ruff)
```

## 위반 발견 시

- 시크릿이 커밋에 들어간 경우: 즉시 revoke + 새 키 발급 + history rewriting (사용자 승인 필요, force push 절차)
- argv 노출 발견: env fallback 으로 수정 + 회귀 테스트 추가
- timeout 누락 외부 호출: timeout 추가 + 실패 매핑 정의 + 회귀 테스트

## 참조

- `.claude/rules/trading.md` — 트레이딩 안전 (주문 한도, 모의/실거래)
- `.claude/rules/escalation.md` — 보안 변경 시 사용자 확인 정책
- `.claude/rules/testing.md` — 외부 API mock 정책
