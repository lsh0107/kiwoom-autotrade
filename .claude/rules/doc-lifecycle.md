# 문서 생명주기 규칙

**기록만 하고 버려지는 문서 금지. 모든 문서는 추적 가능해야 한다.**

## 분류

| 분류 | 예시 | 관리 |
|------|------|------|
| **활성** | project.md, architecture.md | 변경 시 즉시 갱신 |
| **참조** | design-v1.1.md, research-*.md | 상단에 결정 반영 노트 |
| **기록** | sessions/*.md | append only |

## 갱신 트리거

| 이벤트 | 갱신 대상 |
|--------|----------|
| 아키텍처 결정 | architecture.md + 관련 문서 |
| 코드 구현 완료 | project.md |
| Phase 전환 | project.md + design 문서 |
| 사용자 결정 변경 | **관련 모든 문서 즉시** |

## PR 전 검증
1. 활성 문서 ↔ 현재 코드/설계 일치?
2. 새 ADR → 관련 문서 교차 참조?
3. 문서화 안 된 결정 있는가?

## ADR 커밋
- 관련 커밋만: `feat(module, ADR-XXX): 설명`
- 무관 커밋은 기존 컨벤션

## 문서 인덱스

### 활성
| 파일 | 목적 |
|------|------|
| `project.md` | 프로젝트 상태 |
| `architecture.md` | ADR 기록 |
| `decisions-pending.md` | 미결정 추적 |

### 참조
| 파일 | 목적 |
|------|------|
| `design-v1.1.md` | 시스템 설계 기준 |
| `research-*.md` | 리서치 결과 |
| `docs/kiwoom-rest-api/` | 키움 API 레퍼런스 |
