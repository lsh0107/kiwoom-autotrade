# 차트 API

> API 수: 21개

## 목차

- [ka10060 - 종목별투자자기관별차트요청](#ka10060)
- [ka10064 - 장중투자자별매매차트요청](#ka10064)
- [ka10079 - 주식틱차트조회요청](#ka10079)
- [ka10080 - 주식분봉차트조회요청](#ka10080)
- [ka10081 - 주식일봉차트조회요청](#ka10081)
- [ka10082 - 주식주봉차트조회요청](#ka10082)
- [ka10083 - 주식월봉차트조회요청](#ka10083)
- [ka10094 - 주식년봉차트조회요청](#ka10094)
- [ka20004 - 업종틱차트조회요청](#ka20004)
- [ka20005 - 업종분봉조회요청](#ka20005)
- [ka20006 - 업종일봉조회요청](#ka20006)
- [ka20007 - 업종주봉조회요청](#ka20007)
- [ka20008 - 업종월봉조회요청](#ka20008)
- [ka20019 - 업종년봉조회요청](#ka20019)
- [ka50079 - 금현물틱차트조회요청](#ka50079)
- [ka50080 - 금현물분봉차트조회요청](#ka50080)
- [ka50081 - 금현물일봉차트조회요청](#ka50081)
- [ka50082 - 금현물주봉차트조회요청](#ka50082)
- [ka50083 - 금현물월봉차트조회요청](#ka50083)
- [ka50091 - 금현물당일틱차트조회요청](#ka50091)
- [ka50092 - 금현물당일분봉차트조회요청](#ka50092)

---

## ka10060

**종목별투자자기관별차트요청**

- **메뉴**: 국내주식 > 차트 > 종목별투자자기관별차트요청(ka10060)
- **Method**: `POST`
- **URL**: `/api/dostk/chart`

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
| `stk_cd` | 종목코드 | String | Y | 20 | 거래소별 종목코드 (KRX:039490,NXT:039490_NX,SOR:039490_AL) |
| `amt_qty_tp` | 금액수량구분 | String | Y | 1 | 1:금액, 2:수량 |
| `trde_tp` | 매매구분 | String | Y | 1 | 0:순매수, 1:매수, 2:매도 |
| `unit_tp` | 단위구분 | String | Y | 4 | 1000:천주, 1:단주 토큰 지정시 토큰타입("Bearer") 붙혀서 호출 예) Bearer Egicyx... |

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
| `stk_invsr_orgn_chart` | 종목별투자자기관별 차트 LIST N |  |  |  | 종목별투자자기관별 차트 LIST N |
| `- dt` | 일자 | String | N | 20 | 일자 |
| `- cur_prc` | 현재가 | String | N | 20 | 현재가 |
| `- pred_pre` | 전일대비 | String | N | 20 | 전일대비 |
| `- acc_trde_prica` | 누적거래대금 | String | N | 20 | 누적거래대금 |
| `- ind_invsr` | 개인투자자 | String | N | 20 | 개인투자자 |

---

## ka10064

**장중투자자별매매차트요청**

- **메뉴**: 국내주식 > 차트 > 장중투자자별매매차트요청(ka10064)
- **Method**: `POST`
- **URL**: `/api/dostk/chart`

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
| `opmr_invsr_trde_cha` | rt 장중투자자별매매차 트 LIST N |  |  |  | rt 장중투자자별매매차 트 LIST N |
| `- tm` | 시간 | String | N | 20 | 시간 |
| `- frgnr_invsr` | 외국인투자자 | String | N | 20 | 외국인투자자 |
| `- orgn` | 기관계 | String | N | 20 | 기관계 |
| `- invtrt` | 투신 | String | N | 20 | 투신 |
| `- insrnc` | 보험 | String | N | 20 | 보험 |
| `- bank` | 은행 | String | N | 20 | 은행 |

---

## ka10079

**주식틱차트조회요청**

- **메뉴**: 국내주식 > 차트 > 주식틱차트조회요청(ka10079)
- **Method**: `POST`
- **URL**: `/api/dostk/chart`

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
| `tic_scope` | 틱범위 | String | Y | 2 | 1:1틱, 3:3틱, 5:5틱, 10:10틱, 30:30틱 |
| `upd_stkpc_tp` | 수정주가구분 | String | Y | 1 | 0 or 1 토큰 지정시 토큰타입("Bearer") 붙혀서 호출 예) Bearer Egicyx... |

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
| `stk_cd` | 종목코드 | String | N | 6 | 종목코드 |
| `last_tic_cnt` | 마지막틱갯수 | String | N |  | 마지막틱갯수 |
| `stk_tic_chart_qry` | 주식틱차트조회 LIST N |  |  |  | 주식틱차트조회 LIST N |
| `- cur_prc` | 현재가 | String | N | 20 | 현재가 |
| `- trde_qty` | 거래량 | String | N | 20 | 거래량 |
| `- cntr_tm` | 체결시간 | String | N | 20 | 체결시간 |
| `- open_pric` | 시가 | String | N | 20 | 시가 |
| `- high_pric` | 고가 | String | N | 20 | 고가 |
| `- low_pric` | 저가 | String | N | 20 | 저가 |

---

## ka10080

**주식분봉차트조회요청**

- **메뉴**: 국내주식 > 차트 > 주식분봉차트조회요청(ka10080)
- **Method**: `POST`
- **URL**: `/api/dostk/chart`

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
| `tic_scope` | 틱범위 | String | Y | 2 | 1:1분, 3:3분, 5:5분, 10:10분, 15:15분, 30:30분, 45:45분, 60:60분 |
| `upd_stkpc_tp` | 수정주가구분 | String | Y | 1 | 0 or 1 |
| `base_dt` | 기준일자 | String | N | 8 | YYYYMMDD 토큰 지정시 토큰타입("Bearer") 붙혀서 호출 예) Bearer Egicyx... |

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
| `stk_cd` | 종목코드 | String | N | 6 | 종목코드 |
| `stk_min_pole_chart_` | qry 주식분봉차트조회 LIST N |  |  |  | qry 주식분봉차트조회 LIST N |
| `- cur_prc` | 현재가 | String | N | 20 | 현재가 |
| `- trde_qty` | 거래량 | String | N | 20 | 거래량 |
| `- cntr_tm` | 체결시간 | String | N | 20 | 체결시간 |
| `- open_pric` | 시가 | String | N | 20 | 시가 |
| `- high_pric` | 고가 | String | N | 20 | 종가 |

---

## ka10081

**주식일봉차트조회요청**

- **메뉴**: 국내주식 > 차트 > 주식일봉차트조회요청(ka10081)
- **Method**: `POST`
- **URL**: `/api/dostk/chart`

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
| `base_dt` | 기준일자 | String | Y | 8 | YYYYMMDD |
| `upd_stkpc_tp` | 수정주가구분 | String | Y | 1 | 0 or 1 토큰 지정시 토큰타입("Bearer") 붙혀서 호출 예) Bearer Egicyx... |

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
| `stk_cd` | 종목코드 | String | N | 6 | 종목코드 |
| `stk_dt_pole_chart_qr` | y 주식일봉차트조회 LIST N |  |  |  | y 주식일봉차트조회 LIST N |
| `- cur_prc` | 현재가 | String | N | 20 | 현재가 |
| `- trde_qty` | 거래량 | String | N | 20 | 거래량 |
| `- trde_prica` | 거래대금 | String | N | 20 | 거래대금 |
| `- dt` | 일자 | String | N | 20 | 일자 |
| `- open_pric` | 시가 | String | N | 20 | 시가 |
| `- high_pric` | 고가 | String | N | 20 | 고가 |

---

## ka10082

**주식주봉차트조회요청**

- **메뉴**: 국내주식 > 차트 > 주식주봉차트조회요청(ka10082)
- **Method**: `POST`
- **URL**: `/api/dostk/chart`

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
| `base_dt` | 기준일자 | String | Y | 8 | YYYYMMDD |
| `upd_stkpc_tp` | 수정주가구분 | String | Y | 1 | 0 or 1 토큰 지정시 토큰타입("Bearer") 붙혀서 호출 예) Bearer Egicyx... |

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
| `stk_cd` | 종목코드 | String | N | 6 | 종목코드 |
| `stk_stk_pole_chart_qr` | y 주식주봉차트조회 LIST N |  |  |  | y 주식주봉차트조회 LIST N |
| `- cur_prc` | 현재가 | String | N | 20 | 현재가 |
| `- trde_qty` | 거래량 | String | N | 20 | 거래량 |
| `- trde_prica` | 거래대금 | String | N | 20 | 거래대금 |
| `- dt` | 일자 | String | N | 20 | 일자 |
| `- open_pric` | 시가 | String | N | 20 | 시가 |
| `- high_pric` | 고가 | String | N | 20 | 고가 |

---

## ka10083

**주식월봉차트조회요청**

- **메뉴**: 국내주식 > 차트 > 주식월봉차트조회요청(ka10083)
- **Method**: `POST`
- **URL**: `/api/dostk/chart`

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
| `base_dt` | 기준일자 | String | Y | 8 | YYYYMMDD |
| `upd_stkpc_tp` | 수정주가구분 | String | Y | 1 | 0 or 1 토큰 지정시 토큰타입("Bearer") 붙혀서 호출 예) Bearer Egicyx... |

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
| `stk_cd` | 종목코드 | String | N | 6 | 종목코드 |
| `stk_mth_pole_chart_` | qry 주식월봉차트조회 LIST N |  |  |  | qry 주식월봉차트조회 LIST N |
| `- cur_prc` | 현재가 | String | N | 20 | 현재가 |
| `- trde_qty` | 거래량 | String | N | 20 | 거래량 |
| `- trde_prica` | 거래대금 | String | N | 20 | 거래대금 |
| `- dt` | 일자 | String | N | 20 | 일자 |
| `- open_pric` | 시가 | String | N | 20 | 시가 |
| `- high_pric` | 고가 | String | N | 20 | 고가 |

---

## ka10094

**주식년봉차트조회요청**

- **메뉴**: 국내주식 > 차트 > 주식년봉차트조회요청(ka10094)
- **Method**: `POST`
- **URL**: `/api/dostk/chart`

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
| `base_dt` | 기준일자 | String | Y | 8 | YYYYMMDD |
| `upd_stkpc_tp` | 수정주가구분 | String | Y | 1 | 0 or 1 토큰 지정시 토큰타입("Bearer") 붙혀서 호출 예) Bearer Egicyx... |

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
| `stk_cd` | 종목코드 | String | N | 6 | 종목코드 |
| `stk_yr_pole_chart_qr` | y 주식년봉차트조회 LIST N |  |  |  | y 주식년봉차트조회 LIST N |
| `- cur_prc` | 현재가 | String | N | 20 | 현재가 |
| `- trde_qty` | 거래량 | String | N | 20 | 거래량 |
| `- trde_prica` | 거래대금 | String | N | 20 | 거래대금 |
| `- dt` | 일자 | String | N | 20 | 일자 |
| `- open_pric` | 시가 | String | N | 20 | 시가 |
| `- high_pric` | 고가 | String | N | 20 | 고가 |

---

## ka20004

**업종틱차트조회요청**

- **메뉴**: 국내주식 > 차트 > 업종틱차트조회요청(ka20004)
- **Method**: `POST`
- **URL**: `/api/dostk/chart`

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
| `inds_cd` | 업종코드 | String | Y | 3 | 001:종합(KOSPI), 002:대형주, 003:중형주, 004:소형주 101:종합(KOSDAQ), 201:KOSPI200, 302:KOSTAR, 701: KRX100 나머지 ※ 업종코드 참고 |
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
| `inds_cd` | 업종코드 | String | N | 20 | 업종코드 |
| `inds_tic_chart_qry` | 업종틱차트조회 LIST N |  |  |  | 업종틱차트조회 LIST N |
| `- cur_prc` | 현재가 | String | N | 20 | 현재가 |
| `- trde_qty` | 거래량 | String | N | 20 | 거래량 |
| `- cntr_tm` | 체결시간 | String | N | 20 | 체결시간 |
| `- open_pric` | 시가 | String | N | 20 | 지수 값은 소수점 제거 후 100배 값으로 반환 |
| `- high_pric` | 고가 | String | N | 20 | 지수 값은 소수점 제거 후 100배 값으로 반환 |
| `- low_pric` | 저가 | String | N | 20 | 지수 값은 소수점 제거 후 100배 값으로 반환 |
| `- pred_pre` | 전일대비 | String | N | 20 | 현재가 - 전일종가 지수 값은 소수점 제거 후 100배 값으로 반환 |

---

## ka20005

**업종분봉조회요청**

- **메뉴**: 국내주식 > 차트 > 업종분봉조회요청(ka20005)
- **Method**: `POST`
- **URL**: `/api/dostk/chart`

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
| `inds_cd` | 업종코드 | String | Y | 3 | 001:종합(KOSPI), 002:대형주, 003:중형주, 004:소형주 101:종합(KOSDAQ), 201:KOSPI200, 302:KOSTAR, 701: KRX100 나머지 ※ 업종코드 참고 |
| `tic_scope` | 틱범위 | String | Y | 2 | 1:1틱, 3:3틱, 5:5틱, 10:10틱, 30:30틱 |
| `base_dt` | 기준일자 | String | N | 8 | YYYYMMDD 토큰 지정시 토큰타입("Bearer") 붙혀서 호출 예) Bearer Egicyx... |

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
| `inds_cd` | 업종코드 | String | N | 20 | 업종코드 |
| `inds_min_pole_qry` | 업종분봉조회 LIST N |  |  |  | 업종분봉조회 LIST N |
| `- cur_prc` | 현재가 | String | N | 20 | 현재가 |
| `- trde_qty` | 거래량 | String | N | 20 | 거래량 |
| `- cntr_tm` | 체결시간 | String | N | 20 | 체결시간 |
| `- open_pric` | 시가 | String | N | 20 | 지수 값은 소수점 제거 후 100배 값으로 반환 |
| `- high_pric` | 고가 | String | N | 20 | 지수 값은 소수점 제거 후 100배 값으로 반환 |
| `- low_pric` | 저가 | String | N | 20 | 지수 값은 소수점 제거 후 100배 값으로 반환 지수 값은 소수점 제거 후 100배 값으로 반환 |

---

## ka20006

**업종일봉조회요청**

- **메뉴**: 국내주식 > 차트 > 업종일봉조회요청(ka20006)
- **Method**: `POST`
- **URL**: `/api/dostk/chart`

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
| `inds_cd` | 업종코드 | String | Y | 3 | 001:종합(KOSPI), 002:대형주, 003:중형주, 004:소형주 101:종합(KOSDAQ), 201:KOSPI200, 302:KOSTAR, 701: KRX100 나머지 ※ 업종코드 참고 |
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
| `inds_cd` | 업종코드 | String | N | 20 | 업종코드 |
| `inds_dt_pole_qry` | 업종일봉조회 LIST N |  |  |  | 업종일봉조회 LIST N |
| `- cur_prc` | 현재가 | String | N | 20 | 현재가 |
| `- trde_qty` | 거래량 | String | N | 20 | 거래량 |
| `- dt` | 일자 | String | N | 20 | 일자 |
| `- open_pric` | 시가 | String | N | 20 | 지수 값은 소수점 제거 후 100배 값으로 반환 |
| `- high_pric` | 고가 | String | N | 20 | 지수 값은 소수점 제거 후 100배 값으로 반환 |
| `- low_pric` | 저가 | String | N | 20 | 지수 값은 소수점 제거 후 100배 값으로 반환 |
| `- trde_prica` | 거래대금 | String | N | 20 | 지수 값은 소수점 제거 후 100배 값으로 반환 |

---

## ka20007

**업종주봉조회요청**

- **메뉴**: 국내주식 > 차트 > 업종주봉조회요청(ka20007)
- **Method**: `POST`
- **URL**: `/api/dostk/chart`

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
| `inds_cd` | 업종코드 | String | Y | 8 | 001:종합(KOSPI), 002:대형주, 003:중형주, 004:소형주 101:종합(KOSDAQ), 201:KOSPI200, 302:KOSTAR, 701: KRX100 나머지 ※ 업종코드 참고 |
| `base_dt` | 기준일자 | String | Y | 3 | YYYYMMDD 토큰 지정시 토큰타입("Bearer") 붙혀서 호출 예) Bearer Egicyx... |

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
| `inds_cd` | 업종코드 | String | N | 20 | 업종코드 |
| `inds_stk_pole_qry` | 업종주봉조회 LIST N |  |  |  | 업종주봉조회 LIST N |
| `- cur_prc` | 현재가 | String | N | 20 | 현재가 |
| `- trde_qty` | 거래량 | String | N | 20 | 거래량 |
| `- dt` | 일자 | String | N | 20 | 일자 |
| `- open_pric` | 시가 | String | N | 20 | 지수 값은 소수점 제거 후 100배 값으로 반환 |
| `- high_pric` | 고가 | String | N | 20 | 지수 값은 소수점 제거 후 100배 값으로 반환 |
| `- low_pric` | 저가 | String | N | 20 | 지수 값은 소수점 제거 후 100배 값으로 반환 |
| `- trde_prica` | 거래대금 | String | N | 20 | 지수 값은 소수점 제거 후 100배 값으로 반환 |

---

## ka20008

**업종월봉조회요청**

- **메뉴**: 국내주식 > 차트 > 업종월봉조회요청(ka20008)
- **Method**: `POST`
- **URL**: `/api/dostk/chart`

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
| `inds_cd` | 업종코드 | String | Y | 3 | 001:종합(KOSPI), 002:대형주, 003:중형주, 004:소형주 101:종합(KOSDAQ), 201:KOSPI200, 302:KOSTAR, 701: KRX100 나머지 ※ 업종코드 참고 |
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
| `inds_cd` | 업종코드 | String | N | 20 | 업종코드 |
| `inds_mth_pole_qry` | 업종월봉조회 LIST N |  |  |  | 업종월봉조회 LIST N |
| `- cur_prc` | 현재가 | String | N | 20 | 현재가 |
| `- trde_qty` | 거래량 | String | N | 20 | 거래량 |
| `- dt` | 일자 | String | N | 20 | 일자 |
| `- open_pric` | 시가 | String | N | 20 | 지수 값은 소수점 제거 후 100배 값으로 반환 |
| `- high_pric` | 고가 | String | N | 20 | 지수 값은 소수점 제거 후 100배 값으로 반환 |
| `- low_pric` | 저가 | String | N | 20 | 지수 값은 소수점 제거 후 100배 값으로 반환 |
| `- trde_prica` | 거래대금 | String | N | 20 | 지수 값은 소수점 제거 후 100배 값으로 반환 |

---

## ka20019

**업종년봉조회요청**

- **메뉴**: 국내주식 > 차트 > 업종년봉조회요청(ka20019)
- **Method**: `POST`
- **URL**: `/api/dostk/chart`

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
| `inds_cd` | 업종코드 | String | Y | 3 | 001:종합(KOSPI), 002:대형주, 003:중형주, 004:소형주 101:종합(KOSDAQ), 201:KOSPI200, 302:KOSTAR, 701: KRX100 나머지 ※ 업종코드 참고 |
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
| `inds_cd` | 업종코드 | String | N | 20 | 업종코드 |
| `inds_yr_pole_qry` | 업종년봉조회 LIST N |  |  |  | 업종년봉조회 LIST N |
| `- cur_prc` | 현재가 | String | N | 20 | 현재가 |
| `- trde_qty` | 거래량 | String | N | 20 | 거래량 |
| `- dt` | 일자 | String | N | 20 | 일자 |
| `- open_pric` | 시가 | String | N | 20 | 지수 값은 소수점 제거 후 100배 값으로 반환 |
| `- high_pric` | 고가 | String | N | 20 | 지수 값은 소수점 제거 후 100배 값으로 반환 |
| `- low_pric` | 저가 | String | N | 20 | 지수 값은 소수점 제거 후 100배 값으로 반환 |
| `- trde_prica` | 거래대금 | String | N | 20 | 지수 값은 소수점 제거 후 100배 값으로 반환 |

---

## ka50079

**금현물틱차트조회요청**

- **메뉴**: 국내주식 > 차트 > 금현물틱차트조회요청(ka50079)
- **Method**: `POST`
- **URL**: `/api/dostk/chart`

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
| `tic_scope` | 틱범위 | String | Y | 2 | 1:1틱, 3:3틱, 5:5틱, 10:10틱, 30:30틱 |
| `upd_stkpc_tp` | 수정주가구분 | String | Y | 1 | 0 or 1 토큰 지정시 토큰타입("Bearer") 붙혀서 호출 예) Bearer Egicyx... |

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
| `gds_tic_chart_qry` | 금현물틱차트조회 LIST N |  |  |  | 금현물틱차트조회 LIST N |
| `- cur_prc` | 현재가 | String | N | 20 | 현재가 |
| `- pred_pre` | 전일대비 | String | N | 20 | 전일대비 |
| `- trde_qty` | 거래량 | String | N | 20 | 거래량 |
| `- open_pric` | 시가 | String | N | 20 | 시가 |
| `- high_pric` | 고가 | String | N | 20 | 고가 |
| `- low_pric` | 저가 | String | N |  | 저가 |
| `- cntr_tm` | 체결시간 | String | N | 20 | 체결시간 |
| `- dt` | 일자 | String | N | 20 | 일자 |

---

## ka50080

**금현물분봉차트조회요청**

- **메뉴**: 국내주식 > 차트 > 금현물분봉차트조회요청(ka50080)
- **Method**: `POST`
- **URL**: `/api/dostk/chart`

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
| `tic_scope` | 틱범위 | String | Y | 3 | 1:1분, 3:3분, 5:5분, 10:10분, 15:15분, 30:30분, 45:45분, 60:60분 |
| `upd_stkpc_tp` | 수정주가구분 | String | N | 1 | 0 or 1 토큰 지정시 토큰타입("Bearer") 붙혀서 호출 예) Bearer Egicyx... |

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
| `gds_min_chart_qry` | 금현물분봉차트조회 LIST N |  |  |  | 금현물분봉차트조회 LIST N |
| `- cur_prc` | 현재가 | String | N | 20 | 현재가 |
| `- pred_pre` | 전일대비 | String | N | 20 | 전일대비 |
| `- acc_trde_qty` | 누적거래량 | String | N | 20 | 누적거래량 |
| `- trde_qty` | 거래량 | String | N | 20 | 거래량 |
| `- open_pric` | 시가 | String | N | 20 | 시가 |
| `- high_pric` | 고가 | String | N | 20 | 고가 |
| `- low_pric` | 저가 | String | N | 20 | 저가 |
| `- cntr_tm` | 체결시간 | String | N | 20 | 체결시간 |

---

## ka50081

**금현물일봉차트조회요청**

- **메뉴**: 국내주식 > 차트 > 금현물일봉차트조회요청(ka50081)
- **Method**: `POST`
- **URL**: `/api/dostk/chart`

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
| `base_dt` | 기준일자 | String | Y | 8 | YYYYMMDD |
| `upd_stkpc_tp` | 수정주가구분 | String | Y | 1 | 0 or 1 토큰 지정시 토큰타입("Bearer") 붙혀서 호출 예) Bearer Egicyx... |

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
| `gds_day_chart_qry` | 금현물일봉차트조회 LIST N |  |  |  | 금현물일봉차트조회 LIST N |
| `- cur_prc` | 현재가 | String | N | 20 | 현재가 |
| `- acc_trde_qty` | 누적 거래량 | String | N | 20 | 누적 거래량 |
| `- acc_trde_prica` | 누적 거래대금 | String | N | 20 | 누적 거래대금 |
| `- open_pric` | 시가 | String | N | 20 | 시가 |
| `- high_pric` | 고가 | String | N | 20 | 고가 |
| `- low_pric` | 저가 | String | N | 20 | 저가 |
| `- dt` | 일자 | String | N | 20 | 일자 |
| `- pred_pre_sig` | 전일대비기호 | String | N | 20 | 전일대비기호 |

---

## ka50082

**금현물주봉차트조회요청**

- **메뉴**: 국내주식 > 차트 > 금현물주봉차트조회요청(ka50082)
- **Method**: `POST`
- **URL**: `/api/dostk/chart`

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
| `base_dt` | 기준일자 | String | Y | 8 | YYYYMMDD |
| `upd_stkpc_tp` | 수정주가구분 | String | Y | 1 | 0 or 1 토큰 지정시 토큰타입("Bearer") 붙혀서 호출 예) Bearer Egicyx... |

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
| `gds_week_chart_qry` | 금현물일봉차트조회 LIST N |  |  |  | 금현물일봉차트조회 LIST N |
| `- cur_prc` | 현재가 | String | N | 20 | 현재가 |
| `- acc_trde_qty` | 누적 거래량 | String | N | 20 | 누적 거래량 |
| `- acc_trde_prica` | 누적 거래대금 | String | N | 20 | 누적 거래대금 |
| `- open_pric` | 시가 | String | N | 20 | 시가 |
| `- high_pric` | 고가 | String | N | 20 | 고가 |
| `- low_pric` | 저가 | String | N | 20 | 저가 |
| `- dt` | 일자 | String | N | 20 | 일자 |

---

## ka50083

**금현물월봉차트조회요청**

- **메뉴**: 국내주식 > 차트 > 금현물월봉차트조회요청(ka50083)
- **Method**: `POST`
- **URL**: `/api/dostk/chart`

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
| `base_dt` | 기준일자 | String | Y | 8 | YYYYMMDD |
| `upd_stkpc_tp` | 수정주가구분 | String | Y | 1 | 0 or 1 토큰 지정시 토큰타입("Bearer") 붙혀서 호출 예) Bearer Egicyx... |

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
| `gds_month_chart_qr` | y 금현물일봉차트조회 LIST N |  |  |  | y 금현물일봉차트조회 LIST N |
| `- cur_prc` | 현재가 | String | N | 20 | 현재가 |
| `- acc_trde_qty` | 누적 거래량 | String | N | 20 | 누적 거래량 |
| `- acc_trde_prica` | 누적 거래대금 | String | N | 20 | 누적 거래대금 |
| `- open_pric` | 시가 | String | N | 20 | 시가 |
| `- high_pric` | 고가 | String | N | 20 | 고가 |
| `- low_pric` | 저가 | String | N | 20 | 저가 |
| `- dt` | 일자 | String | N | 20 | 일자 |

---

## ka50091

**금현물당일틱차트조회요청**

- **메뉴**: 국내주식 > 차트 > 금현물당일틱차트조회요청(ka50091)
- **Method**: `POST`
- **URL**: `/api/dostk/chart`

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
| `gds_tic_chart_qry` | 금현물일봉차트조회 LIST N |  |  |  | 금현물일봉차트조회 LIST N |
| `- cntr_pric` | 체결가 | String | N | 20 | 체결가 |
| `- pred_pre` | 전일 대비(원) | String | N | 20 | 전일 대비(원) |
| `- trde_qty` | 거래량(체결량) | String | N | 20 | 거래량(체결량) |
| `- open_pric` | 시가 | String | N | 20 | 시가 |
| `- high_pric` | 고가 | String | N | 20 | 고가 |
| `- low_pric` | 저가 | String | N | 20 | 저가 |
| `- cntr_tm` | 체결시간 | String | N | 20 | 체결시간 |
| `- dt` | 일자 | String | N | 20 | 일자 |
| `- pred_pre_sig` | 전일대비기호 | String | N | 20 | 전일대비기호 |

---

## ka50092

**금현물당일분봉차트조회요청**

- **메뉴**: 국내주식 > 차트 > 금현물당일분봉차트조회요청(ka50092)
- **Method**: `POST`
- **URL**: `/api/dostk/chart`

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
| `gds_min_chart_qry` | 금현물일봉차트조회 LIST N |  |  |  | 금현물일봉차트조회 LIST N |
| `- cntr_pric` | 체결가 | String | N | 20 | 체결가 |
| `- pred_pre` | 전일 대비(원) | String | N | 20 | 전일 대비(원) |
| `- acc_trde_qty` | 누적 거래량 | String | N | 20 | 누적 거래량 |
| `- acc_trde_prica` | 누적 거래대금 | String | N | 20 | 누적 거래대금 |
| `- trde_qty` | 거래량(체결량) | String | N | 20 | 거래량(체결량) |
| `- open_pric` | 시가 | String | N | 20 | 시가 |
| `- high_pric` | 고가 | String | N | 20 | 고가 |
| `- low_pric` | 저가 | String | N | 20 | 저가 |
| `- cntr_tm` | 체결시간 | String | N | 20 | 체결시간 |

---

