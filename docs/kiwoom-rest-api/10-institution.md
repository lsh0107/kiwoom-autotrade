# 기관/외국인 API

> API 수: 4개

## 목차

- [ka10008 - 주식외국인종목별매매동향](#ka10008)
- [ka10009 - 주식기관요청](#ka10009)
- [ka10131 - 기관외국인연속매매현황요청](#ka10131)
- [ka52301 - 금현물투자자현황](#ka52301)

---

## ka10008

**주식외국인종목별매매동향**

- **메뉴**: 국내주식 > 기관/외국인 > 주식외국인종목별매매동향(ka10008)
- **Method**: `POST`
- **URL**: `/api/dostk/frgnistt`

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
| `stk_cd` | 종목코드 | String | Y | 20 | 거래소별 종목코드 (KRX:039490,NXT:039490_NX,SOR:039490_AL) 토큰 지정시 토큰타입("Bearer") 붙혀서 호출 예) Bearer Egicyx... |

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
| `stk_frgnr` | 주식외국인 LIST N |  |  |  | 주식외국인 LIST N |
| `- dt` | 일자 | String | N | 20 | 일자 |
| `- close_pric` | 종가 | String | N | 20 | 종가 |
| `- pred_pre` | 전일대비 | String | N | 20 | 전일대비 |
| `- trde_qty` | 거래량 | String | N | 20 | 거래량 |
| `- chg_qty` | 변동수량 | String | N | 20 | 변동수량 |
| `- poss_stkcnt` | 보유주식수 | String | N | 20 | 보유주식수 |
| `- wght` | 비중 | String | N | 20 | 비중 |
| `- gain_pos_stkcnt` | 취득가능주식수 | String | N | 20 | 취득가능주식수 |
| `- frgnr_limit` | 외국인한도 | String | N | 20 | 외국인한도 |
| `- frgnr_limit_irds` | 외국인한도증감 | String | N | 20 | 외국인한도증감 |

---

## ka10009

**주식기관요청**

- **메뉴**: 국내주식 > 기관/외국인 > 주식기관요청(ka10009)
- **Method**: `POST`
- **URL**: `/api/dostk/frgnistt`

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
| `stk_cd` | 종목코드 | String | Y | 20 | 거래소별 종목코드 (KRX:039490,NXT:039490_NX,SOR:039490_AL) 토큰 지정시 토큰타입("Bearer") 붙혀서 호출 예) Bearer Egicyx... |

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
| `date` | 날짜 | String | N | 20 | 날짜 |
| `close_pric` | 종가 | String | N | 20 | 종가 |
| `pre` | 대비 | String | N | 20 | 대비 |
| `orgn_dt_acc` | 기관기간누적 | String | N | 20 | 기관기간누적 |
| `orgn_daly_nettrde` | 기관일별순매매 | String | N | 20 | 기관일별순매매 |
| `frgnr_daly_nettrde` | 외국인일별순매매 | String | N | 20 | 외국인일별순매매 |
| `frgnr_qota_rt` | 외국인지분율 | String | N | 20 | 외국인지분율 |

---

## ka10131

**기관외국인연속매매현황요청**

- **메뉴**: 국내주식 > 기관/외국인 > 기관외국인연속매매현황요청(ka10131)
- **Method**: `POST`
- **URL**: `/api/dostk/frgnistt`

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
| `dt` | 기간 | String | Y | 3 | 1:최근일, 3:3일, 5:5일, 10:10일, 20:20일, 120:120일, 0:시작일자/종료일자로 조회 |
| `strt_dt` | 시작일자 | String | N | 8 | YYYYMMDD |
| `end_dt` | 종료일자 | String | N | 8 | YYYYMMDD |
| `mrkt_tp` | 장구분 | String | Y | 3 | 001:코스피, 101:코스닥 |
| `netslmt_tp` | 순매도수구분 | String | Y | 1 | 2:순매수(고정값) |
| `stk_inds_tp` | 종목업종구분 | String | Y | 1 | 0:종목(주식),1:업종 |
| `amt_qty_tp` | 금액수량구분 | String | Y | 1 | 0:금액, 1:수량 |
| `stex_tp` | 거래소구분 | String | Y | 1 | 1:KRX, 2:NXT, 3:통합 토큰 지정시 토큰타입("Bearer") 붙혀서 호출 예) Bearer Egicyx... |

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
| `orgn_frgnr_cont_trde` | _prst 기관외국인연속매매 현황 LIST N |  |  |  | _prst 기관외국인연속매매 현황 LIST N |
| `- rank` | 순위 | String | N |  | 순위 |
| `- stk_cd` | 종목코드 | String | N | 6 | 종목코드 |

---

## ka52301

**금현물투자자현황**

- **메뉴**: 국내주식 > 기관/외국인 > 금현물투자자현황(ka52301)
- **Method**: `POST`
- **URL**: `/api/dostk/frgnistt`

### Request

**Headers**

| Element | 한글명 | Type | Required | Length | Description |
|---------|--------|------|----------|--------|-------------|
| `api-id` | TR명 | String | Y | 10 | TR명 |
| `authorization` | 접근토큰 | String | Y | 1000 | 접근토큰 |
| `cont-yn` | 연속조회여부 | String | N | 1 | 응답 Header의 연속조회여부값이 Y일 경우 다음데이터 요청시 응답 Header의 cont-yn값 세팅 |
| `next-key` | 연속조회키 | String | N | 50 | 응답 Header의 연속조회여부값이 Y일 경우 다음데이터 요청시 응답 Header의 next-key값 세팅 토큰 지정시 토큰타입("Bearer") 붙혀서 호출 예) Bearer Egicyx... |

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
| `inve_trad_stat` | 금현물투자자현황 LIST N |  |  |  | 금현물투자자현황 LIST N |
| `- all_dfrt_trst_sell_qty` | 투자자별 매도 수량(천) | String | N | 20 | 투자자별 매도 수량(천) |
| `- sell_qty_irds` | 투자자별 매도 수량 증감(천) | String | N | 20 | 투자자별 매도 수량 증감(천) |
| `all_dfrt_trst_sell_amt` | 투자자별 매도 금액(억) | String | N | 20 | 투자자별 매도 금액(억) |
| `- sell_amt_irds` | 투자자별 매도 금액 증감(억) | String | N | 20 | 투자자별 매도 금액 증감(억) |
| `all_dfrt_trst_buy_qty` | 투자자별 매수 수량(천) | String | N | 20 | 투자자별 매수 수량(천) |
| `- buy_qty_irds` | 투자자별 매수 수량 증감(천) | String | N | 20 | 투자자별 매수 수량 증감(천) |
| `all_dfrt_trst_buy_amt` | 투자자별 매수 금액(억) | String | N | 20 | 투자자별 매수 금액(억) |
| `- buy_amt_irds` | 투자자별 매수 금액 | String | N | 20 | 투자자별 매수 금액 |

---

