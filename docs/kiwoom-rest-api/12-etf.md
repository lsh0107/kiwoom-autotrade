# ETF API

> API 수: 9개

## 목차

- [ka40001 - ETF수익율요청](#ka40001)
- [ka40002 - ETF종목정보요청](#ka40002)
- [ka40003 - ETF일별추이요청](#ka40003)
- [ka40004 - ETF전체시세요청](#ka40004)
- [ka40006 - ETF시간대별추이요청](#ka40006)
- [ka40007 - ETF시간대별체결요청](#ka40007)
- [ka40008 - ETF일자별체결요청](#ka40008)
- [ka40009 - ETF시간대별체결요청](#ka40009)
- [ka40010 - ETF시간대별추이요청](#ka40010)

---

## ka40001

**ETF수익율요청**

- **메뉴**: 국내주식 > ETF > ETF수익율요청(ka40001)
- **Method**: `POST`
- **URL**: `/api/dostk/etf`

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
| `stk_cd` | 종목코드 | String | Y | 6 | 종목코드 |
| `etfobjt_idex_cd` | ETF대상지수코드 | String | Y | 3 | ETF대상지수코드 |
| `dt` | 기간 | String | Y | 1 | 토큰 지정시 토큰타입("Bearer") 붙혀서 호출 예) Bearer Egicyx... 0:1주, 1:1달, 2:6개월, 3:1년 |

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
| `etfprft_rt_lst` | ETF수익율 LIST N |  |  |  | ETF수익율 LIST N |
| `- etfprft_rt` | ETF수익률 | String | N | 20 | ETF수익률 |
| `- cntr_prft_rt` | 체결수익률 | String | N | 20 | 체결수익률 |
| `- for_netprps_qty` | 외인순매수수량 | String | N | 20 | 외인순매수수량 |
| `- orgn_netprps_qty` | 기관순매수수량 | String | N | 20 | 기관순매수수량 |

---

## ka40002

**ETF종목정보요청**

- **메뉴**: 국내주식 > ETF > ETF종목정보요청(ka40002)
- **Method**: `POST`
- **URL**: `/api/dostk/etf`

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
| `stk_nm` | 종목명 | String | N | 40 | 종목명 |
| `etfobjt_idex_nm` | ETF대상지수명 | String | N | 20 | ETF대상지수명 |
| `wonju_pric` | 원주가격 | String | N | 20 | 원주가격 |
| `etftxon_type` | ETF과세유형 | String | N | 20 | ETF과세유형 |
| `etntxon_type` | ETN과세유형 | String | N | 20 | ETN과세유형 |

---

## ka40003

**ETF일별추이요청**

- **메뉴**: 국내주식 > ETF > ETF일별추이요청(ka40003)
- **Method**: `POST`
- **URL**: `/api/dostk/etf`

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
| `etfdaly_trnsn` | ETF일별추이 LIST N |  |  |  | ETF일별추이 LIST N |
| `- cntr_dt` | 체결일자 | String | N | 20 | 체결일자 |
| `- cur_prc` | 현재가 | String | N | 20 | 현재가 |
| `- pre_sig` | 대비기호 | String | N | 20 | 대비기호 |
| `- pred_pre` | 전일대비 | String | N | 20 | 전일대비 |
| `- pre_rt` | 대비율 | String | N | 20 | 대비율 |
| `- trde_qty` | 거래량 | String | N | 20 | 거래량 |
| `- nav` | NAV | String | N | 20 | NAV |
| `- acc_trde_prica` | 누적거래대금 | String | N | 20 | 누적거래대금 |
| `- navidex_dispty_rt` | NAV/지수괴리율 | String | N | 20 | NAV/지수괴리율 |
| `- navetfdispty_rt` | NAV/ETF괴리율 | String | N | 20 | NAV/ETF괴리율 |

---

## ka40004

**ETF전체시세요청**

- **메뉴**: 국내주식 > ETF > ETF전체시세요청(ka40004)
- **Method**: `POST`
- **URL**: `/api/dostk/etf`

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
| `txon_type` | 과세유형 | String | Y | 1 | 0:전체, 1:비과세, 2:보유기간과세, 3:회사형, 4:외국, 5:비과세해외(보유기간관세) |
| `navpre` | NAV대비 | String | Y | 1 | 0:전체, 1:NAV > 전일종가, 2:NAV < 전일종가 |
| `mngmcomp` | 운용사 | String | Y | 4 | 0000:전체, 3020:KODEX(삼성), 3027:KOSEF(키움), 3191:TIGER(미래에셋), 3228:KINDEX(한국투자), 3023:KStar(KB), 3022:아리랑(한화), 9999:기타운용사 |
| `txon_yn` | 과세여부 | String | Y | 1 | 0:전체, 1:과세, 2:비과세 |
| `trace_idex` | 추적지수 | String | Y | 1 | 0:전체 |
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
| `etfall_mrpr` | ETF전체시세 LIST N |  |  |  | ETF전체시세 LIST N |
| `- stk_cd` | 종목코드 | String | N | 20 | 종목코드 |
| `- stk_cls` | 종목분류 | String | N | 20 | 종목분류 |
| `- stk_nm` | 종목명 | String | N | 40 | 종목명 |
| `- close_pric` | 종가 | String | N | 20 | 종가 |

---

## ka40006

**ETF시간대별추이요청**

- **메뉴**: 국내주식 > ETF > ETF시간대별추이요청(ka40006)
- **Method**: `POST`
- **URL**: `/api/dostk/etf`

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
| `stk_nm` | 종목명 | String | N | 40 | 종목명 |
| `etfobjt_idex_nm` | ETF대상지수명 | String | N | 20 | ETF대상지수명 |
| `wonju_pric` | 원주가격 | String | N | 20 | 원주가격 |
| `etftxon_type` | ETF과세유형 | String | N | 20 | ETF과세유형 |
| `etntxon_type` | ETN과세유형 | String | N | 20 | ETN과세유형 |
| `etftisl_trnsn` | ETF시간대별추이 LIST N |  |  |  | ETF시간대별추이 LIST N |
| `- tm` | 시간 | String | N | 20 | 시간 |
| `- close_pric` | 종가 | String | N | 20 | 종가 |
| `- pre_sig` | 대비기호 | String | N | 20 | 대비기호 |
| `- pred_pre` | 전일대비 | String | N | 20 | 전일대비 |
| `- flu_rt` | 등락율 | String | N | 20 | 등락율 |

---

## ka40007

**ETF시간대별체결요청**

- **메뉴**: 국내주식 > ETF > ETF시간대별체결요청(ka40007)
- **Method**: `POST`
- **URL**: `/api/dostk/etf`

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
| `stk_cls` | 종목분류 | String | N | 20 | 종목분류 |
| `stk_nm` | 종목명 | String | N | 40 | 종목명 |
| `etfobjt_idex_nm` | ETF대상지수명 | String | N | 20 | ETF대상지수명 |
| `etfobjt_idex_cd` | ETF대상지수코드 | String | N | 20 | ETF대상지수코드 |
| `objt_idex_pre_rt` | 대상지수대비율 | String | N | 20 | 대상지수대비율 |
| `wonju_pric` | 원주가격 | String | N | 20 | 원주가격 |
| `etftisl_cntr_array` | ETF시간대별체결배 열 LIST N |  |  |  | ETF시간대별체결배 열 LIST N |
| `- cntr_tm` | 체결시간 | String | N | 20 | 체결시간 |
| `- cur_prc` | 현재가 | String | N | 20 | 현재가 |
| `- pre_sig` | 대비기호 | String | N | 20 | 대비기호 |
| `- pred_pre` | 전일대비 | String | N | 20 | 전일대비 |

---

## ka40008

**ETF일자별체결요청**

- **메뉴**: 국내주식 > ETF > ETF일자별체결요청(ka40008)
- **Method**: `POST`
- **URL**: `/api/dostk/etf`

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
| `cntr_tm` | 체결시간 | String | N | 20 | 체결시간 |
| `cur_prc` | 현재가 | String | N | 20 | 현재가 |
| `pre_sig` | 대비기호 | String | N | 20 | 대비기호 |
| `pred_pre` | 전일대비 | String | N | 20 | 전일대비 |
| `trde_qty` | 거래량 | String | N | 20 | 거래량 |
| `etfnetprps_qty_array` | ETF순매수수량배열 LIST N |  |  |  | ETF순매수수량배열 LIST N |
| `- dt` | 일자 | String | N | 20 | 일자 |
| `- cur_prc_n` | 현재가n | String | N | 20 | 현재가n |
| `- pre_sig_n` | 대비기호n | String | N | 20 | 대비기호n |
| `- pred_pre_n` | 전일대비n | String | N | 20 | 전일대비n |
| `- acc_trde_qty` | 누적거래량 | String | N | 20 | 누적거래량 |

---

## ka40009

**ETF시간대별체결요청**

- **메뉴**: 국내주식 > ETF > ETF시간대별체결요청(ka40009)
- **Method**: `POST`
- **URL**: `/api/dostk/etf`

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
| `etfnavarray` | ETFNAV배열 LIST N |  |  |  | ETFNAV배열 LIST N |
| `- nav` | NAV | String | N | 20 | NAV |
| `- navpred_pre` | NAV전일대비 | String | N | 20 | NAV전일대비 |
| `- navflu_rt` | NAV등락율 | String | N | 20 | NAV등락율 |
| `- trace_eor_rt` | 추적오차율 | String | N | 20 | 추적오차율 |
| `- dispty_rt` | 괴리율 | String | N | 20 | 괴리율 |
| `- stkcnt` | 주식수 | String | N | 20 | 주식수 |
| `- base_pric` | 기준가 | String | N | 20 | 기준가 |
| `- for_rmnd_qty` | 외인보유수량 | String | N | 20 | 외인보유수량 |
| `- repl_pric` | 대용가 | String | N | 20 | 대용가 |
| `- conv_pric` | 환산가격 | String | N | 20 | 환산가격 |

---

## ka40010

**ETF시간대별추이요청**

- **메뉴**: 국내주식 > ETF > ETF시간대별추이요청(ka40010)
- **Method**: `POST`
- **URL**: `/api/dostk/etf`

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
| `etftisl_trnsn` | ETF시간대별추이 LIST N |  |  |  | ETF시간대별추이 LIST N |
| `- cur_prc` | 현재가 | String | N | 20 | 현재가 |
| `- pre_sig` | 대비기호 | String | N | 20 | 대비기호 |
| `- pred_pre` | 전일대비 | String | N | 20 | 전일대비 |
| `- trde_qty` | 거래량 | String | N | 20 | 거래량 |
| `- for_netprps` | 외인순매수 | String | N | 20 | 외인순매수 |

---

