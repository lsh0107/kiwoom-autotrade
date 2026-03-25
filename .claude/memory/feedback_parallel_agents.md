---
name: 문서 작업 병렬화
description: 문서 수정 시 파일 겹치지 않으면 담당별로 나눠서 병렬 투입
type: feedback
---

문서 수정 작업 시 하나의 에이전트에 전부 맡기지 말고, 파일이 안 겹치면 담당별로 나눠서 병렬 투입.

**Why:** 순차 처리하면 시간 낭비. 문서 파일은 서로 독립적이라 충돌 위험 없음.

**How to apply:** 예) rules/*.md 담당 1명, memory/*.md 담당 1명, airflow/tests/ + README 담당 1명 — 동시 투입.
