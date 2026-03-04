# 공매도 API

> API 수: 1개

## 목차

- [ka10014 - 공매도추이요청](#ka10014)

---

## ka10014

**공매도추이요청**

- **메뉴**: 국내주식 > 공매도 > 공매도추이요청(ka10014)
- **Method**: `POST`
- **URL**: `/api/dostk/shsa`

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
| `stk_cd` | 종목코드 | String | Y | 20 | 거래소별 종목코드 (KRX:039490,NXT:039490_NX,SOR:039490_AL) |
| `tm_tp` | 시간구분 | String | N | 1 | 0:시작일, 1:기간 |
| `strt_dt` | 시작일자 | String | Y | 8 | YYYYMMDD |
| `end_dt` | 종료일자 | String | Y | 8 | YYYYMMDD 토큰 지정시 토큰타입("Bearer") 붙혀서 호출 예) Bearer Egicyx... |

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
| `shrts_trnsn` | 공매도추이 LIST N |  |  |  | 공매도추이 LIST N |
| `- dt` | 일자 | String | N | 20 | 일자 |
| `- close_pric` | 종가 | String | N | 20 | 종가 |
| `- pred_pre_sig` | 전일대비기호 | String | N | 20 | 전일대비기호 |
| `- pred_pre` | 전일대비 | String | N | 20 | 전일대비 |
| `- flu_rt` | 등락율 | String | N | 20 | 등락율 |
| `- trde_qty` | 거래량 | String | N | 20 | 거래량 |
| `- shrts_qty` | 공매도량 | String | N | 20 | 공매도량 |

---

