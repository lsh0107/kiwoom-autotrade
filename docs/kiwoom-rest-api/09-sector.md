# 업종 API

> API 수: 6개

## 목차

- [ka10010 - 업종프로그램요청](#ka10010)
- [ka10051 - 업종별투자자순매수요청](#ka10051)
- [ka20001 - 업종현재가요청](#ka20001)
- [ka20002 - 업종별주가요청](#ka20002)
- [ka20003 - 전업종지수요청](#ka20003)
- [ka20009 - 업종현재가일별요청](#ka20009)

---

## ka10010

**업종프로그램요청**

- **메뉴**: 국내주식 > 업종 > 업종프로그램요청(ka10010)
- **Method**: `POST`
- **URL**: `/api/dostk/sect`

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
| `dfrt_trst_sell_qty` | 차익위탁매도수량 | String | N | 20 | 차익위탁매도수량 |
| `dfrt_trst_sell_amt` | 차익위탁매도금액 | String | N | 20 | 차익위탁매도금액 |
| `dfrt_trst_buy_qty` | 차익위탁매수수량 | String | N | 20 | 차익위탁매수수량 |
| `dfrt_trst_buy_amt` | 차익위탁매수금액 | String | N | 20 | 차익위탁매수금액 |
| `dfrt_trst_netprps_qty` | 차익위탁순매수수량 | String | N | 20 | 차익위탁순매수수량 |
| `dfrt_trst_netprps_am` | t 차익위탁순매수금액 | String | N | 20 | t 차익위탁순매수금액 |
| `ndiffpro_trst_sell_qty` | 비차익위탁매도수량 | String | N | 20 | 비차익위탁매도수량 |
| `ndiffpro_trst_sell_am` | t 비차익위탁매도금액 | String | N | 20 | t 비차익위탁매도금액 |
| `ndiffpro_trst_buy_qty` | 비차익위탁매수수량 | String | N | 20 | 비차익위탁매수수량 |
| `ndiffpro_trst_buy_am` | 비차익위탁매수금액 | String | N | 20 | 비차익위탁매수금액 |

---

## ka10051

**업종별투자자순매수요청**

- **메뉴**: 국내주식 > 업종 > 업종별투자자순매수요청(ka10051)
- **Method**: `POST`
- **URL**: `/api/dostk/sect`

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
| `mrkt_tp` | 시장구분 | String | Y | 1 | 코스피:0, 코스닥:1 |
| `amt_qty_tp` | 금액수량구분 | String | Y | 1 | 금액:0, 수량:1 |
| `base_dt` | 기준일자 | String | N | 8 | YYYYMMDD |
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
| `inds_netprps` | 업종별순매수 LIST N |  |  |  | 업종별순매수 LIST N |
| `- inds_cd` | 업종코드 | String | N | 20 | 업종코드 |
| `- inds_nm` | 업종명 | String | N | 20 | 업종명 |
| `- cur_prc` | 현재가 | String | N | 20 | 현재가 |
| `- pre_smbol` | 대비부호 | String | N | 20 | 대비부호 |
| `- pred_pre` | 전일대비 | String | N | 20 | 전일대비 |
| `- flu_rt` | 등락율 | String | N | 20 | 등락율 |
| `- trde_qty` | 거래량 | String | N | 20 | 거래량 |

---

## ka20001

**업종현재가요청**

- **메뉴**: 국내주식 > 업종 > 업종현재가요청(ka20001)
- **Method**: `POST`
- **URL**: `/api/dostk/sect`

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
| `mrkt_tp` | 시장구분 | String | Y | 1 | 0:코스피, 1:코스닥, 2:코스피200 |
| `inds_cd` | 업종코드 | String | Y | 3 | 001:종합(KOSPI), 002:대형주, 003:중형주, 004:소형주 101:종합(KOSDAQ), 201:KOSPI200, 302:KOSTAR, 701: KRX100 나머지 ※ 업종코드 참고 토큰 지정시 토큰타입("Bearer") 붙혀서 호출 예) Bearer Egicyx... |

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
| `cur_prc` | 현재가 | String | N | 20 | 현재가 |
| `pred_pre_sig` | 전일대비기호 | String | N | 20 | 전일대비기호 |
| `pred_pre` | 전일대비 | String | N | 20 | 전일대비 |
| `flu_rt` | 등락률 | String | N | 20 | 등락률 |
| `trde_qty` | 거래량 | String | N | 20 | 거래량 |
| `trde_prica` | 거래대금 | String | N | 20 | 거래대금 |
| `trde_frmatn_stk_num` | 거래형성종목수 | String | N | 20 | 거래형성종목수 |
| `trde_frmatn_rt` | 거래형성비율 | String | N | 20 | 거래형성비율 |
| `open_pric` | 시가 | String | N | 20 | 시가 |

---

## ka20002

**업종별주가요청**

- **메뉴**: 국내주식 > 업종 > 업종별주가요청(ka20002)
- **Method**: `POST`
- **URL**: `/api/dostk/sect`

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
| `mrkt_tp` | 시장구분 | String | Y | 1 | 0:코스피, 1:코스닥, 2:코스피200 |
| `inds_cd` | 업종코드 | String | Y | 3 | 001:종합(KOSPI), 002:대형주, 003:중형주, 004:소형주 101:종합(KOSDAQ), 201:KOSPI200, 302:KOSTAR, 701: KRX100 나머지 ※ 업종코드 참고 |
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
| `inds_stkpc` | 업종별주가 LIST N |  |  |  | 업종별주가 LIST N |
| `- stk_cd` | 종목코드 | String | N | 20 | 종목코드 |
| `- stk_nm` | 종목명 | String | N | 40 | 종목명 |
| `- cur_prc` | 현재가 | String | N | 20 | 현재가 |
| `- pred_pre_sig` | 전일대비기호 | String | N | 20 | 전일대비기호 |
| `- pred_pre` | 전일대비 | String | N | 20 | 전일대비 |
| `- flu_rt` | 등락률 | String | N | 20 | 등락률 |
| `- now_trde_qty` | 현재거래량 | String | N | 20 | 현재거래량 |

---

## ka20003

**전업종지수요청**

- **메뉴**: 국내주식 > 업종 > 전업종지수요청(ka20003)
- **Method**: `POST`
- **URL**: `/api/dostk/sect`

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
| `inds_cd` | 업종코드 | String | Y | 3 | 001:종합(KOSPI), 101:종합(KOSDAQ) 토큰 지정시 토큰타입("Bearer") 붙혀서 호출 예) Bearer Egicyx... |

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
| `all_inds_idex` | 전업종지수 LIST N |  |  |  | 전업종지수 LIST N |
| `- stk_cd` | 종목코드 | String | N | 20 | 종목코드 |
| `- stk_nm` | 종목명 | String | N | 40 | 종목명 |
| `- cur_prc` | 현재가 | String | N | 20 | 현재가 |
| `- pre_sig` | 대비기호 | String | N | 20 | 대비기호 |
| `- pred_pre` | 전일대비 | String | N | 20 | 전일대비 |
| `- flu_rt` | 등락률 | String | N | 20 | 등락률 |
| `- trde_qty` | 거래량 | String | N | 20 | 거래량 |
| `- wght` | 비중 | String | N | 20 | 비중 |
| `- trde_prica` | 거래대금 | String | N | 20 | 거래대금 |
| `- upl` | 상한 | String | N | 20 | 상한 |

---

## ka20009

**업종현재가일별요청**

- **메뉴**: 국내주식 > 업종 > 업종현재가일별요청(ka20009)
- **Method**: `POST`
- **URL**: `/api/dostk/sect`

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
| `mrkt_tp` | 시장구분 | String | Y | 1 | 0:코스피, 1:코스닥, 2:코스피200 |
| `inds_cd` | 업종코드 | String | Y | 3 | 001:종합(KOSPI), 002:대형주, 003:중형주, 004:소형주 101:종합(KOSDAQ), 201:KOSPI200, 302:KOSTAR, 701: KRX100 나머지 ※ 업종코드 참고 토큰 지정시 토큰타입("Bearer") 붙혀서 호출 예) Bearer Egicyx... |

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
| `cur_prc` | 현재가 | String | N | 20 | 현재가 |
| `pred_pre_sig` | 전일대비기호 | String | N | 20 | 전일대비기호 |
| `pred_pre` | 전일대비 | String | N | 20 | 전일대비 |
| `flu_rt` | 등락률 | String | N | 20 | 등락률 |
| `trde_qty` | 거래량 | String | N | 20 | 거래량 |
| `trde_prica` | 거래대금 | String | N | 20 | 거래대금 |
| `trde_frmatn_stk_num` | 거래형성종목수 | String | N | 20 | 거래형성종목수 |
| `trde_frmatn_rt` | 거래형성비율 | String | N | 20 | 거래형성비율 |
| `open_pric` | 시가 | String | N | 20 | 시가 |

---
