# 시세/시장조건 API

> API 수: 25개

## 목차

- [ka10004 - 주식호가요청](#ka10004)
- [ka10005 - 주식일주월시분요청](#ka10005)
- [ka10006 - 주식시분요청](#ka10006)
- [ka10007 - 시세표성정보요청](#ka10007)
- [ka10011 - 신주인수권전체시세요청](#ka10011)
- [ka10044 - 일별기관매매종목요청](#ka10044)
- [ka10045 - 종목별기관매매추이요청](#ka10045)
- [ka10046 - 체결강도추이시간별요청](#ka10046)
- [ka10047 - 체결강도추이일별요청](#ka10047)
- [ka10063 - 장중투자자별매매요청](#ka10063)
- [ka10066 - 장마감후투자자별매매요청](#ka10066)
- [ka10078 - 증권사별종목매매동향요청](#ka10078)
- [ka10086 - 일별주가요청](#ka10086)
- [ka10087 - 시간외단일가요청](#ka10087)
- [ka50010 - 금현물체결추이](#ka50010)
- [ka50012 - 금현물일별추이](#ka50012)
- [ka50087 - 금현물예상체결](#ka50087)
- [ka50100 - 금현물 시세정보](#ka50100)
- [ka50101 - 금현물 호가](#ka50101)
- [ka90005 - 프로그램매매추이요청 시간대별](#ka90005)
- [ka90006 - 프로그램매매차익잔고추이요청](#ka90006)
- [ka90007 - 프로그램매매누적추이요청](#ka90007)
- [ka90008 - 종목시간별프로그램매매추이요청](#ka90008)
- [ka90010 - 프로그램매매추이요청 일자별](#ka90010)
- [ka90013 - 종목일별프로그램매매추이요청](#ka90013)

---

## ka10004

**주식호가요청**

- **메뉴**: 국내주식 > 시세 > 주식호가요청(ka10004)
- **Method**: `POST`
- **URL**: `/api/dostk/mrkcond`

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
| `bid_req_base_tm` | 호가잔량기준시간 | String | N | 20 | 호가시간 |
| `sel_10th_pre_req_pre` | 매도10차선잔량대비 | String | N | 20 | 매도호가직전대비10 |
| `sel_10th_pre_req` | 매도10차선잔량 | String | N | 20 | 매도호가수량10 |
| `sel_10th_pre_bid` | 매도10차선호가 | String | N | 20 | 매도호가10 |
| `sel_9th_pre_req_pre` | 매도9차선잔량대비 | String | N | 20 | 매도호가직전대비9 |
| `sel_9th_pre_req` | 매도9차선잔량 | String | N | 20 | 매도호가수량9 |
| `sel_9th_pre_bid` | 매도9차선호가 | String | N | 20 | 매도호가9 |
| `sel_8th_pre_req_pre` | 매도8차선잔량대비 | String | N | 20 | 매도호가직전대비8 |
| `sel_8th_pre_req` | 매도8차선잔량 | String | N | 20 | 매도호가수량8 |
| `sel_8th_pre_bid` | 매도8차선호가 | String | N | 20 | 매도호가8 |
| `sel_7th_pre_req_pre` | 매도7차선잔량대비 | String | N | 20 | 매도호가직전대비7 |

---

## ka10005

**주식일주월시분요청**

- **메뉴**: 국내주식 > 시세 > 주식일주월시분요청(ka10005)
- **Method**: `POST`
- **URL**: `/api/dostk/mrkcond`

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
| `stk_ddwkmm` | 주식일주월시분 LIST N |  |  |  | 주식일주월시분 LIST N |
| `- date` | 날짜 | String | N | 20 | 날짜 |
| `- open_pric` | 시가 | String | N | 20 | 시가 |
| `- high_pric` | 고가 | String | N | 20 | 고가 |
| `- low_pric` | 저가 | String | N | 20 | 저가 |
| `- close_pric` | 종가 | String | N | 20 | 종가 |
| `- pre` | 대비 | String | N | 20 | 대비 |
| `- flu_rt` | 등락률 | String | N | 20 | 등락률 |
| `- trde_qty` | 거래량 | String | N | 20 | 거래량 |
| `- trde_prica` | 거래대금 | String | N | 20 | 거래대금 |
| `- for_poss` | 외인보유 | String | N | 20 | 외인보유 |

---

## ka10006

**주식시분요청**

- **메뉴**: 국내주식 > 시세 > 주식시분요청(ka10006)
- **Method**: `POST`
- **URL**: `/api/dostk/mrkcond`

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
| `open_pric` | 시가 | String | N | 20 | 시가 |
| `high_pric` | 고가 | String | N | 20 | 고가 |
| `low_pric` | 저가 | String | N | 20 | 저가 |
| `close_pric` | 종가 | String | N | 20 | 종가 |
| `pre` | 대비 | String | N | 20 | 대비 |
| `flu_rt` | 등락률 | String | N | 20 | 등락률 |
| `trde_qty` | 거래량 | String | N | 20 | 거래량 |
| `trde_prica` | 거래대금 | String | N | 20 | 거래대금 |
| `cntr_str` | 체결강도 | String | N | 20 | 체결강도 |

---

## ka10007

**시세표성정보요청**

- **메뉴**: 국내주식 > 시세 > 시세표성정보요청(ka10007)
- **Method**: `POST`
- **URL**: `/api/dostk/mrkcond`

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
| `stk_nm` | 종목명 | String | N | 40 | 종목명 |
| `stk_cd` | 종목코드 | String | N | 6 | 종목코드 |
| `date` | 날짜 | String | N | 20 | 날짜 |
| `tm` | 시간 | String | N | 20 | 시간 |
| `pred_close_pric` | 전일종가 | String | N | 20 | 전일종가 |
| `pred_trde_qty` | 전일거래량 | String | N | 20 | 전일거래량 |
| `upl_pric` | 상한가 | String | N | 20 | 상한가 |
| `lst_pric` | 하한가 | String | N | 20 | 하한가 |
| `pred_trde_prica` | 전일거래대금 | String | N | 20 | 전일거래대금 |
| `flo_stkcnt` | 상장주식수 | String | N | 20 | 상장주식수 |
| `cur_prc` | 현재가 | String | N | 20 | 현재가 |

---

## ka10011

**신주인수권전체시세요청**

- **메뉴**: 국내주식 > 시세 > 신주인수권전체시세요청(ka10011)
- **Method**: `POST`
- **URL**: `/api/dostk/mrkcond`

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
| `newstk_recvrht_tp` | 신주인수권구분 | String | Y | 2 | 00:전체, 05:신주인수권증권, 07:신주인수권증서 토큰 지정시 토큰타입("Bearer") 붙혀서 호출 예) Bearer Egicyx... |

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
| `newstk_recvrht_mrpr` | 신주인수권시세 LIST N |  |  |  | 신주인수권시세 LIST N |
| `- stk_cd` | 종목코드 | String | N | 20 | 종목코드 |
| `- stk_nm` | 종목명 | String | N | 40 | 종목명 |
| `- cur_prc` | 현재가 | String | N | 20 | 현재가 |
| `- pred_pre_sig` | 전일대비기호 | String | N | 20 | 전일대비기호 |
| `- pred_pre` | 전일대비 | String | N | 20 | 전일대비 |
| `- flu_rt` | 등락율 | String | N | 20 | 등락율 |
| `- fpr_sel_bid` | 최우선매도호가 | String | N | 20 | 최우선매도호가 |
| `- fpr_buy_bid` | 최우선매수호가 | String | N | 20 | 최우선매수호가 |
| `- acc_trde_qty` | 누적거래량 | String | N | 20 | 누적거래량 |
| `- open_pric` | 시가 | String | N | 20 | 시가 |

---

## ka10044

**일별기관매매종목요청**

- **메뉴**: 국내주식 > 시세 > 일별기관매매종목요청(ka10044)
- **Method**: `POST`
- **URL**: `/api/dostk/mrkcond`

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
| `strt_dt` | 시작일자 | String | Y | 8 | YYYYMMDD |
| `end_dt` | 종료일자 | String | Y | 8 | YYYYMMDD |
| `trde_tp` | 매매구분 | String | Y | 1 | 1:순매도, 2:순매수 |
| `mrkt_tp` | 시장구분 | String | Y | 3 | 001:코스피, 101:코스닥 |
| `stex_tp` | 거래소구분 | String | Y | 1 | 1:KRX, 2:NXT 3.통합 토큰 지정시 토큰타입("Bearer") 붙혀서 호출 예) Bearer Egicyx... |

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
| `daly_orgn_trde_stk` | 일별기관매매종목 LIST N |  |  |  | 일별기관매매종목 LIST N |
| `- stk_cd` | 종목코드 | String | N | 20 | 종목코드 |
| `- stk_nm` | 종목명 | String | N | 40 | 종목명 |
| `- netprps_qty` | 순매수수량 | String | N | 20 | 순매수수량 |
| `- netprps_amt` | 순매수금액 | String | N | 20 | 순매수금액 |

---

## ka10045

**종목별기관매매추이요청**

- **메뉴**: 국내주식 > 시세 > 종목별기관매매추이요청(ka10045)
- **Method**: `POST`
- **URL**: `/api/dostk/mrkcond`

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
| `strt_dt` | 시작일자 | String | Y | 8 | YYYYMMDD |
| `end_dt` | 종료일자 | String | Y | 8 | YYYYMMDD |
| `orgn_prsm_unp_tp` | 기관추정단가구분 | String | Y | 1 | 1:매수단가, 2:매도단가 |
| `for_prsm_unp_tp` | 외인추정단가구분 | String | Y | 1 | 1:매수단가, 2:매도단가 토큰 지정시 토큰타입("Bearer") 붙혀서 호출 예) Bearer Egicyx... |

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
| `orgn_prsm_avg_pric` | 기관추정평균가 | String | N |  | 기관추정평균가 |
| `for_prsm_avg_pric` | 외인추정평균가 | String | N |  | 외인추정평균가 |
| `stk_orgn_trde_trnsn` | 종목별기관매매추이 LIST N |  |  |  | 종목별기관매매추이 LIST N |
| `- dt` | 일자 | String | N | 20 | 일자 |
| `- close_pric` | 종가 | String | N | 20 | 종가 |
| `- pre_sig` | 대비기호 | String | N | 20 | 대비기호 |
| `- pred_pre` | 전일대비 | String | N | 20 | 전일대비 |

---

## ka10046

**체결강도추이시간별요청**

- **메뉴**: 국내주식 > 시세 > 체결강도추이시간별요청(ka10046)
- **Method**: `POST`
- **URL**: `/api/dostk/mrkcond`

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
| `stk_cd` | 종목코드 | String | Y | 6 | 거래소별 종목코드 (KRX:039490,NXT:039490_NX,SOR:039490_AL) 토큰 지정시 토큰타입("Bearer") 붙혀서 호출 예) Bearer Egicyx... |

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
| `cntr_str_tm` | 체결강도시간별 LIST N |  |  |  | 체결강도시간별 LIST N |
| `- cntr_tm` | 체결시간 | String | N | 20 | 체결시간 |
| `- cur_prc` | 현재가 | String | N | 20 | 현재가 |
| `- pred_pre` | 전일대비 | String | N | 20 | 전일대비 |
| `- pred_pre_sig` | 전일대비기호 | String | N | 20 | 전일대비기호 |
| `- flu_rt` | 등락율 | String | N | 20 | 등락율 |
| `- trde_qty` | 거래량 | String | N | 20 | 거래량 |
| `- acc_trde_prica` | 누적거래대금 | String | N | 20 | 누적거래대금 |
| `- acc_trde_qty` | 누적거래량 | String | N | 20 | 누적거래량 |
| `- cntr_str` | 체결강도 | String | N | 20 | 체결강도 |
| `- cntr_str_5min` | 체결강도5분 | String | N | 20 | 체결강도5분 |

---

## ka10047

**체결강도추이일별요청**

- **메뉴**: 국내주식 > 시세 > 체결강도추이일별요청(ka10047)
- **Method**: `POST`
- **URL**: `/api/dostk/mrkcond`

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
| `stk_cd` | 종목코드 | String | Y | 6 | 거래소별 종목코드 (KRX:039490,NXT:039490_NX,SOR:039490_AL) 토큰 지정시 토큰타입("Bearer") 붙혀서 호출 예) Bearer Egicyx... |

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
| `cntr_str_daly` | 체결강도일별 LIST N |  |  |  | 체결강도일별 LIST N |
| `- dt` | 일자 | String | N | 20 | 일자 |
| `- cur_prc` | 현재가 | String | N | 20 | 현재가 |
| `- pred_pre` | 전일대비 | String | N | 20 | 전일대비 |
| `- pred_pre_sig` | 전일대비기호 | String | N | 20 | 전일대비기호 |
| `- flu_rt` | 등락율 | String | N | 20 | 등락율 |
| `- trde_qty` | 거래량 | String | N | 20 | 거래량 |
| `- acc_trde_prica` | 누적거래대금 | String | N | 20 | 누적거래대금 |
| `- acc_trde_qty` | 누적거래량 | String | N | 20 | 누적거래량 |
| `- cntr_str` | 체결강도 | String | N | 20 | 체결강도 |
| `- cntr_str_5min` | 체결강도5일 | String | N | 20 | 체결강도5일 |

---

## ka10063

**장중투자자별매매요청**

- **메뉴**: 국내주식 > 시세 > 장중투자자별매매요청(ka10063)
- **Method**: `POST`
- **URL**: `/api/dostk/mrkcond`

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
| `mrkt_tp` | 시장구분 | String | Y | 3 | 000:전체, 001:코스피, 101:코스닥 |
| `amt_qty_tp` | 금액수량구분 | String | Y | 1 | 1: 금액&수량 |
| `invsr` | 투자자별 | String | Y | 1 | 6:외국인, 7:기관계, 1:투신, 0:보험, 2:은행, 3:연기금, 4:국가, 5:기타법인 |
| `frgn_all` | 외국계전체 | String | Y | 1 | 1:체크, 0:미체크 |
| `smtm_netprps_tp` | 동시순매수구분 | String | Y | 1 | 1:체크, 0:미체크 |
| `stex_tp` | 거래소구분 | String | Y | 1 | 1:KRX, 2:NXT 3.통합 토큰 지정시 토큰타입("Bearer") 붙혀서 호출 예) Bearer Egicyx... |

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
| `opmr_invsr_trde` | 장중투자자별매매 LIST N |  |  |  | 장중투자자별매매 LIST N |
| `- stk_cd` | 종목코드 | String | N | 20 | 종목코드 |
| `- stk_nm` | 종목명 | String | N | 40 | 종목명 |
| `- cur_prc` | 현재가 | String | N | 20 | 현재가 |
| `- pre_sig` | 대비기호 | String | N | 20 | 대비기호 |
| `- pred_pre` | 전일대비 | String | N | 20 | 전일대비 |

---

## ka10066

**장마감후투자자별매매요청**

- **메뉴**: 국내주식 > 시세 > 장마감후투자자별매매요청(ka10066)
- **Method**: `POST`
- **URL**: `/api/dostk/mrkcond`

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
| `mrkt_tp` | 시장구분 | String | Y | 3 | 000:전체, 001:코스피, 101:코스닥 |
| `amt_qty_tp` | 금액수량구분 | String | Y | 1 | 1:금액, 2:수량 |
| `trde_tp` | 매매구분 | String | Y | 1 | 0:순매수, 1:매수, 2:매도 |
| `stex_tp` | 거래소구분 | String | Y | 1 | 1:KRX, 2:NXT 3.통합 토큰 지정시 토큰타입("Bearer") 붙혀서 호출 예) Bearer Egicyx... |

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
| `opaf_invsr_trde` | 장중투자자별매매차 트 LIST N |  |  |  | 장중투자자별매매차 트 LIST N |
| `- stk_cd` | 종목코드 | String | N | 20 | 종목코드 |
| `- stk_nm` | 종목명 | String | N | 40 | 종목명 |
| `- cur_prc` | 현재가 | String | N | 20 | 현재가 |
| `- pre_sig` | 대비기호 | String | N | 20 | 대비기호 |
| `- pred_pre` | 전일대비 | String | N | 20 | 전일대비 |
| `- flu_rt` | 등락률 | String | N | 20 | 등락률 |
| `- trde_qty` | 거래량 | String | N | 20 | 거래량 |

---

## ka10078

**증권사별종목매매동향요청**

- **메뉴**: 국내주식 > 시세 > 증권사별종목매매동향요청(ka10078)
- **Method**: `POST`
- **URL**: `/api/dostk/mrkcond`

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
| `mmcm_cd` | 회원사코드 | String | Y | 3 | 회원사 코드는 ka10102 조회 |
| `stk_cd` | 종목코드 | String | Y | 20 | 거래소별 종목코드 (KRX:039490,NXT:039490_NX,SOR:039490_AL) |
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
| `sec_stk_trde_trend` | 증권사별종목매매동 향 LIST N |  |  |  | 증권사별종목매매동 향 LIST N |
| `- dt` | 일자 | String | N | 20 | 일자 |
| `- cur_prc` | 현재가 | String | N | 20 | 현재가 |
| `- pre_sig` | 대비기호 | String | N | 20 | 대비기호 |
| `- pred_pre` | 전일대비 | String | N | 20 | 전일대비 |
| `- flu_rt` | 등락율 | String | N | 20 | 등락율 |
| `- acc_trde_qty` | 누적거래량 | String | N | 20 | 누적거래량 |

---

## ka10086

**일별주가요청**

- **메뉴**: 국내주식 > 시세 > 일별주가요청(ka10086)
- **Method**: `POST`
- **URL**: `/api/dostk/mrkcond`

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
| `qry_dt` | 조회일자 | String | Y | 8 | YYYYMMDD |
| `indc_tp` | 표시구분 | String | Y | 1 | 0:수량, 1:금액(백만원) 토큰 지정시 토큰타입("Bearer") 붙혀서 호출 예) Bearer Egicyx... |

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
| `daly_stkpc` | 일별주가 LIST N |  |  |  | 일별주가 LIST N |
| `- date` | 날짜 | String | N | 20 | 날짜 |
| `- open_pric` | 시가 | String | N | 20 | 시가 |
| `- high_pric` | 고가 | String | N | 20 | 고가 |
| `- low_pric` | 저가 | String | N | 20 | 저가 |
| `- close_pric` | 종가 | String | N | 20 | 종가 |
| `- pred_rt` | 전일비 | String | N | 20 | 전일비 |
| `- flu_rt` | 등락률 | String | N | 20 | 등락률 |
| `- trde_qty` | 거래량 | String | N | 20 | 거래량 |

---

## ka10087

**시간외단일가요청**

- **메뉴**: 국내주식 > 시세 > 시간외단일가요청(ka10087)
- **Method**: `POST`
- **URL**: `/api/dostk/mrkcond`

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
| `bid_req_base_tm` | 호가잔량기준시간 | String | N |  | 호가잔량기준시간 |
| `ovt_sigpric_sel_bid_j` | ub_pre_5 시간외단일가_매도호 가직전대비5 | String | N |  | ub_pre_5 시간외단일가_매도호 가직전대비5 |
| `ovt_sigpric_sel_bid_j` | ub_pre_4 시간외단일가_매도호 가직전대비4 | String | N |  | ub_pre_4 시간외단일가_매도호 가직전대비4 |
| `ovt_sigpric_sel_bid_j` | ub_pre_3 시간외단일가_매도호 가직전대비3 | String | N |  | ub_pre_3 시간외단일가_매도호 가직전대비3 |
| `ovt_sigpric_sel_bid_j` | ub_pre_2 시간외단일가_매도호 가직전대비2 | String | N |  | ub_pre_2 시간외단일가_매도호 가직전대비2 |
| `ovt_sigpric_sel_bid_j` | ub_pre_1 시간외단일가_매도호 가직전대비1 | String | N |  | ub_pre_1 시간외단일가_매도호 가직전대비1 |
| `ovt_sigpric_sel_bid_q` | ty_5 시간외단일가_매도호 가수량5 | String | N |  | ty_5 시간외단일가_매도호 가수량5 |
| `ovt_sigpric_sel_bid_q` | ty_4 시간외단일가_매도호 가수량4 | String | N |  | ty_4 시간외단일가_매도호 가수량4 |

---

## ka50010

**금현물체결추이**

- **메뉴**: 국내주식 > 시세 > 금현물체결추이(ka50010)
- **Method**: `POST`
- **URL**: `/api/dostk/mrkcond`

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
| `stk_cd` | 종목코드 | String | Y | 20 | M04020000 금 99.99_1kg, M04020100 미니금 99.99_100g 토큰 지정시 토큰타입("Bearer") 붙혀서 호출 예) Bearer Egicyx... |

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
| `gold_cntr` | 금현물체결추이 LIST N |  |  |  | 금현물체결추이 LIST N |
| `- cntr_pric` | 체결가 | String | N | 20 | 체결가 |
| `- pred_pre` | 전일 대비 | String | N | 20 | 전일 대비 |
| `- flu_rt` | 등락율 | String | N | 20 | 등락율 |
| `- trde_qty` | 누적 거래량 | String | N | 20 | 누적 거래량 |
| `- acc_trde_prica` | 누적 거래대금 | String | N | 20 | 누적 거래대금 |
| `- cntr_trde_qty` | 거래량(체결량) | String | N | 20 | 거래량(체결량) |
| `- tm` | 체결시간 | String | N | 20 | 체결시간 |
| `- pre_sig` | 전일대비기호 | String | N | 20 | 전일대비기호 |
| `- pri_sel_bid_unit` | 매도호가 | String | N | 20 | 매도호가 |
| `- pri_buy_bid_unit` | 매수호가 | String | N | 20 | 매수호가 |

---

## ka50012

**금현물일별추이**

- **메뉴**: 국내주식 > 시세 > 금현물일별추이(ka50012)
- **Method**: `POST`
- **URL**: `/api/dostk/mrkcond`

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
| `stk_cd` | 종목코드 | String | Y | 20 | M04020000 금 99.99_1kg, M04020100 미니금 99.99_100g |
| `base_dt` | 기준일자 | String | Y | 8 | YYYYMMDD 토큰 지정시 토큰타입("Bearer") 붙혀서 호출 예) Bearer Egicyx... |

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
| `gold_daly_trnsn` | 금현물일별추이 LIST N |  |  |  | 금현물일별추이 LIST N |
| `- cur_prc` | 종가 | String | N | 20 | 종가 |
| `- pred_pre` | 전일 대비 | String | N | 20 | 전일 대비 |
| `- flu_rt` | 등락율 | String | N | 20 | 등락율 |
| `- trde_qty` | 누적 거래량 | String | N | 20 | 누적 거래량 |
| `- acc_trde_prica` | 누적 거래대금(백만) | String | N | 20 | 누적 거래대금(백만) |
| `- open_pric` | 시가 | String | N | 20 | 시가 |
| `- high_pric` | 고가 | String | N | 20 | 고가 |
| `- low_pric` | 저가 | String | N | 20 | 저가 |
| `- dt` | 일자 | String | N | 20 | 일자 |

---

## ka50087

**금현물예상체결**

- **메뉴**: 국내주식 > 시세 > 금현물예상체결(ka50087)
- **Method**: `POST`
- **URL**: `/api/dostk/mrkcond`

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
| `stk_cd` | 종목코드 | String | Y | 20 | M04020000 금 99.99_1kg, M04020100 미니금 99.99_100g 토큰 지정시 토큰타입("Bearer") 붙혀서 호출 예) Bearer Egicyx... |

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
| `gold_expt_exec` | 금현물예상체결 LIST N |  |  |  | 금현물예상체결 LIST N |
| `- exp_cntr_pric` | 예상 체결가 | String | N | 20 | 예상 체결가 |
| `- exp_pred_pre` | 예상 체결가 전일대비 | String | N | 20 | 예상 체결가 전일대비 |
| `- exp_flu_rt` | 예상 체결가 등락율 | String | N | 20 | 예상 체결가 등락율 |
| `- exp_acc_trde_qty` | 예상 체결 수량(누적) | String | N | 20 | 예상 체결 수량(누적) |
| `- exp_cntr_trde_qty` | 예상 체결 수량 | String | N | 20 | 예상 체결 수량 |
| `- exp_tm` | 예상 체결 시간 | String | N | 20 | 예상 체결 시간 |
| `- exp_pre_sig` | 예상 체결가 전일대비기호 | String | N | 20 | 예상 체결가 전일대비기호 |
| `- stex_tp` | 거래소 구분 | String | N |  | 거래소 구분 |

---

## ka50100

**금현물 시세정보**

- **메뉴**: 국내주식 > 시세 > 금현물 시세정보(ka50100)
- **Method**: `POST`
- **URL**: `/api/dostk/mrkcond`

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
| `stk_cd` | 종목코드 | String | Y | 20 | 토큰 지정시 토큰타입("Bearer") 붙혀서 호출 예) Bearer Egicyx... |

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
| `pred_pre_sig` | 전일대비기호 | String | N | 20 | 전일대비기호 |
| `pred_pre` | 전일대비 | String | N | 20 | 전일대비 |
| `flu_rt` | 등락율 | String | N | 20 | 등락율 |
| `trde_qty` | 거래량 | String | N | 20 | 거래량 |
| `open_pric` | 시가 | String | N | 20 | 시가 |
| `high_pric` | 고가 | String | N | 20 | 고가 |
| `low_pric` | 저가 | String | N | 20 | 저가 |
| `pred_rt` | 전일비 | String | N | 20 | 전일비 |
| `upl_pric` | 상한가 | String | N | 20 | 상한가 |
| `lst_pric` | 하한가 | String | N | 20 | 하한가 |
| `pred_close_pric` | 전일종가 | String | N | 20 | 전일종가 |

---

## ka50101

**금현물 호가**

- **메뉴**: 국내주식 > 시세 > 금현물 호가(ka50101)
- **Method**: `POST`
- **URL**: `/api/dostk/mrkcond`

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
| `stk_cd` | 종목코드 | String | Y | 20 | M04020000 금 99.99_1kg, M04020100 미니금 99.99_100g |
| `tic_scope` | 틱범위 | String | Y | 2 | 1:1틱, 3:3틱, 5:5틱, 10:10틱, 30:30틱 토큰 지정시 토큰타입("Bearer") 붙혀서 호출 예) Bearer Egicyx... |

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
| `gold_bid` | 금현물호가 LIST N |  |  |  | 금현물호가 LIST N |
| `- cntr_pric` | 체결가 | String | N | 20 | 체결가 |
| `- pred_pre` | 전일 대비(원) | String | N | 20 | 전일 대비(원) |
| `- flu_rt` | 등락율 | String | N | 20 | 등락율 |
| `- trde_qty` | 누적 거래량 | String | N | 20 | 누적 거래량 |
| `- acc_trde_prica` | 누적 거래대금 | String | N | 20 | 누적 거래대금 |
| `- cntr_trde_qty` | 거래량(체결량) | String | N | 20 | 거래량(체결량) |
| `- tm` | 체결시간 | String | N | 20 | 체결시간 |
| `- pre_sig` | 전일대비기호 | String | N | 20 | 전일대비기호 |
| `- pri_sel_bid_unit` | 매도호가 | String | N | 20 | 매도호가 |

---

## ka90005

**프로그램매매추이요청 시간대별**

- **메뉴**: 국내주식 > 시세 > 프로그램매매추이요청 시간대별(ka90005)
- **Method**: `POST`
- **URL**: `/api/dostk/mrkcond`

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
| `date` | 날짜 | String | Y | 8 | YYYYMMDD |
| `amt_qty_tp` | 금액수량구분 | String | Y | 1 | 1:금액(백만원), 2:수량(천주) 토큰 지정시 토큰타입("Bearer") 붙혀서 호출 예) Bearer Egicyx... |
| `mrkt_tp` | 시장구분 | String | Y | 10 | 코스피- 거래소구분값 1일경우:P00101, 2일경우:P001_NX01, 3일경우:P001_AL01 코스닥- 거래소구분값 1일경우:P10102, 2일경우:P101_NX02, 3일경우:P101_AL02 |
| `min_tic_tp` | 분틱구분 | String | Y | 1 | 0:틱, 1:분 |
| `stex_tp` | 거래소구분 | String | Y | 1 | 1:KRX, 2:NXT 3.통합 |

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
| `prm_trde_trnsn` | 프로그램매매추이 LIST N |  |  |  | 프로그램매매추이 LIST N |
| `- cntr_tm` | 체결시간 | String | N | 20 | 체결시간 |
| `- dfrt_trde_sel` | 차익거래매도 | String | N | 20 | 차익거래매도 |
| `- dfrt_trde_buy` | 차익거래매수 | String | N | 20 | 차익거래매수 |
| `- dfrt_trde_netprps` | 차익거래순매수 | String | N | 20 | 차익거래순매수 |
| `- ndiffpro_trde_sel` | 비차익거래매도 | String | N | 20 | 비차익거래매도 |

---

## ka90006

**프로그램매매차익잔고추이요청**

- **메뉴**: 국내주식 > 시세 > 프로그램매매차익잔고추이요청(ka90006)
- **Method**: `POST`
- **URL**: `/api/dostk/mrkcond`

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
| `date` | 날짜 | String | Y | 8 | YYYYMMDD |
| `stex_tp` | 거래소구분 | String | Y | 1 | 1:KRX, 2:NXT 3.통합 토큰 지정시 토큰타입("Bearer") 붙혀서 호출 예) Bearer Egicyx... |

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
| `prm_trde_dfrt_remn_` | trnsn 프로그램매매차익잔 고추이 LIST N |  |  |  | trnsn 프로그램매매차익잔 고추이 LIST N |
| `- dt` | 일자 | String | N | 20 | 일자 |
| `- buy_dfrt_trde_qty` | 매수차익거래수량 | String | N | 20 | 매수차익거래수량 |
| `- buy_dfrt_trde_amt` | 매수차익거래금액 | String | N | 20 | 매수차익거래금액 |
| `- buy_dfrt_trde_irds_` | amt 매수차익거래증감액 | String | N | 20 | amt 매수차익거래증감액 |
| `- sel_dfrt_trde_qty` | 매도차익거래수량 | String | N | 20 | 매도차익거래수량 |
| `- sel_dfrt_trde_amt` | 매도차익거래금액 | String | N | 20 | 매도차익거래금액 |
| `- sel_dfrt_trde_irds_a` | mt 매도차익거래증감액 | String | N | 20 | mt 매도차익거래증감액 |

---

## ka90007

**프로그램매매누적추이요청**

- **메뉴**: 국내주식 > 시세 > 프로그램매매누적추이요청(ka90007)
- **Method**: `POST`
- **URL**: `/api/dostk/mrkcond`

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
| `date` | 날짜 | String | Y | 8 | YYYYMMDD (종료일기준 1년간 데이터만 조회가능) |
| `amt_qty_tp` | 금액수량구분 | String | Y | 1 | 1:금액, 2:수량 |
| `mrkt_tp` | 시장구분 | String | Y | 5 | 0:코스피 , 1:코스닥 |
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
| `prm_trde_acc_trnsn` | 프로그램매매누적추 이 LIST N |  |  |  | 프로그램매매누적추 이 LIST N |
| `- dt` | 일자 | String | N | 20 | 일자 |
| `- kospi200` | KOSPI200 | String | N | 20 | KOSPI200 |
| `- basis` | BASIS | String | N | 20 | BASIS |
| `- dfrt_trde_tdy` | 차익거래당일 | String | N | 20 | 차익거래당일 |
| `- dfrt_trde_acc` | 차익거래누적 | String | N | 20 | 차익거래누적 |
| `- ndiffpro_trde_tdy` | 비차익거래당일 | String | N | 20 | 비차익거래당일 |
| `- ndiffpro_trde_acc` | 비차익거래누적 | String | N | 20 | 비차익거래누적 |

---

## ka90008

**종목시간별프로그램매매추이요청**

- **메뉴**: 국내주식 > 시세 > 종목시간별프로그램매매추이요청(ka90008)
- **Method**: `POST`
- **URL**: `/api/dostk/mrkcond`

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
| `amt_qty_tp` | 금액수량구분 | String | Y | 1 | 1:금액, 2:수량 |
| `stk_cd` | 종목코드 | String | Y | 6 | 거래소별 종목코드 (KRX:039490,NXT:039490_NX,SOR:039490_AL) |
| `date` | 날짜 | String | Y | 8 | YYYYMMDD 토큰 지정시 토큰타입("Bearer") 붙혀서 호출 예) Bearer Egicyx... |

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
| `stk_tm_prm_trde_trn` | sn 종목시간별프로그램 매매추이 LIST N |  |  |  | sn 종목시간별프로그램 매매추이 LIST N |
| `- tm` | 시간 | String | N | 20 | 시간 |
| `- cur_prc` | 현재가 | String | N | 20 | 현재가 |
| `- pre_sig` | 대비기호 | String | N | 20 | 대비기호 |
| `- pred_pre` | 전일대비 | String | N | 20 | 전일대비 |
| `- flu_rt` | 등락율 | String | N | 20 | 등락율 |
| `- trde_qty` | 거래량 | String | N | 20 | 거래량 |
| `- prm_sell_amt` | 프로그램매도금액 | String | N | 20 | 프로그램매도금액 |

---

## ka90010

**프로그램매매추이요청 일자별**

- **메뉴**: 국내주식 > 시세 > 프로그램매매추이요청 일자별(ka90010)
- **Method**: `POST`
- **URL**: `/api/dostk/mrkcond`

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
| `date` | 날짜 | String | Y | 8 | YYYYMMDD |
| `amt_qty_tp` | 금액수량구분 | String | Y | 1 | 1:금액(백만원), 2:수량(천주) 토큰 지정시 토큰타입("Bearer") 붙혀서 호출 예) Bearer Egicyx... |
| `mrkt_tp` | 시장구분 | String | Y | 10 | 코스피- 거래소구분값 1일경우:P00101, 2일경우:P001_NX01, 3일경우:P001_AL01 코스닥- 거래소구분값 1일경우:P10102, 2일경우:P101_NX02, 3일경우:P001_AL02 |
| `min_tic_tp` | 분틱구분 | String | Y | 1 | 0:틱, 1:분 |
| `stex_tp` | 거래소구분 | String | Y | 1 | 1:KRX, 2:NXT 3.통합 |

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
| `prm_trde_trnsn` | 프로그램매매추이 LIST N |  |  |  | 프로그램매매추이 LIST N |
| `- cntr_tm` | 체결시간 | String | N | 20 | 체결시간 |
| `- dfrt_trde_sel` | 차익거래매도 | String | N | 20 | 차익거래매도 |
| `- dfrt_trde_buy` | 차익거래매수 | String | N | 20 | 차익거래매수 |
| `- dfrt_trde_netprps` | 차익거래순매수 | String | N | 20 | 차익거래순매수 |
| `- ndiffpro_trde_sel` | 비차익거래매도 | String | N | 20 | 비차익거래매도 |

---

## ka90013

**종목일별프로그램매매추이요청**

- **메뉴**: 국내주식 > 시세 > 종목일별프로그램매매추이요청(ka90013)
- **Method**: `POST`
- **URL**: `/api/dostk/mrkcond`

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
| `amt_qty_tp` | 금액수량구분 | String | N | 1 | 1:금액, 2:수량 |
| `stk_cd` | 종목코드 | String | Y | 20 | 거래소별 종목코드 (KRX:039490,NXT:039490_NX,SOR:039490_AL) |
| `date` | 날짜 | String | N | 8 | YYYYMMDD 토큰 지정시 토큰타입("Bearer") 붙혀서 호출 예) Bearer Egicyx... |

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
| `stk_daly_prm_trde_tr` | nsn 종목일별프로그램매 매추이 LIST N |  |  |  | nsn 종목일별프로그램매 매추이 LIST N |
| `- dt` | 일자 | String | N | 20 | 일자 |
| `- cur_prc` | 현재가 | String | N | 20 | 현재가 |
| `- pre_sig` | 대비기호 | String | N | 20 | 대비기호 |
| `- pred_pre` | 전일대비 | String | N | 20 | 전일대비 |
| `- flu_rt` | 등락율 | String | N | 20 | 등락율 |
| `- trde_qty` | 거래량 | String | N | 20 | 거래량 |
| `- prm_sell_amt` | 프로그램매도금액 | String | N | 20 | 프로그램매도금액 |

---
