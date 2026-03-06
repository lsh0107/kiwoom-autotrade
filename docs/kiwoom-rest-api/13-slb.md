# 대차거래 API

> API 수: 4개

## 목차

- [ka10068 - 대차거래추이요청](#ka10068)
- [ka10069 - 대차거래상위10종목요청](#ka10069)
- [ka20068 - 대차거래추이요청(종목별)](#ka20068)
- [ka90012 - 대차거래내역요청](#ka90012)

---

## ka10068

**대차거래추이요청**

- **메뉴**: 국내주식 > 대차거래 > 대차거래추이요청(ka10068)
- **Method**: `POST`
- **URL**: `/api/dostk/slb`

### Request

**Headers**

| Element | 한글명 | Type | Required | Length | Description |
|---------|--------|------|----------|--------|-------------|
| `api-id` | TR명 | String | Y | 10 | TR명 |
| `authorization` | 접근토큰 | String | Y | 1000 | 접근토큰 |
| `cont-yn` | 연속조회여부 | String | N | 1 | 응답 Header의 연속조회여부값이 Y일 경우 다음데이터 요청시 응답 Header의 cont-yn값 세팅 |
| `next-key` | 연속조회키 | String | N | 50 | 응답 Header의 연속조회여부값이 Y일 경우 다음데이터 요청시 응답 Header의 next-key값 세팅 |

**Body**

| Element | 한글명 | Type | Required | Length | Description |
|---------|--------|------|----------|--------|-------------|
| `strt_dt` | 시작일자 | String | N | 8 | YYYYMMDD |
| `end_dt` | 종료일자 | String | N | 8 | YYYYMMDD |
| `all_tp` | 전체구분 | String | Y | 6 | 1: 전체표시 토큰 지정시 토큰타입("Bearer") 붙혀서 호출 예) Bearer Egicyx... |

### Response

**Headers**

| Element | 한글명 | Type | Required | Length | Description |
|---------|--------|------|----------|--------|-------------|
| `api-id` | TR명 | String | Y | 10 | TR명 |
| `cont-yn` | 연속조회여부 | String | N | 1 | 다음 데이터가 있을시 Y값 전달 |
| `next-key` | 연속조회키 | String | N | 50 | 다음 데이터가 있을시 다음 키값 전달 |

**Body**

| Element | 한글명 | Type | Required | Length | Description |
|---------|--------|------|----------|--------|-------------|
| `dbrt_trde_trnsn` | 대차거래추이 LIST N |  |  |  | 대차거래추이 LIST N |
| `- dt` | 일자 | String | N | 8 | 일자 |
| `- dbrt_trde_cntrcnt` | 대차거래체결주수 | String | N | 12 | 대차거래체결주수 |
| `- dbrt_trde_rpy` | 대차거래상환주수 | String | N | 18 | 대차거래상환주수 |
| `- rmnd` | 잔고주수 | String | N | 18 | 잔고주수 |
| `- dbrt_trde_irds` | 대차거래증감 | String | N | 60 | 대차거래증감 |
| `- remn_amt` | 잔고금액 | String | N | 18 | 잔고금액 |

---

## ka10069

**대차거래상위10종목요청**

- **메뉴**: 국내주식 > 대차거래 > 대차거래상위10종목요청(ka10069)
- **Method**: `POST`
- **URL**: `/api/dostk/slb`

### Request

**Headers**

| Element | 한글명 | Type | Required | Length | Description |
|---------|--------|------|----------|--------|-------------|
| `api-id` | TR명 | String | Y | 10 | TR명 |
| `authorization` | 접근토큰 | String | Y | 1000 | 접근토큰 |
| `cont-yn` | 연속조회여부 | String | N | 1 | 응답 Header의 연속조회여부값이 Y일 경우 다음데이터 요청시 응답 Header의 cont-yn값 세팅 |
| `next-key` | 연속조회키 | String | N | 50 | 응답 Header의 연속조회여부값이 Y일 경우 다음데이터 요청시 응답 Header의 next-key값 세팅 |

**Body**

| Element | 한글명 | Type | Required | Length | Description |
|---------|--------|------|----------|--------|-------------|
| `strt_dt` | 시작일자 | String | Y | 8 | YYYYMMDD (연도4자리, 월 2자리, 일 2자리 형식) |
| `end_dt` | 종료일자 | String | N | 8 | YYYYMMDD (연도4자리, 월 2자리, 일 2자리 형식) |
| `mrkt_tp` | 시장구분 | String | Y | 3 | 001:코스피, 101:코스닥 토큰 지정시 토큰타입("Bearer") 붙혀서 호출 예) Bearer Egicyx... |

### Response

**Headers**

| Element | 한글명 | Type | Required | Length | Description |
|---------|--------|------|----------|--------|-------------|
| `api-id` | TR명 | String | Y | 10 | TR명 |
| `cont-yn` | 연속조회여부 | String | N | 1 | 다음 데이터가 있을시 Y값 전달 |
| `next-key` | 연속조회키 | String | N | 50 | 다음 데이터가 있을시 다음 키값 전달 |

**Body**

| Element | 한글명 | Type | Required | Length | Description |
|---------|--------|------|----------|--------|-------------|
| `dbrt_trde_cntrcnt_su` | m 대차거래체결주수합 | String | N |  | m 대차거래체결주수합 |
| `dbrt_trde_rpy_sum` | 대차거래상환주수합 | String | N |  | 대차거래상환주수합 |
| `rmnd_sum` | 잔고주수합 | String | N |  | 잔고주수합 |
| `remn_amt_sum` | 잔고금액합 | String | N |  | 잔고금액합 |
| `dbrt_trde_cntrcnt_rt` | 대차거래체결주수비 율 | String | N |  | 대차거래체결주수비 율 |
| `dbrt_trde_rpy_rt` | 대차거래상환주수비 율 | String | N |  | 대차거래상환주수비 율 |
| `rmnd_rt` | 잔고주수비율 | String | N |  | 잔고주수비율 |

---

## ka20068

**대차거래추이요청(종목별)**

- **메뉴**: 국내주식 > 대차거래 > 대차거래추이요청(종목별)(ka20068)
- **Method**: `POST`
- **URL**: `/api/dostk/slb`

### Request

**Headers**

| Element | 한글명 | Type | Required | Length | Description |
|---------|--------|------|----------|--------|-------------|
| `api-id` | TR명 | String | Y | 10 | TR명 |
| `authorization` | 접근토큰 | String | Y | 1000 | 접근토큰 |
| `cont-yn` | 연속조회여부 | String | N | 1 | 응답 Header의 연속조회여부값이 Y일 경우 다음데이터 요청시 응답 Header의 cont-yn값 세팅 |
| `next-key` | 연속조회키 | String | N | 50 | 응답 Header의 연속조회여부값이 Y일 경우 다음데이터 요청시 응답 Header의 next-key값 세팅 |

**Body**

| Element | 한글명 | Type | Required | Length | Description |
|---------|--------|------|----------|--------|-------------|
| `strt_dt` | 시작일자 | String | N | 8 | YYYYMMDD |
| `end_dt` | 종료일자 | String | N | 8 | YYYYMMDD |
| `all_tp` | 전체구분 | String | N | 1 | 0:종목코드 입력종목만 표시 |
| `stk_cd` | 종목코드 | String | Y | 6 | 토큰 지정시 토큰타입("Bearer") 붙혀서 호출 예) Bearer Egicyx... |

### Response

**Headers**

| Element | 한글명 | Type | Required | Length | Description |
|---------|--------|------|----------|--------|-------------|
| `api-id` | TR명 | String | Y | 10 | TR명 |
| `cont-yn` | 연속조회여부 | String | N | 1 | 다음 데이터가 있을시 Y값 전달 |
| `next-key` | 연속조회키 | String | N | 50 | 다음 데이터가 있을시 다음 키값 전달 |

**Body**

| Element | 한글명 | Type | Required | Length | Description |
|---------|--------|------|----------|--------|-------------|
| `dbrt_trde_trnsn` | 대차거래추이 LIST N |  |  |  | 대차거래추이 LIST N |
| `- dt` | 일자 | String | N | 20 | 일자 |
| `- dbrt_trde_cntrcnt` | 대차거래체결주수 | String | N | 20 | 대차거래체결주수 |
| `- dbrt_trde_rpy` | 대차거래상환주수 | String | N | 20 | 대차거래상환주수 |
| `- dbrt_trde_irds` | 대차거래증감 | String | N | 20 | 대차거래증감 |
| `- rmnd` | 잔고주수 | String | N | 20 | 잔고주수 |
| `- remn_amt` | 잔고금액 | String | N | 20 | 잔고금액 |

---

## ka90012

**대차거래내역요청**

- **메뉴**: 국내주식 > 대차거래 > 대차거래내역요청(ka90012)
- **Method**: `POST`
- **URL**: `/api/dostk/slb`

### Request

**Headers**

| Element | 한글명 | Type | Required | Length | Description |
|---------|--------|------|----------|--------|-------------|
| `api-id` | TR명 | String | Y | 10 | TR명 |
| `authorization` | 접근토큰 | String | Y | 1000 | 접근토큰 |
| `cont-yn` | 연속조회여부 | String | N | 1 | 응답 Header의 연속조회여부값이 Y일 경우 다음데이터 요청시 응답 Header의 cont-yn값 세팅 |
| `next-key` | 연속조회키 | String | N | 50 | 응답 Header의 연속조회여부값이 Y일 경우 다음데이터 요청시 응답 Header의 next-key값 세팅 |

**Body**

| Element | 한글명 | Type | Required | Length | Description |
|---------|--------|------|----------|--------|-------------|
| `dt` | 일자 | String | Y | 8 | YYYYMMDD |
| `mrkt_tp` | 시장구분 | String | Y | 3 | 001:코스피, 101:코스닥 토큰 지정시 토큰타입("Bearer") 붙혀서 호출 예) Bearer Egicyx... |

### Response

**Headers**

| Element | 한글명 | Type | Required | Length | Description |
|---------|--------|------|----------|--------|-------------|
| `api-id` | TR명 | String | Y | 10 | TR명 |
| `cont-yn` | 연속조회여부 | String | N | 1 | 다음 데이터가 있을시 Y값 전달 |
| `next-key` | 연속조회키 | String | N | 50 | 다음 데이터가 있을시 다음 키값 전달 |

**Body**

| Element | 한글명 | Type | Required | Length | Description |
|---------|--------|------|----------|--------|-------------|
| `dbrt_trde_prps` | 대차거래내역 LIST N |  |  |  | 대차거래내역 LIST N |
| `- stk_nm` | 종목명 | String | N | 40 | 종목명 |
| `- stk_cd` | 종목코드 | String | N | 20 | 종목코드 |
| `- dbrt_trde_cntrcnt` | 대차거래체결주수 | String | N | 20 | 대차거래체결주수 |
| `- dbrt_trde_rpy` | 대차거래상환주수 | String | N | 20 | 대차거래상환주수 |
| `- rmnd` | 잔고주수 | String | N | 20 | 잔고주수 |
| `- remn_amt` | 잔고금액 | String | N | 20 | 잔고금액 |

---
