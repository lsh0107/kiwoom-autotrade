# Backtest 디렉토리 & 산출물 관리 정책

> 백테스트 엔진 / 테스트 / 스크립트 와 그 산출물 (`docs/backtest-results/`) 의 관리 정책. 코드는 유지, 결과물은 "decision evidence" 와 "generated artifact" 로 분리.

## 1. 디렉토리 구조 (유지)

| Path | 역할 |
|---|---|
| `src/backtest/` | 백테스트 엔진 (daily / generic / mr / walk-forward / metrics / slippage) |
| `tests/backtest/` | 엔진 단위/회귀 테스트 |
| `scripts/run_backtest.py`, `scripts/run_daily_backtest.py` | 실행 진입점 |
| `docs/backtest-results/` | 실행 산출물 — 본 정책의 관리 대상 |
| `docs/design/design-015-backtest-engine-integrity.md` | 엔진 무결성 ADR (PR #326) |
| `docs/design/design-016~021` | 전략 설계 / 검증 ADR — 산출물을 evidence 로 인용 |

본 정책은 위 경로 중 **`docs/backtest-results/` 만** 다룬다. 엔진/테스트/스크립트 코드 변경은 본 정책 범위 외.

## 2. 산출물 분류

### 2.1 Decision Evidence (curated, git tracked)

ADR / 디자인 문서 / Phase 보고서가 인용하는 산출물. 전략 의사결정에 실제 쓰임 → 영구 보존 + repo 추적.

**판정 기준**:
- `docs/design/*.md` 또는 `docs/ai-hedge/*.md` 의 본문 / 표 / 차트에서 파일명/PR/지표를 인용
- ADR 의 `related:` frontmatter 에 명시
- PR 본문에서 "이 결과 기반 결정" 으로 참조

**보존 동작**:
- `git ls-files docs/backtest-results/` 에 포함
- 파일 자체는 immutable (수정 시 새 파일로)
- 30 MB 이상 대용량은 별도 archive 정책 검토 (§5)

### 2.2 Generated Artifact (gitignored, `outputs/backtest/` 이동 대상)

매일/매주 정기 실행으로 만들어지는 일자 단위 산출물. 의사결정 evidence 가 아니므로 repo 에 포함시키지 않음.

대표 패턴:
- `live_YYYYMMDD_HHMMSS.json` — 라이브 트레이더 일일 결과
- `screened_YYYYMMDD_HHMMSS.json` — 일일 스크리닝 결과
- 같은 시나리오 재실행본 (예: `backtest_20260424_064956.json` 와 `backtest_20260424_113050.json` 둘 중 하나만 evidence, 나머지는 artifact)
- 디버그/탐색 walk-forward run

**보존 동작**:
- `.gitignore` 처리 (§4)
- 생성 위치: 향후 `outputs/backtest/` 로 분리 권장 (현재는 `docs/backtest-results/` 에 섞여 있음)
- 사용자 로컬 보관. repo 부피 키우지 않음

### 2.3 삭제 후보 (사용자 확인 필수)

- 같은 의도의 산출물이 여러 개 (e.g. 같은 날 timestamps 다른 3개) 중 evidence 외 잔여물
- 엔진 변경 전 결과로 더 이상 비교 baseline 으로 쓰지 않는 것
- 30 MB+ 대용량 중 evidence 도 아니고 정기 재현 가능한 것

본 정책은 **삭제 명령을 내리지 않는다** — 사용자 확인 후 별도 PR.

## 3. 현재 분류 결과 (2026-05-28 기준)

### 3.1 ADR 인용 매핑

| 파일 | 인용 ADR | 상태 |
|---|---|---|
| `daily_backtest_20260427_113311.json` | design-016/018/019/020/021 | ✅ tracked |
| `strategy_comparison_20260427.json` | design-016/018 | ✅ tracked |
| `walk_forward_cross_momentum_full_20260427_192906.json` | design-021 | ⚠️ **untracked — 추적 누락** |
| `walk_forward_cross_momentum_recompute_20260427_201019.json` | design-018/021 | ✅ tracked |
| `walk_forward_extended_20260427_180305.json` (30 MB) | design-020 | ✅ tracked (대용량 archive 검토) |
| `walk_forward_pullback_range_20260427_151928.json` | design-019 | ✅ tracked |
| `walk_forward_rerun_20260427_045847.json` | design-018 | ✅ tracked |

### 3.2 tracked 인데 ADR 인용 없음

| 파일 | 추정 |
|---|---|
| `backtest_20260424_064956.json` | PR #326 (design-015) Skeptic 시점 산출물. ADR 본문에 직접 인용 X — 참조 노트 추가 또는 evidence 강등 검토 |
| `daily_backtest_20260427_103106.json`, `_103117.json` | `_113311.json` 의 이전 시도. evidence 1건만 남기고 나머지 강등 검토 |
| `walk_forward_cross_momentum_full_20260427_193805.json` | `_192906.json` 의 이후 재실행본. 둘 중 final 선택 필요 |

### 3.3 untracked (generated artifact)

```
backtest_20260424_113050.json         # 같은 날 재실행본
live_YYYYMMDD_HHMMSS.json (16건)      # 라이브 trader 일일 결과
screened_YYYYMMDD_HHMMSS.json (19건)  # 일일 스크리닝
walk_forward_cross_momentum_20260427_192034.json    # 탐색 run, evidence 외
walk_forward_cross_momentum_full_20260427_192906.json # ⚠️ design-021 인용 — 추적 필요 (예외)
```

## 4. `.gitignore` 제안 (사용자 확인 후 적용)

현재 `.gitignore` 는 `docs/backtest-results/*.log` 만 무시. 다음 패턴 추가 제안:

```gitignore
# 백테스트 일일 산출물 (generated artifact)
docs/backtest-results/live_*.json
docs/backtest-results/screened_*.json
# 향후 outputs/backtest/ 로 분리 시:
outputs/backtest/
```

**적용 전 사용자 확인**:
- 위 패턴 추가 시 현재 untracked `live_*.json` (16건) + `screened_*.json` (19건) 가 git status 에서 사라짐 (의도된 동작).
- 이미 tracked 인 파일은 영향 없음 (git 의 ignore 는 tracked 파일에 적용되지 않음).
- `walk_forward_cross_momentum_full_20260427_192906.json` 은 별도 add 가 필요한 evidence — ignore 보다 add 우선.

## 5. Retention / Archive 정책 (권고)

| 산출물 | 보존 기간 | 위치 |
|---|---|---|
| ADR 인용 evidence < 5 MB | 영구 | `docs/backtest-results/` tracked |
| ADR 인용 evidence ≥ 30 MB | 영구 | tracked 또는 별도 archive (e.g. git LFS / 외부 스토리지 + 본 README 에 포인터) — 사용자 결정 |
| live/screened 일일 산출물 | 90 일 로컬 보관 | `outputs/backtest/` (gitignored) |
| 탐색/디버그 walk-forward run | 7~14 일 로컬 | gitignored 또는 즉시 삭제 |
| `*.log` | 30 일 로컬 (이미 gitignored) | 변동 없음 |

대용량 evidence 의 별도 archive 도입은 본 PR 범위 외. `walk_forward_extended_20260427_180305.json` (30 MB) 가 첫 후보.

## 6. Naming Convention

기존 패턴 유지 (대소문자 + underscore + YYYYMMDD + 옵션 HHMMSS):

```
<strategy_or_kind>_YYYYMMDD[_HHMMSS].json
```

예시:
- `walk_forward_<strategy>_<scenario>_YYYYMMDD_HHMMSS.json`
- `live_YYYYMMDD_HHMMSS.json`
- `screened_YYYYMMDD_HHMMSS.json`
- `strategy_comparison_YYYYMMDD.json`

ADR 본문에서 인용할 때는 **PR 번호와 timestamp 를 함께 명시** (`design-XXX §N — walk_forward_*_PRYYY.json`).

## 7. Claude / 다른 작업자 판단 가이드

`docs/backtest-results/` 안의 파일을 보고 의사결정 근거로 인용할 때:

1. **그 파일이 ADR / 디자인 문서에 인용되었는지 먼저 확인**. tracked 라고 자동 evidence 가 아니다.
2. **timestamp 가 현재 엔진 / 정책과 호환되는지 확인** (예: PR #326 이전 엔진 산출물은 `design-015` 4종 무결성 수정 전이라 비교 baseline 으로 쓰면 안 됨).
3. **재현 가능성 확인**. ADR 의 `pr:` 와 엔진 버전 / 데이터 cutoff 가 일치해야 evidence 로 인용 가능.
4. **generated artifact (live/screened) 를 evidence 로 쓰지 않음**. 일일 trader / scanner 출력은 일자 단위 관찰용.

## 8. 미진행 작업 (사용자 확인 후 별도 PR)

본 정책 문서는 **분류 + 정책 정의만** 한다. 다음은 별도 사용자 확인 + 별도 PR:

- [ ] `.gitignore` 패턴 추가 (`live_*.json`, `screened_*.json`)
- [ ] 현재 untracked `walk_forward_cross_momentum_full_20260427_192906.json` 을 evidence 로 add (design-021 인용 추적 누락 해소)
- [ ] tracked 인데 ADR 인용 없는 산출물 (§3.2) 정리 — evidence 강등 / 삭제 / archive
- [ ] 30 MB+ evidence 의 별도 archive 도입 (git LFS 또는 외부 스토리지)
- [ ] `outputs/backtest/` 디렉토리 도입 + `scripts/run_*backtest*.py` 의 출력 경로 변경 (코드 변경 — 별도 PR)
- [ ] 기존 `docs/backtest-results/` 의 generated artifact 일부 `outputs/backtest/` 로 이동

## 9. 참조

- 엔진 무결성: `docs/design/design-015-backtest-engine-integrity.md`
- 전략 ADR: `docs/design/design-016~021`
- 문서 신선도 정책: `.claude/rules/doc-freshness.md`
- 보안 정책 (gitignore 항목): `.claude/rules/security.md`
