# 순위정보 API

> API 수: 23개

## 목차

- [ka10020 - 호가잔량상위요청](#ka10020)
- [ka10021 - 호가잔량급증요청](#ka10021)
- [ka10022 - 잔량율급증요청](#ka10022)
- [ka10023 - 거래량급증요청](#ka10023)
- [ka10027 - 전일대비등락률상위요청](#ka10027)
- [ka10029 - 예상체결등락률상위요청](#ka10029)
- [ka10030 - 당일거래량상위요청](#ka10030)
- [ka10031 - 전일거래량상위요청](#ka10031)
- [ka10032 - 거래대금상위요청](#ka10032)
- [ka10033 - 신용비율상위요청](#ka10033)
- [ka10034 - 외인기간별매매상위요청](#ka10034)
- [ka10035 - 외인연속순매매상위요청](#ka10035)
- [ka10036 - 외인한도소진율증가상위](#ka10036)
- [ka10037 - 외국계창구매매상위요청](#ka10037)
- [ka10038 - 종목별증권사순위요청](#ka10038)
- [ka10039 - 증권사별매매상위요청](#ka10039)
- [ka10040 - 당일주요거래원요청](#ka10040)
- [ka10042 - 순매수거래원순위요청](#ka10042)
- [ka10053 - 당일상위이탈원요청](#ka10053)
- [ka10062 - 동일순매매순위요청](#ka10062)
- [ka10065 - 장중투자자별매매상위요청](#ka10065)
- [ka10098 - 시간외단일가등락율순위요청](#ka10098)
- [ka90009 - 외국인기관매매상위요청](#ka90009)

---

## ka10020

**호가잔량상위요청**

- **메뉴**: 국내주식 > 순위정보 > 호가잔량상위요청(ka10020)
- **Method**: `POST`
- **URL**: `/api/dostk/rkinfo`

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
| `mrkt_tp` | 시장구분 | String | Y | 3 | 001:코스피, 101:코스닥 |
| `sort_tp` | 정렬구분 | String | Y | 1 | 1:순매수잔량순, 2:순매도잔량순, 3:매수비율순, 4:매도비율순 |
| `trde_qty_tp` | 거래량구분 | String | Y | 4 | 0000:장시작전(0주이상), 0010:만주이상, 0050:5만주이상, 00100:10만주이상 |
| `stk_cnd` | 종목조건 | String | Y | 1 | 0:전체조회, 1:관리종목제외, 5:증100제외, 6:증100만보기, 7:증40만보기, 8:증30만보기, 9:증20만보기 |
| `crd_cnd` | 신용조건 | String | Y | 1 | 0:전체조회, 1:신용융자A군, 2:신용융자B군, 3:신용융자C군, 4:신용융자D군, 7:신용융자E군, 9:신용융자전체 |
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
| `bid_req_upper` | 호가잔량상위 LIST N |  |  |  | 호가잔량상위 LIST N |
| `- stk_cd` | 종목코드 | String | N | 20 | 종목코드 |
| `- stk_nm` | 종목명 | String | N | 40 | 종목명 |
| `- cur_prc` | 현재가 | String | N | 20 | 현재가 |
| `- pred_pre_sig` | 전일대비기호 | String | N | 20 | 전일대비기호 |

---

## ka10021

**호가잔량급증요청**

- **메뉴**: 국내주식 > 순위정보 > 호가잔량급증요청(ka10021)
- **Method**: `POST`
- **URL**: `/api/dostk/rkinfo`

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
| `mrkt_tp` | 시장구분 | String | Y | 3 | 001:코스피, 101:코스닥 |
| `trde_tp` | 매매구분 | String | Y | 1 | 1:매수잔량, 2:매도잔량 |
| `sort_tp` | 정렬구분 | String | Y | 1 | 1:급증량, 2:급증률 |
| `tm_tp` | 시간구분 | String | Y | 2 | 분 입력 |
| `trde_qty_tp` | 거래량구분 | String | Y | 4 | 1:천주이상, 5:5천주이상, 10:만주이상, 50:5만주이상, 100:10만주이상 |
| `stk_cnd` | 종목조건 | String | Y | 1 | 0:전체조회, 1:관리종목제외, 5:증100제외, 6:증100만보기, 7:증40만보기, 8:증30만보기, 9:증20만보기 |
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
| `bid_req_sdnin` | 호가잔량급증 LIST N |  |  |  | 호가잔량급증 LIST N |
| `- stk_cd` | 종목코드 | String | N | 20 | 종목코드 |
| `- stk_nm` | 종목명 | String | N | 40 | 종목명 |
| `- cur_prc` | 현재가 | String | N | 20 | 현재가 |

---

## ka10022

**잔량율급증요청**

- **메뉴**: 국내주식 > 순위정보 > 잔량율급증요청(ka10022)
- **Method**: `POST`
- **URL**: `/api/dostk/rkinfo`

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
| `mrkt_tp` | 시장구분 | String | Y | 3 | 001:코스피, 101:코스닥 |
| `rt_tp` | 비율구분 | String | Y | 1 | 1:매수/매도비율, 2:매도/매수비율 |
| `tm_tp` | 시간구분 | String | Y | 2 | 분 입력 |
| `trde_qty_tp` | 거래량구분 | String | Y | 1 | 5:5천주이상, 10:만주이상, 50:5만주이상, 100:10만주이상 |
| `stk_cnd` | 종목조건 | String | Y | 1 | 0:전체조회, 1:관리종목제외, 5:증100제외, 6:증100만보기, 7:증40만보기, 8:증30만보기, 9:증20만보기 |
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
| `req_rt_sdnin` | 잔량율급증 LIST N |  |  |  | 잔량율급증 LIST N |
| `- stk_cd` | 종목코드 | String | N | 20 | 종목코드 |
| `- stk_nm` | 종목명 | String | N | 40 | 종목명 |
| `- cur_prc` | 현재가 | String | N | 20 | 현재가 |
| `- pred_pre_sig` | 전일대비기호 | String | N | 20 | 전일대비기호 |
| `- pred_pre` | 전일대비 | String | N | 20 | 전일대비 |

---

## ka10023

**거래량급증요청**

- **메뉴**: 국내주식 > 순위정보 > 거래량급증요청(ka10023)
- **Method**: `POST`
- **URL**: `/api/dostk/rkinfo`

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
| `sort_tp` | 정렬구분 | String | Y | 1 | 1:급증량, 2:급증률, 3:급감량, 4:급감률 |
| `tm_tp` | 시간구분 | String | Y | 1 | 1:분, 2:전일 |
| `trde_qty_tp` | 거래량구분 | String | Y | 1 | 5:5천주이상, 10:만주이상, 50:5만주이상, 100:10만주이상, 200:20만주이상, 300:30만주이상, 500:50만주이상, 1000:백만주이상 |
| `tm` | 시간 | String | N | 2 | 분 입력 토큰 지정시 토큰타입("Bearer") 붙혀서 호출 예) Bearer Egicyx... |
| `stk_cnd` | 종목조건 | String | Y | 1 | 0:전체조회, 1:관리종목제외, 3:우선주제외, 11:정리매매종목제외, 4:관리종목,우선주제외, 5:증100제외, 6:증100만보기, 13:증60만보기, 12:증50만보기, 7:증40만보기, 8:증30만보기, 9:증20만보기, 17:ETN제외, 14:ETF제외, 18:ETF+ETN제외, 15:스팩제외, 20:ETF+ETN+스팩제외 |
| `pric_tp` | 가격구분 | String | Y | 1 | 0:전체조회, 2:5만원이상, 5:1만원이상, 6:5천원이상, 8:1천원이상, 9:10만원이상 |
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
| `trde_qty_sdnin` | 거래량급증 LIST N |  |  |  | 거래량급증 LIST N |

---

## ka10027

**전일대비등락률상위요청**

- **메뉴**: 국내주식 > 순위정보 > 전일대비등락률상위요청(ka10027)
- **Method**: `POST`
- **URL**: `/api/dostk/rkinfo`

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
| `sort_tp` | 정렬구분 | String | Y | 1 | 1:상승률, 2:상승폭, 3:하락률, 4:하락폭, 5:보합 |
| `trde_qty_cnd` | 거래량조건 | String | Y | 5 | 0000:전체조회, 0010:만주이상, 0050:5만주이상, 0100:10만주이상, 0150:15만주이상, 0200:20만주이상, 0300:30만주이상, 0500:50만주이상, 1000:백만주이상 토큰 지정시 토큰타입("Bearer") 붙혀서 호출 예) Bearer Egicyx... |
| `stk_cnd` | 종목조건 | String | Y | 2 | 0:전체조회, 1:관리종목제외, 4:우선주+관리주제외, 3:우선주제외, 5:증100제외, 6:증100만보기, 7:증40만보기, 8:증30만보기, 9:증20만보기, 11:정리매매종목제외, 12:증50만보기, 13:증60만보기, 14:ETF제외, 15:스펙제외, 16:ETF+ETN제외 |
| `crd_cnd` | 신용조건 | String | Y | 1 | 0:전체조회, 1:신용융자A군, 2:신용융자B군, 3:신용융자C군, 4:신용융자D군, 7:신용융자E군, 9:신용융자전체 |
| `updown_incls` | 상하한포함 | String | Y | 2 | 0:불 포함, 1:포함 |
| `pric_cnd` | 가격조건 | String | Y | 2 | 0:전체조회, 1:1천원미만, 2:1천원~2천원, 3:2천원~5천원, 4:5천원~1만원, 5:1만원이상, 8:1천원이상, 10: 1만원미만 |
| `trde_prica_cnd` | 거래대금조건 | String | Y | 4 | 0:전체조회, 3:3천만원이상, 5:5천만원이상, 10:1억원이상, 30:3억원이상, 50:5억원이상, 100:10억원이상, 300:30억원이상, 500:50억원이상, 1000:100억원이상, 3000:300억원이상, 5000:500억원이상 |
| `stex_tp` | 거래소구분 | String | Y | 1 | 1:KRX, 2:NXT 3.통합 |

### Response

**Headers**

| Element | 한글명 | Type | Required | Length | Description |
|---------|--------|------|----------|--------|-------------|
| `api-id` | TR명 Require d | String | Y | 10 | TR명 Require d |

---

## ka10029

**예상체결등락률상위요청**

- **메뉴**: 국내주식 > 순위정보 > 예상체결등락률상위요청(ka10029)
- **Method**: `POST`
- **URL**: `/api/dostk/rkinfo`

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
| `sort_tp` | 정렬구분 | String | Y | 1 | 1:상승률, 2:상승폭, 3:보합, 4:하락률, 5:하락폭, 6:체결량, 7:상한, 8:하한 |
| `trde_qty_cnd` | 거래량조건 | String | Y | 5 | 0:전체조회, 1;천주이상, 3:3천주, 5:5천주, 10:만주이상, 50:5만주이상, 100:10만주이상 토큰 지정시 토큰타입("Bearer") 붙혀서 호출 예) Bearer Egicyx... |
| `stk_cnd` | 종목조건 | String | Y | 2 | 0:전체조회, 1:관리종목제외, 3:우선주제외, 4:관리종목,우선주제외, 5:증100제외, 6:증100만보기, 7:증40만보기, 8:증30만보기, 9:증20만보기, 11:정리매매종목제외, 12:증50만보기, 13:증60만보기, 14:ETF제외, 15:스팩제외, 16:ETF+ETN제외 |
| `crd_cnd` | 신용조건 | String | Y | 1 | 0:전체조회, 1:신용융자A군, 2:신용융자B군, 3:신용융자C군, 4:신용융자D군, 5:신용한도초과제외, 7:신용융자E군, 8:신용대주, 9:신용융자전체 |
| `pric_cnd` | 가격조건 | String | Y | 2 | 0:전체조회, 1:1천원미만, 2:1천원~2천원, 3:2천원~5천원, 4:5천원~1만원, 5:1만원이상, 8:1천원이상, 10:1만원미만 |
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
| `exp_cntr_flu_rt_uppe` | 예상체결등락률상위 LIST N |  |  |  | 예상체결등락률상위 LIST N |

---

## ka10030

**당일거래량상위요청**

- **메뉴**: 국내주식 > 순위정보 > 당일거래량상위요청(ka10030)
- **Method**: `POST`
- **URL**: `/api/dostk/rkinfo`

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
| `sort_tp` | 정렬구분 | String | Y | 1 | 1:거래량, 2:거래회전율, 3:거래대금 토큰 지정시 토큰타입("Bearer") 붙혀서 호출 예) Bearer Egicyx... |
| `mang_stk_incls` | 관리종목포함 | String | Y | 1 | 0:관리종목 포함, 1:관리종목 미포함, 3:우선주제외, 11:정리매매종목제외, 4:관리종목, 우선주제외, 5:증100제외, 6:증100마나보기, 13:증60만보기, 12:증50만보기, 7:증40만보기, 8:증30만보기, 9:증20만보기, 14:ETF제외, 15:스팩제외, 16:ETF+ETN제외 |
| `crd_tp` | 신용구분 | String | Y | 1 | 0:전체조회, 9:신용융자전체, 1:신용융자A군, 2:신용융자B군, 3:신용융자C군, 4:신용융자D군, 8:신용대주 |
| `trde_qty_tp` | 거래량구분 | String | Y | 1 | 0:전체조회, 5:5천주이상, 10:1만주이상, 50:5만주이상, 100:10만주이상, 200:20만주이상, 300:30만주이상, 500:500만주이상, 1000:백만주이상 |
| `pric_tp` | 가격구분 | String | Y | 1 | 0:전체조회, 1:1천원미만, 2:1천원이상, 3:1천원~2천원, 4:2천원~5천원, 5:5천원이상, 6:5천원~1만원, 10:1만원미만, 7:1만원이상, 8:5만원이상, 9:10만원이상 |
| `trde_prica_tp` | 거래대금구분 | String | Y | 1 | 0:전체조회, 1:1천만원이상, 3:3천만원이상, 4:5천만원이상, 10:1억원이상, 30:3억원이상, 50:5억원이상, 100:10억원이상, 300:30억원이상, 500:50억원이상, 1000:100억원이상, 3000:300억원이상, 5000:500억원이상 |
| `mrkt_open_tp` | 장운영구분 | String | Y | 1 | 0:전체조회, 1:장중, 2:장전시간외, 3:장후시간외 |
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
| `tdy_trde_qty_upper` | 당일거래량상위 LIST N |  |  |  | 당일거래량상위 LIST N |
| `- stk_cd` | 종목코드 | String | N | 20 | 종목코드 |
| `- stk_nm` | 종목명 | String | N | 40 | 종목명 |
| `- cur_prc` | 현재가 | String | N | 20 | 현재가 |
| `- pred_pre_sig` | 전일대비기호 | String | N | 20 | 전일대비기호 |
| `- pred_pre` | 전일대비 | String | N | 20 | 전일대비 |
| `- flu_rt` | 등락률 | String | N | 20 | 등락률 |
| `- trde_qty` | 거래량 | String | N | 20 | 거래량 |
| `- pred_rt` | 전일비 | String | N | 20 | 전일비 |
| `- trde_tern_rt` | 거래회전율 | String | N | 20 | 거래회전율 |
| `- trde_amt` | 거래금액 | String | N | 20 | 거래금액 |
| `- opmr_trde_qty` | 장중거래량 | String | N | 20 | 장중거래량 |
| `- opmr_pred_rt` | 장중전일비 | String | N | 20 | 장중전일비 |
| `- opmr_trde_rt` | 장중거래회전율 | String | N | 20 | 장중거래회전율 |
| `- opmr_trde_amt` | 장중거래금액 | String | N | 20 | 장중거래금액 |
| `- af_mkrt_trde_qty` | 장후거래량 | String | N | 20 | 장후거래량 |
| `- af_mkrt_pred_rt` | 장후전일비 | String | N | 20 | 장후전일비 |
| `- af_mkrt_trde_rt` | 장후거래회전율 | String | N | 20 | 장후거래회전율 |
| `- af_mkrt_trde_amt` | 장후거래금액 | String | N | 20 | 장후거래금액 |
| `- bf_mkrt_trde_qty` | 장전거래량 | String | N | 20 | 장전거래량 |
| `- bf_mkrt_pred_rt` | 장전전일비 | String | N | 20 | 장전전일비 |
| `- bf_mkrt_trde_rt` | 장전거래회전율 | String | N | 20 | 장전거래회전율 |
| `- bf_mkrt_trde_amt` | 장전거래금액 | String | N | 20 | 장전거래금액 |

---

## ka10031

**전일거래량상위요청**

- **메뉴**: 국내주식 > 순위정보 > 전일거래량상위요청(ka10031)
- **Method**: `POST`
- **URL**: `/api/dostk/rkinfo`

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
| `qry_tp` | 조회구분 | String | Y | 1 | 1:전일거래량 상위100종목, 2:전일거래대금 상위100종목 |
| `rank_strt` | 순위시작 | String | Y | 3 | 0 ~ 100 값 중에 조회를 원하는 순위 시작값 |
| `rank_end` | 순위끝 | String | Y | 3 | 0 ~ 100 값 중에 조회를 원하는 순위 끝값 |
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
| `pred_trde_qty_upper` | 전일거래량상위 LIST N |  |  |  | 전일거래량상위 LIST N |
| `- stk_cd` | 종목코드 | String | N | 20 | 종목코드 |
| `- stk_nm` | 종목명 | String | N | 40 | 종목명 |
| `- cur_prc` | 현재가 | String | N | 20 | 현재가 |
| `- pred_pre_sig` | 전일대비기호 | String | N | 20 | 전일대비기호 |
| `- pred_pre` | 전일대비 | String | N | 20 | 전일대비 |
| `- trde_qty` | 거래량 | String | N | 20 | 거래량 |

---

## ka10032

**거래대금상위요청**

- **메뉴**: 국내주식 > 순위정보 > 거래대금상위요청(ka10032)
- **Method**: `POST`
- **URL**: `/api/dostk/rkinfo`

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
| `mang_stk_incls` | 관리종목포함 | String | Y | 1 | 0:관리종목 미포함, 1:관리종목 포함 |
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
| `trde_prica_upper` | 거래대금상위 LIST N |  |  |  | 거래대금상위 LIST N |
| `- stk_cd` | 종목코드 | String | N | 20 | 종목코드 |
| `- now_rank` | 현재순위 | String | N | 20 | 현재순위 |
| `- pred_rank` | 전일순위 | String | N | 20 | 전일순위 |
| `- stk_nm` | 종목명 | String | N | 40 | 종목명 |
| `- cur_prc` | 현재가 | String | N | 20 | 현재가 |
| `- pred_pre_sig` | 전일대비기호 | String | N | 20 | 전일대비기호 |
| `- pred_pre` | 전일대비 | String | N | 20 | 전일대비 |
| `- flu_rt` | 등락률 | String | N | 20 | 등락률 |

---

## ka10033

**신용비율상위요청**

- **메뉴**: 국내주식 > 순위정보 > 신용비율상위요청(ka10033)
- **Method**: `POST`
- **URL**: `/api/dostk/rkinfo`

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
| `trde_qty_tp` | 거래량구분 | String | Y | 3 | 0:전체조회, 10:만주이상, 50:5만주이상, 100:10만주이상, 200:20만주이상, 300:30만주이상, 500:50만주이상, 1000:백만주이상 |
| `stk_cnd` | 종목조건 | String | Y | 1 | 0:전체조회, 1:관리종목제외, 5:증100제외, 6:증100만보기, 7:증40만보기, 8:증30만보기, 9:증20만보기 |
| `updown_incls` | 상하한포함 | String | Y | 1 | 0:상하한 미포함, 1:상하한포함 |
| `crd_cnd` | 신용조건 | String | Y | 1 | 0:전체조회, 1:신용융자A군, 2:신용융자B군, 3:신용융자C군, 4:신용융자D군, 7:신용융자E군, 9:신용융자전체 |
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
| `crd_rt_upper` | 신용비율상위 LIST N |  |  |  | 신용비율상위 LIST N |
| `- stk_infr` | 종목정보 | String | N | 20 | 종목정보 |
| `- stk_cd` | 종목코드 | String | N | 20 | 종목코드 |
| `- stk_nm` | 종목명 | String | N | 40 | 종목명 |

---

## ka10034

**외인기간별매매상위요청**

- **메뉴**: 국내주식 > 순위정보 > 외인기간별매매상위요청(ka10034)
- **Method**: `POST`
- **URL**: `/api/dostk/rkinfo`

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
| `trde_tp` | 매매구분 | String | Y | 1 | 1:순매도, 2:순매수, 3:순매매 |
| `dt` | 기간 | String | Y | 2 | 0:당일, 1:전일, 5:5일, 10;10일, 20:20일, 60:60일 |
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
| `for_dt_trde_upper` | 외인기간별매매상위 LIST N |  |  |  | 외인기간별매매상위 LIST N |
| `- rank` | 순위 | String | N | 20 | 순위 |
| `- stk_cd` | 종목코드 | String | N | 20 | 종목코드 |
| `- stk_nm` | 종목명 | String | N | 40 | 종목명 |
| `- cur_prc` | 현재가 | String | N | 20 | 현재가 |
| `- pred_pre_sig` | 전일대비기호 | String | N | 20 | 전일대비기호 |
| `- pred_pre` | 전일대비 | String | N | 20 | 전일대비 |
| `- sel_bid` | 매도호가 | String | N | 20 | 매도호가 |

---

## ka10035

**외인연속순매매상위요청**

- **메뉴**: 국내주식 > 순위정보 > 외인연속순매매상위요청(ka10035)
- **Method**: `POST`
- **URL**: `/api/dostk/rkinfo`

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
| `trde_tp` | 매매구분 | String | Y | 1 | 1:연속순매도, 2:연속순매수 |
| `base_dt_tp` | 기준일구분 | String | Y | 1 | 0:당일기준, 1:전일기준 |
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
| `for_cont_nettrde_up` | per 외인연속순매매상위 LIST N |  |  |  | per 외인연속순매매상위 LIST N |
| `- stk_cd` | 종목코드 | String | N | 20 | 종목코드 |
| `- stk_nm` | 종목명 | String | N | 40 | 종목명 |
| `- cur_prc` | 현재가 | String | N | 20 | 현재가 |
| `- pred_pre_sig` | 전일대비기호 | String | N | 20 | 전일대비기호 |
| `- pred_pre` | 전일대비 | String | N | 20 | 전일대비 |
| `- dm1` | D-1 | String | N | 20 | D-1 |
| `- dm2` | D-2 | String | N | 20 | D-2 |

---

## ka10036

**외인한도소진율증가상위**

- **메뉴**: 국내주식 > 순위정보 > 외인한도소진율증가상위(ka10036)
- **Method**: `POST`
- **URL**: `/api/dostk/rkinfo`

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
| `dt` | 기간 | String | Y | 2 | 0:당일, 1:전일, 5:5일, 10;10일, 20:20일, 60:60일 |
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
| `for_limit_exh_rt_incrs` | _upper 외인한도소진율증가 상위 LIST N |  |  |  | _upper 외인한도소진율증가 상위 LIST N |
| `- rank` | 순위 | String | N | 20 | 순위 |
| `- stk_cd` | 종목코드 | String | N | 20 | 종목코드 |
| `- stk_nm` | 종목명 | String | N | 40 | 종목명 |
| `- cur_prc` | 현재가 | String | N | 20 | 현재가 |
| `- pred_pre_sig` | 전일대비기호 | String | N | 20 | 전일대비기호 |
| `- pred_pre` | 전일대비 | String | N | 20 | 전일대비 |
| `- trde_qty` | 거래량 | String | N | 20 | 거래량 |
| `- poss_stkcnt` | 보유주식수 | String | N | 20 | 보유주식수 |

---

## ka10037

**외국계창구매매상위요청**

- **메뉴**: 국내주식 > 순위정보 > 외국계창구매매상위요청(ka10037)
- **Method**: `POST`
- **URL**: `/api/dostk/rkinfo`

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
| `dt` | 기간 | String | Y | 2 | 0:당일, 1:전일, 5:5일, 10;10일, 20:20일, 60:60일 |
| `trde_tp` | 매매구분 | String | Y | 1 | 1:순매수, 2:순매도, 3:매수, 4:매도 |
| `sort_tp` | 정렬구분 | String | Y | 1 | 1:금액, 2:수량 |
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
| `frgn_wicket_trde_up` | per 외국계창구매매상위 LIST N |  |  |  | per 외국계창구매매상위 LIST N |
| `- rank` | 순위 | String | N | 20 | 순위 |
| `- stk_cd` | 종목코드 | String | N | 20 | 종목코드 |
| `- stk_nm` | 종목명 | String | N | 40 | 종목명 |
| `- cur_prc` | 현재가 | String | N | 20 | 현재가 |
| `- pred_pre_sig` | 전일대비기호 | String | N | 20 | 전일대비기호 |
| `- pred_pre` | 전일대비 | String | N | 20 | 전일대비 |

---

## ka10038

**종목별증권사순위요청**

- **메뉴**: 국내주식 > 순위정보 > 종목별증권사순위요청(ka10038)
- **Method**: `POST`
- **URL**: `/api/dostk/rkinfo`

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
| `stk_cd` | 종목코드 | String | Y | 6 | 거래소별 종목코드 (KRX:039490,NXT:039490_NX,SOR:039490_AL) |
| `strt_dt` | 시작일자 | String | N | 8 | YYYYMMDD (연도4자리, 월 2자리, 일 2자리 형식) |
| `end_dt` | 종료일자 | String | N | 8 | YYYYMMDD (연도4자리, 월 2자리, 일 2자리 형식) |
| `qry_tp` | 조회구분 | String | Y | 1 | 1:순매도순위정렬, 2:순매수순위정렬 |
| `dt` | 기간 | String | N | 2 | 1:전일, 4:5일, 9:10일, 19:20일, 39:40일, 59:60일, 119:120일 토큰 지정시 토큰타입("Bearer") 붙혀서 호출 예) Bearer Egicyx... |

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
| `rank_1` | 순위1 | String | N | 20 | 순위1 |
| `rank_2` | 순위2 | String | N | 20 | 순위2 |
| `rank_3` | 순위3 | String | N | 20 | 순위3 |
| `prid_trde_qty` | 기간중거래량 | String | N | 20 | 기간중거래량 |
| `stk_sec_rank` | 종목별증권사순위 LIST N |  |  |  | 종목별증권사순위 LIST N |
| `- rank` | 순위 | String | N | 20 | 순위 |

---

## ka10039

**증권사별매매상위요청**

- **메뉴**: 국내주식 > 순위정보 > 증권사별매매상위요청(ka10039)
- **Method**: `POST`
- **URL**: `/api/dostk/rkinfo`

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
| `trde_qty_tp` | 거래량구분 | String | Y | 4 | 0:전체, 5:5000주, 10:1만주, 50:5만주, 100:10만주, 500:50만주, 1000: 100만주 |
| `trde_tp` | 매매구분 | String | Y | 2 | 1:순매수, 2:순매도 |
| `dt` | 기간 | String | Y | 2 | 1:전일, 5:5일, 10:10일, 60:60일 |
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
| `sec_trde_upper` | 증권사별매매상위 LIST N |  |  |  | 증권사별매매상위 LIST N |
| `- rank` | 순위 | String | N | 20 | 순위 |
| `- stk_cd` | 종목코드 | String | N | 20 | 종목코드 |
| `- stk_nm` | 종목명 | String | N | 40 | 종목명 |
| `- prid_stkpc_flu` | 기간중주가등락 | String | N | 20 | 기간중주가등락 |
| `- flu_rt` | 등락율 | String | N | 20 | 등락율 |
| `- prid_trde_qty` | 기간중거래량 | String | N | 20 | 기간중거래량 |

---

## ka10040

**당일주요거래원요청**

- **메뉴**: 국내주식 > 순위정보 > 당일주요거래원요청(ka10040)
- **Method**: `POST`
- **URL**: `/api/dostk/rkinfo`

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
| `sel_trde_ori_irds_1` | 매도거래원별증감1 | String | N |  | 매도거래원별증감1 |
| `sel_trde_ori_qty_1` | 매도거래원수량1 | String | N |  | 매도거래원수량1 |
| `sel_trde_ori_1` | 매도거래원1 | String | N |  | 매도거래원1 |
| `sel_trde_ori_cd_1` | 매도거래원코드1 | String | N |  | 매도거래원코드1 |
| `buy_trde_ori_1` | 매수거래원1 | String | N |  | 매수거래원1 |
| `buy_trde_ori_cd_1` | 매수거래원코드1 | String | N |  | 매수거래원코드1 |
| `buy_trde_ori_qty_1` | 매수거래원수량1 | String | N |  | 매수거래원수량1 |
| `buy_trde_ori_irds_1` | 매수거래원별증감1 | String | N |  | 매수거래원별증감1 |
| `sel_trde_ori_irds_2` | 매도거래원별증감2 | String | N |  | 매도거래원별증감2 |
| `sel_trde_ori_qty_2` | 매도거래원수량2 | String | N |  | 매도거래원수량2 |
| `sel_trde_ori_2` | 매도거래원2 | String | N |  | 매도거래원2 |

---

## ka10042

**순매수거래원순위요청**

- **메뉴**: 국내주식 > 순위정보 > 순매수거래원순위요청(ka10042)
- **Method**: `POST`
- **URL**: `/api/dostk/rkinfo`

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
| `stk_cd` | 종목코드 | String | Y | 6 | 거래소별 종목코드 (KRX:039490,NXT:039490_NX,SOR:039490_AL) |
| `strt_dt` | 시작일자 | String | N | 8 | YYYYMMDD (연도4자리, 월 2자리, 일 2자리 형식) |
| `end_dt` | 종료일자 | String | N | 8 | YYYYMMDD (연도4자리, 월 2자리, 일 2자리 형식) |
| `qry_dt_tp` | 조회기간구분 | String | Y | 1 | 0:기간으로 조회, 1:시작일자, 종료일자로 조회 |
| `pot_tp` | 시점구분 | String | Y | 1 | 0:당일, 1:전일 |
| `dt` | 기간 | String | N | 4 | 5:5일, 10:10일, 20:20일, 40:40일, 60:60일, 120:120일 |
| `sort_base` | 정렬기준 | String | Y | 1 | 1:종가순, 2:날짜순 토큰 지정시 토큰타입("Bearer") 붙혀서 호출 예) Bearer Egicyx... |

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
| `netprps_trde_ori_ran` | k 순매수거래원순위 LIST N |  |  |  | k 순매수거래원순위 LIST N |
| `- rank` | 순위 | String | N | 20 | 순위 |
| `- mmcm_cd` | 회원사코드 | String | N | 20 | 회원사코드 |

---

## ka10053

**당일상위이탈원요청**

- **메뉴**: 국내주식 > 순위정보 > 당일상위이탈원요청(ka10053)
- **Method**: `POST`
- **URL**: `/api/dostk/rkinfo`

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
| `tdy_upper_scesn_ori` | 당일상위이탈원 LIST N |  |  |  | 당일상위이탈원 LIST N |
| `- sel_scesn_tm` | 매도이탈시간 | String | N | 20 | 매도이탈시간 |
| `- sell_qty` | 매도수량 | String | N | 20 | 매도수량 |
| `sel_upper_scesn_ori` | 매도상위이탈원 | String | N | 20 | 매도상위이탈원 |
| `- buy_scesn_tm` | 매수이탈시간 | String | N | 20 | 매수이탈시간 |
| `- buy_qty` | 매수수량 | String | N | 20 | 매수수량 |
| `buy_upper_scesn_ori` | 매수상위이탈원 | String | N | 20 | 매수상위이탈원 |
| `- qry_dt` | 조회일자 | String | N | 20 | 조회일자 |
| `- qry_tm` | 조회시간 | String | N | 20 | 조회시간 |

---

## ka10062

**동일순매매순위요청**

- **메뉴**: 국내주식 > 순위정보 > 동일순매매순위요청(ka10062)
- **Method**: `POST`
- **URL**: `/api/dostk/rkinfo`

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
| `mrkt_tp` | 시장구분 | String | Y | 3 | 000:전체, 001: 코스피, 101:코스닥 |
| `trde_tp` | 매매구분 | String | Y | 1 | 1:순매수, 2:순매도 |
| `sort_cnd` | 정렬조건 | String | Y | 1 | 1:수량, 2:금액 |
| `unit_tp` | 단위구분 | String | Y | 1 | 1:단주, 1000:천주 |
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
| `eql_nettrde_rank` | 동일순매매순위 LIST N |  |  |  | 동일순매매순위 LIST N |
| `- stk_cd` | 종목코드 | String | N | 20 | 종목코드 |
| `- rank` | 순위 | String | N | 20 | 순위 |
| `- stk_nm` | 종목명 | String | N | 40 | 종목명 |

---

## ka10065

**장중투자자별매매상위요청**

- **메뉴**: 국내주식 > 순위정보 > 장중투자자별매매상위요청(ka10065)
- **Method**: `POST`
- **URL**: `/api/dostk/rkinfo`

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
| `trde_tp` | 매매구분 | String | Y | 1 | 1:순매수, 2:순매도 |
| `mrkt_tp` | 시장구분 | String | Y | 3 | 000:전체, 001:코스피, 101:코스닥 |
| `orgn_tp` | 기관구분 | String | Y | 4 | 9000:외국인, 9100:외국계, 1000:금융투자, 3000:투신, 5000:기타금융, 4000:은행, 2000:보험, 6000:연기금, 7000:국가, 7100:기타법인, 9999:기관계 토큰 지정시 토큰타입("Bearer") 붙혀서 호출 예) Bearer Egicyx... |

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
| `opmr_invsr_trde_upp` | er 장중투자자별매매상 위 LIST N |  |  |  | er 장중투자자별매매상 위 LIST N |
| `- stk_cd` | 종목코드 | String | N | 20 | 종목코드 |
| `- stk_nm` | 종목명 | String | N | 40 | 종목명 |
| `- sel_qty` | 매도량 | String | N | 20 | 매도량 |
| `- buy_qty` | 매수량 | String | N | 20 | 매수량 |
| `- netslmt` | 순매도 | String | N | 20 | 순매도 |

---

## ka10098

**시간외단일가등락율순위요청**

- **메뉴**: 국내주식 > 순위정보 > 시간외단일가등락율순위요청(ka10098)
- **Method**: `POST`
- **URL**: `/api/dostk/rkinfo`

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
| `mrkt_tp` | 시장구분 | String | Y | 3 | 000:전체,001:코스피,101:코스닥 |
| `sort_base` | 정렬기준 | String | Y | 1 | 1:상승률, 2:상승폭, 3:하락률, 4:하락폭, 5:보합 토큰 지정시 토큰타입("Bearer") 붙혀서 호출 예) Bearer Egicyx... |
| `stk_cnd` | 종목조건 | String | Y | 2 | 0:전체조회,1:관리종목제외,2:정리매매종목제외,3:우선주제외, 4:관리종목우선주제외,5:증100제외,6:증100만보기,7:증40만보 기,8:증30만보기,9:증20만보기,12:증50만보기,13:증60만보기, 14:ETF제외,15:스팩제외,16:ETF+ETN제외,17:ETN제외 |
| `trde_qty_cnd` | 거래량조건 | String | Y | 5 | 0:전체조회, 10:백주이상,50:5백주이상,100;천주이상, 500:5천주이상, 1000:만주이상, 5000:5만주이상, 10000:10만주이상 |
| `crd_cnd` | 신용조건 | String | Y | 1 | 0:전체조회, 9:신용융자전체, 1:신용융자A군, 2:신용융자B군, 3:신용융자C군, 4:신용융자D군, 7:신용융자E군, 8:신용대주, 5:신용한도초과제외 |
| `trde_prica` | 거래대금 | String | Y | 5 | 0:전체조회, 5:5백만원이상,10:1천만원이상, 30:3천만원이상, 50:5천만원이상, 100:1억원이상, 300:3억원이상, 500:5억원이상, 1000:10억원이상, 3000:30억원이상, 5000:50억원이상, 10000:100억원이상 |

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
| `ovt_sigpric_flu_rt_ran` | k 시간외단일가등락율 순위 LIST N |  |  |  | k 시간외단일가등락율 순위 LIST N |

---

## ka90009

**외국인기관매매상위요청**

- **메뉴**: 국내주식 > 순위정보 > 외국인기관매매상위요청(ka90009)
- **Method**: `POST`
- **URL**: `/api/dostk/rkinfo`

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
| `amt_qty_tp` | 금액수량구분 | String | Y | 1 | 1:금액(천만), 2:수량(천) |
| `qry_dt_tp` | 조회일자구분 | String | Y | 1 | 0:조회일자 미포함, 1:조회일자 포함 |
| `date` | 날짜 | String | N | 8 | YYYYMMDD (연도4자리, 월 2자리, 일 2자리 형식) |
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
| `frgnr_orgn_trde_upp` | er 외국인기관매매상위 LIST N |  |  |  | er 외국인기관매매상위 LIST N |
| `- for_netslmt_stk_cd` | 외인순매도종목코드 | String | N | 20 | 외인순매도종목코드 |
| `- for_netslmt_stk_nm` | 외인순매도종목명 | String | N | 20 | 외인순매도종목명 |
| `- for_netslmt_amt` | 외인순매도금액 | String | N | 20 | 외인순매도금액 |
| `- for_netslmt_qty` | 외인순매도수량 | String | N | 20 | 외인순매도수량 |
| `- for_netprps_stk_cd` | 외인순매수종목코드 | String | N | 20 | 외인순매수종목코드 |

---

