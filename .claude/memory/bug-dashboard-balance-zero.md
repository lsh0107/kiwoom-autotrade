---
name: Dashboard 잔고/보유종목 0 표시 버그
description: 대시보드에서 금액과 보유종목이 0으로 표시되는 버그 원인 규명 및 해결 완료 기록
type: project
---

## 버그 개요
- **증상**: 대시보드에서 총 평가금액, 주문가능금액, 보유종목 0으로 표시됨
- **영향 범위**: Frontend 대시보드 전체 (SectionCards, HoldingsTable)
- **상태**: ✅ 2026-03-13 최종 수정 완료 (PR #111→#112→#113 kt00004+ord_alowa 확정)

## 최종 수정 내용 (세션 19~20)
1. `_request()`가 `return_code` 에러 미감지 → 반환 코드 에러 감지 추가
2. 토큰 8005 에러 시 재시도 로직 없음 → 자동 재시도 추가
3. `entr`(예수금)에 D+2 미결제 매수금 포함 → `kt00018` (prsm_dpst_aset_amt) 기반 정확한 금액 계산으로 전환

## 원인 분석

### 추적 경로
1. Frontend: `useBalance()` hook → API GET `/account/balance` 호출
2. Backend: `src/api/v1/account.py` → `KiwoomClient.get_balance()` 호출
3. Backend: `src/broker/kiwoom.py:542-623` → 2개 API 호출

### 핵심 버그
**src/broker/kiwoom.py:600 라인**
```python
available_cash = _safe_int(deposit_data.get("ord_alow_amt", 0))
```

**문제점**:
- 현재 코드는 kt00001 (예수금상세현황) API 호출
- kt00001 응답에는 `ord_alow_amt` 필드가 **없음**
- 따라서 `.get("ord_alow_amt", 0)`은 항상 0 반환

### 키움 공식 문서 확인
- **참조 문서**: git show 76782c4:docs/kiwoom-rest-api/02-account.md
- **ka10085** (계좌수익률): 보유종목 리스트 → 필드명 정확 ✓
- **kt00001** (예수금상세현황): 응답에 `entr`, `profa_ch` 등 포함, `ord_alow_amt` 없음 ✗
- **kt00005** (체결잔고요청): `ord_alowa` (주문가능현금) ← **정답**

## 해결책
두 가지 옵션 → 리드 선택 대기 중:

### Option A: kt00005로 교체 (권장)
```python
# API ID 추가
"balance_position": "kt00005",  # 체결잔고

# get_balance() 메서드 수정
deposit_data = await self._request(
    ENDPOINTS["account"],
    API_IDS["balance_position"],  # kt00005
    json_body={"dmst_stex_tp": "KRX"},
)
available_cash = _safe_int(deposit_data.get("ord_alowa", 0))  # 정확한 필드명
```

### Option B: kt00001 필드명 수정 (간단)
```python
# kt00001의 실제 필드 사용
available_cash = _safe_int(deposit_data.get("entr", 0))  # 예수금만
```

## 영향
- 대시보드 전체 (총 평가금액, 주문가능금액, 보유종목 테이블)
- 프론트 `useBalance()` hook이 응답하는 모든 데이터 0

## 이력
- 2026-03-12 세션 18: 원인 확정 (kt00001 필드명 `ord_alow_amt` 없음)
- 2026-03-12 세션 19: 1차 수정 — `ord_alow_amt` → `entr` (PR #111)
- 2026-03-12 세션 20: 근본 원인 3건 추가 수정 (return_code 감지, 8005 재시도, kt00018 기반) (PR #112)
- 2026-03-13 세션 22: 최종 수정 — kt00001→kt00004(계좌평가현황), ord_alow_amt→ord_alowa(주문가능현금) (PR #113)
