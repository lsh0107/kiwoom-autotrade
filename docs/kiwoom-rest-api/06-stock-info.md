# 종목정보 API

> API 수: 31개

## 목차

- [ka00198 - 실시간종목조회순위](#ka00198)
- [ka10001 - 주식기본정보요청](#ka10001)
- [ka10002 - 주식거래원요청](#ka10002)
- [ka10003 - 체결정보요청](#ka10003)
- [ka10013 - 신용매매동향요청](#ka10013)
- [ka10015 - 일별거래상세요청](#ka10015)
- [ka10016 - 신고저가요청](#ka10016)
- [ka10017 - 상하한가요청](#ka10017)
- [ka10018 - 고저가근접요청](#ka10018)
- [ka10019 - 가격급등락요청](#ka10019)
- [ka10024 - 거래량갱신요청](#ka10024)
- [ka10025 - 매물대집중요청](#ka10025)
- [ka10026 - 고저PER요청](#ka10026)
- [ka10028 - 시가대비등락률요청](#ka10028)
- [ka10043 - 거래원매물대분석요청](#ka10043)
- [ka10052 - 거래원순간거래량요청](#ka10052)
- [ka10054 - 변동성완화장치발동종목요청](#ka10054)
- [ka10055 - 당일전일체결량요청](#ka10055)
- [ka10058 - 투자자별일별매매종목요청](#ka10058)
- [ka10059 - 종목별투자자기관별요청](#ka10059)
- [ka10061 - 종목별투자자기관별합계요청](#ka10061)
- [ka10084 - 당일전일체결요청](#ka10084)
- [ka10095 - 관심종목정보요청](#ka10095)
- [ka10099 - 종목정보 리스트](#ka10099)
- [ka10100 - 종목정보 조회](#ka10100)
- [ka10101 - 업종코드 리스트](#ka10101)
- [ka10102 - 회원사 리스트](#ka10102)
- [ka90003 - 프로그램순매수상위50요청](#ka90003)
- [ka90004 - 종목별프로그램매매현황요청](#ka90004)
- [kt20016 - 신용융자 가능종목요청](#kt20016)
- [kt20017 - 신용융자 가능문의](#kt20017)

---

## ka00198

**실시간종목조회순위**

- **메뉴**: 국내주식 > 종목정보 > 실시간종목조회순위(ka00198)
- **Method**: `POST`
- **URL**: `/api/dostk/stkinfo`

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
| `qry_tp` | String Y 1 1:1분, 2:10분, 3:1시간, 4:당일 누적, 5:30초 토큰 지정시 토큰타입("Bearer") 붙혀서 호출 예) Bearer Egicyx... |  |  |  | String Y 1 1:1분, 2:10분, 3:1시간, 4:당일 누적, 5:30초 토큰 지정시 토큰타입("Bearer") 붙혀서 호출 예) Bearer Egicyx... |

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
| `item_inq_rank` | 실시간종목조회순위 LIST N |  |  |  | 실시간종목조회순위 LIST N |
| `- stk_nm` | 종목명 | String | N | 40 | 종목명 |
| `- bigd_rank` | 빅데이터 순위 | String | N | 20 | 빅데이터 순위 |
| `- rank_chg` | 순위 등락 | String | N | 20 | 순위 등락 |
| `- rank_chg_sign` | 순위 등락 부호 | String | N | 20 | 순위 등락 부호 |
| `- past_curr_prc` | 과거 현재가 | String | N | 20 | 과거 현재가 |
| `- base_comp_sign` | 기준가 대비 부호 | String | N | 20 | 기준가 대비 부호 |
| `- base_comp_chgr` | 기준가 대비 등락율 | String | N | 20 | 기준가 대비 등락율 |
| `- prev_base_sign` | 직전 기준 대비 부호 | String | N | 20 | 직전 기준 대비 부호 |
| `- prev_base_chgr` | 직전 기준 대비 등락율 | String | N | 20 | 직전 기준 대비 등락율 |
| `- dt` | 일자 | String | N | 20 | 일자 |

---

## ka10001

**주식기본정보요청**

- **메뉴**: 국내주식 > 종목정보 > 주식기본정보요청(ka10001)
- **Method**: `POST`
- **URL**: `/api/dostk/stkinfo`

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
| `stk_cd` | 종목코드 | String | N | 20 | 종목코드 |
| `stk_nm` | 종목명 | String | N | 40 | 종목명 |
| `setl_mm` | 결산월 | String | N | 20 | 결산월 |
| `fav` | 액면가 | String | N | 20 | 액면가 |
| `cap` | 자본금 | String | N | 20 | 자본금 |
| `flo_stk` | 상장주식 | String | N | 20 | 상장주식 |
| `crd_rt` | 신용비율 | String | N | 20 | 신용비율 |
| `oyr_hgst` | 연중최고 | String | N | 20 | 연중최고 |
| `oyr_lwst` | 연중최저 | String | N | 20 | 연중최저 |
| `mac` | 시가총액 | String | N | 20 | 시가총액 |
| `mac_wght` | 시가총액비중 | String | N | 20 | 시가총액비중 |

---

## ka10002

**주식거래원요청**

- **메뉴**: 국내주식 > 종목정보 > 주식거래원요청(ka10002)
- **Method**: `POST`
- **URL**: `/api/dostk/stkinfo`

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
| `stk_cd` | 종목코드 | String | N | 20 | 종목코드 |
| `stk_nm` | 종목명 | String | N | 40 | 종목명 |
| `cur_prc` | 현재가 | String | N | 20 | 현재가 |
| `flu_smbol` | 등락부호 | String | N | 20 | 등락부호 |
| `base_pric` | 기준가 | String | N | 20 | 기준가 |
| `pred_pre` | 전일대비 | String | N | 20 | 전일대비 |
| `flu_rt` | 등락율 | String | N | 20 | 등락율 |
| `sel_trde_ori_nm_1` | 매도거래원명1 | String | N | 20 | 매도거래원명1 |
| `sel_trde_ori_1` | 매도거래원1 | String | N | 20 | 매도거래원1 |
| `sel_trde_qty_1` | 매도거래량1 | String | N | 20 | 매도거래량1 |
| `buy_trde_ori_nm_1` | 매수거래원명1 | String | N | 20 | 매수거래원명1 |

---

## ka10003

**체결정보요청**

- **메뉴**: 국내주식 > 종목정보 > 체결정보요청(ka10003)
- **Method**: `POST`
- **URL**: `/api/dostk/stkinfo`

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
| `cntr_infr` | 체결정보 LIST N |  |  |  | 체결정보 LIST N |
| `- tm` | 시간 | String | N | 20 | 시간 |
| `- cur_prc` | 현재가 | String | N | 20 | 현재가 |
| `- pred_pre` | 전일대비 | String | N | 20 | 전일대비 |
| `- pre_rt` | 대비율 | String | N | 20 | 대비율 |
| `- pri_sel_bid_unit` | 우선매도호가단위 | String | N | 20 | 우선매도호가단위 |
| `- pri_buy_bid_unit` | 우선매수호가단위 | String | N | 20 | 우선매수호가단위 |
| `- cntr_trde_qty` | 체결거래량 | String | N | 20 | 체결거래량 |
| `- sign` | sign | String | N | 20 | sign |
| `- acc_trde_qty` | 누적거래량 | String | N | 20 | 누적거래량 |
| `- acc_trde_prica` | 누적거래대금 | String | N | 20 | 누적거래대금 |

---

## ka10013

**신용매매동향요청**

- **메뉴**: 국내주식 > 종목정보 > 신용매매동향요청(ka10013)
- **Method**: `POST`
- **URL**: `/api/dostk/stkinfo`

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
| `dt` | 일자 | String | Y | 8 | YYYYMMDD |
| `qry_tp` | 조회구분 | String | Y | 1 | 1:융자, 2:대주 토큰 지정시 토큰타입("Bearer") 붙혀서 호출 예) Bearer Egicyx... |

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
| `crd_trde_trend` | 신용매매동향 LIST N |  |  |  | 신용매매동향 LIST N |
| `- dt` | 일자 | String | N | 20 | 일자 |
| `- cur_prc` | 현재가 | String | N | 20 | 현재가 |
| `- pred_pre_sig` | 전일대비기호 | String | N | 20 | 전일대비기호 |
| `- pred_pre` | 전일대비 | String | N | 20 | 전일대비 |
| `- trde_qty` | 거래량 | String | N | 20 | 거래량 |
| `- new` | 신규 | String | N | 20 | 신규 |
| `- rpya` | 상환 | String | N | 20 | 상환 |
| `- remn` | 잔고 | String | N | 20 | 잔고 |

---

## ka10015

**일별거래상세요청**

- **메뉴**: 국내주식 > 종목정보 > 일별거래상세요청(ka10015)
- **Method**: `POST`
- **URL**: `/api/dostk/stkinfo`

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
| `strt_dt` | 시작일자 | String | Y | 8 | YYYYMMDD 토큰 지정시 토큰타입("Bearer") 붙혀서 호출 예) Bearer Egicyx... |

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
| `daly_trde_dtl` | 일별거래상세 LIST N |  |  |  | 일별거래상세 LIST N |
| `- dt` | 일자 | String | N | 20 | 일자 |
| `- close_pric` | 종가 | String | N | 20 | 종가 |
| `- pred_pre_sig` | 전일대비기호 | String | N | 20 | 전일대비기호 |
| `- pred_pre` | 전일대비 | String | N | 20 | 전일대비 |
| `- flu_rt` | 등락율 | String | N | 20 | 등락율 |
| `- trde_qty` | 거래량 | String | N | 20 | 거래량 |
| `- trde_prica` | 거래대금 | String | N | 20 | 거래대금 |
| `- bf_mkrt_trde_qty` | 장전거래량 | String | N | 20 | 장전거래량 |
| `- bf_mkrt_trde_wght` | 장전거래비중 | String | N | 20 | 장전거래비중 |

---

## ka10016

**신고저가요청**

- **메뉴**: 국내주식 > 종목정보 > 신고저가요청(ka10016)
- **Method**: `POST`
- **URL**: `/api/dostk/stkinfo`

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
| `ntl_tp` | 신고저구분 | String | Y | 1 | 1:신고가,2:신저가 |
| `high_low_close_tp` | 고저종구분 | String | Y | 1 | 1:고저기준, 2:종가기준 |
| `stk_cnd` | 종목조건 | String | Y | 1 | 0:전체조회,1:관리종목제외, 3:우선주제외, 5:증100제외, 6:증100만보기, 7:증40만보기, 8:증30만보기 |
| `trde_qty_tp` | 거래량구분 | String | Y | 5 | 00000:전체조회, 00010:만주이상, 00050:5만주이상, 00100:10만주이상, 00150:15만주이상, 00200:20만주이상, 00300:30만주이상, 00500:50만주이상, 01000:백만주이상 |
| `crd_cnd` | 신용조건 | String | Y | 1 | 0:전체조회, 1:신용융자A군, 2:신용융자B군, 3:신용융자C군, 4:신용융자D군, 7:신용융자E군, 9:신용융자전체 |
| `updown_incls` | 상하한포함 | String | Y | 1 | 0:미포함, 1:포함 |
| `dt` | 기간 | String | Y | 3 | 5:5일, 10:10일, 20:20일, 60:60일, 250:250일, 250일까지 입력가능 |
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
| `ntl_pric` | 신고저가 LIST N |  |  |  | 신고저가 LIST N |

---

## ka10017

**상하한가요청**

- **메뉴**: 국내주식 > 종목정보 > 상하한가요청(ka10017)
- **Method**: `POST`
- **URL**: `/api/dostk/stkinfo`

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
| `updown_tp` | 상하한구분 | String | Y | 1 | 1:상한, 2:상승, 3:보합, 4: 하한, 5:하락, 6:전일상한, 7:전일하한 |
| `sort_tp` | 정렬구분 | String | Y | 1 | 1:종목코드순, 2:연속횟수순(상위100개), 3:등락률순 토큰 지정시 토큰타입("Bearer") 붙혀서 호출 예) Bearer Egicyx... |
| `stk_cnd` | 종목조건 | String | Y | 1 | 0:전체조회,1:관리종목제외, 3:우선주제외, 4:우선주+관리종목제외, 5:증100제외, 6:증100만 보기, 7:증40만 보기, 8:증30만 보기, 9:증20만 보기, 10:우선주+관리종목+환기종목제외 |
| `trde_qty_tp` | 거래량구분 | String | Y | 5 | 00000:전체조회, 00010:만주이상, 00050:5만주이상, 00100:10만주이상, 00150:15만주이상, 00200:20만주이상, 00300:30만주이상, 00500:50만주이상, 01000:백만주이상 |
| `crd_cnd` | 신용조건 | String | Y | 1 | 0:전체조회, 1:신용융자A군, 2:신용융자B군, 3:신용융자C군, 4:신용융자D군, 7:신용융자E군, 9:신용융자전체 |
| `trde_gold_tp` | 매매금구분 | String | Y | 1 | 0:전체조회, 1:1천원미만, 2:1천원~2천원, 3:2천원~3천원, 4:5천원~1만원, 5:1만원이상, 8:1천원이상 |
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
| `updown_pric` | 상하한가 LIST N |  |  |  | 상하한가 LIST N |

---

## ka10018

**고저가근접요청**

- **메뉴**: 국내주식 > 종목정보 > 고저가근접요청(ka10018)
- **Method**: `POST`
- **URL**: `/api/dostk/stkinfo`

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
| `high_low_tp` | 고저구분 | String | Y | 1 | 1:고가, 2:저가 |
| `alacc_rt` | 근접율 | String | Y | 2 | 05:0.5 10:1.0, 15:1.5, 20:2.0. 25:2.5, 30:3.0 |
| `mrkt_tp` | 시장구분 | String | Y | 3 | 000:전체, 001:코스피, 101:코스닥 |
| `trde_qty_tp` | 거래량구분 | String | Y | 5 | 00000:전체조회, 00010:만주이상, 00050:5만주이상, 00100:10만주이상, 00150:15만주이상, 00200:20만주이상, 00300:30만주이상, 00500:50만주이상, 01000:백만주이상 |
| `stk_cnd` | 종목조건 | String | Y | 1 | 0:전체조회,1:관리종목제외, 3:우선주제외, 5:증100제외, 6:증100만보기, 7:증40만보기, 8:증30만보기 |
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
| `high_low_pric_alacc` | 고저가근접 LIST N |  |  |  | 고저가근접 LIST N |
| `- stk_cd` | 종목코드 | String | N | 20 | 종목코드 |
| `- stk_nm` | 종목명 | String | N | 40 | 종목명 |

---

## ka10019

**가격급등락요청**

- **메뉴**: 국내주식 > 종목정보 > 가격급등락요청(ka10019)
- **Method**: `POST`
- **URL**: `/api/dostk/stkinfo`

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
| `mrkt_tp` | 시장구분 | String | Y | 3 | 000:전체, 001:코스피, 101:코스닥, 201:코스피200 |
| `flu_tp` | 등락구분 | String | Y | 1 | 1:급등, 2:급락 |
| `tm_tp` | 시간구분 | String | Y | 1 | 1:분전, 2:일전 |
| `tm` | 시간 | String | Y | 2 | 분 혹은 일입력 |
| `trde_qty_tp` | 거래량구분 | String | Y | 4 | 00000:전체조회, 00010:만주이상, 00050:5만주이상, 00100:10만주이상, 00150:15만주이상, 00200:20만주이상, 00300:30만주이상, 00500:50만주이상, 01000:백만주이상 |
| `stk_cnd` | 종목조건 | String | Y | 1 | 0:전체조회,1:관리종목제외, 3:우선주제외, 5:증100제외, 6:증100만보기, 7:증40만보기, 8:증30만보기 |
| `crd_cnd` | 신용조건 | String | Y | 1 | 0:전체조회, 1:신용융자A군, 2:신용융자B군, 3:신용융자C군, 4:신용융자D군, 7:신용융자E군, 9:신용융자전체 |
| `pric_cnd` | 가격조건 | String | Y | 1 | 0:전체조회, 1:1천원미만, 2:1천원~2천원, 3:2천원~3천원, 4:5천원~1만원, 5:1만원이상, 8:1천원이상 |
| `updown_incls` | 상하한포함 | String | Y | 1 | 0:미포함, 1:포함 |
| `stex_tp` | 거래소구분 | String | Y | 1 | 1:KRX, 2:NXT 3.통합 토큰 지정시 토큰타입("Bearer") 붙혀서 호출 예) Bearer Egicyx... |

### Response

**Headers**

| Element | 한글명 | Type | Required | Length | Description |
|---------|--------|------|----------|--------|-------------|
| `api-id` | TR명 | String | Y | 10 | TR명 |
| `cont-yn` | 연속조회여부 | String | N | 1 | 다음 데이터가 있을시 Y값 전달 |
| `next-key` | 연속조회키 | String | N | 50 | 다음 데이터가 있을시 다음 키값 전달 |

---

## ka10024

**거래량갱신요청**

- **메뉴**: 국내주식 > 종목정보 > 거래량갱신요청(ka10024)
- **Method**: `POST`
- **URL**: `/api/dostk/stkinfo`

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
| `cycle_tp` | 주기구분 | String | Y | 1 | 5:5일, 10:10일, 20:20일, 60:60일, 250:250일 |
| `trde_qty_tp` | 거래량구분 | String | Y | 1 | 5:5천주이상, 10:만주이상, 50:5만주이상, 100:10만주이상, 200:20만주이상, 300:30만주이상, 500:50만주이상, 1000:백만주이상 |
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
| `trde_qty_updt` | 거래량갱신 LIST N |  |  |  | 거래량갱신 LIST N |
| `- stk_cd` | 종목코드 | String | N | 20 | 종목코드 |
| `- stk_nm` | 종목명 | String | N | 40 | 종목명 |
| `- cur_prc` | 현재가 | String | N | 20 | 현재가 |
| `- pred_pre_sig` | 전일대비기호 | String | N | 20 | 전일대비기호 |
| `- pred_pre` | 전일대비 | String | N | 20 | 전일대비 |
| `- flu_rt` | 등락률 | String | N | 20 | 등락률 |

---

## ka10025

**매물대집중요청**

- **메뉴**: 국내주식 > 종목정보 > 매물대집중요청(ka10025)
- **Method**: `POST`
- **URL**: `/api/dostk/stkinfo`

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
| `prps_cnctr_rt` | 매물집중비율 | String | Y | 3 | 0~100 입력 |
| `cur_prc_entry` | 현재가진입 | String | Y | 1 | 0:현재가 매물대 진입 포함안함, 1:현재가 매물대 진입포함 |
| `prpscnt` | 매물대수 | String | Y | 2 | 숫자입력 |
| `cycle_tp` | 주기구분 | String | Y | 2 | 50:50일, 100:100일, 150:150일, 200:200일, 250:250일, 300:300일 |
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
| `prps_cnctr` | 매물대집중 LIST N |  |  |  | 매물대집중 LIST N |
| `- stk_cd` | 종목코드 | String | N | 20 | 종목코드 |
| `- stk_nm` | 종목명 | String | N | 40 | 종목명 |
| `- cur_prc` | 현재가 | String | N | 20 | 현재가 |
| `- pred_pre_sig` | 전일대비기호 | String | N | 20 | 전일대비기호 |
| `- pred_pre` | 전일대비 | String | N | 20 | 전일대비 |

---

## ka10026

**고저PER요청**

- **메뉴**: 국내주식 > 종목정보 > 고저PER요청(ka10026)
- **Method**: `POST`
- **URL**: `/api/dostk/stkinfo`

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
| `pertp` | PER구분 | String | Y | 1 | 1:저PBR, 2:고PBR, 3:저PER, 4:고PER, 5:저ROE, 6:고ROE |
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
| `high_low_per` | 고저PER LIST N |  |  |  | 고저PER LIST N |
| `- stk_cd` | 종목코드 | String | N | 20 | 종목코드 |
| `- stk_nm` | 종목명 | String | N | 40 | 종목명 |
| `- per` | PER | String | N | 20 | PER |
| `- cur_prc` | 현재가 | String | N | 20 | 현재가 |
| `- pred_pre_sig` | 전일대비기호 | String | N | 20 | 전일대비기호 |
| `- pred_pre` | 전일대비 | String | N | 20 | 전일대비 |
| `- flu_rt` | 등락률 | String | N | 20 | 등락률 |
| `- now_trde_qty` | 현재거래량 | String | N | 20 | 현재거래량 |
| `- sel_bid` | 매도호가 | String | N | 20 | 매도호가 |

---

## ka10028

**시가대비등락률요청**

- **메뉴**: 국내주식 > 종목정보 > 시가대비등락률요청(ka10028)
- **Method**: `POST`
- **URL**: `/api/dostk/stkinfo`

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
| `sort_tp` | 정렬구분 | String | Y | 1 | 1:시가, 2:고가, 3:저가, 4:기준가 |
| `trde_qty_cnd` | 거래량조건 | String | Y | 4 | 0000:전체조회, 0010:만주이상, 0050:5만주이상, 0100:10만주이상, 0500:50만주이상, 1000:백만주이상 |
| `mrkt_tp` | 시장구분 | String | Y | 3 | 000:전체, 001:코스피, 101:코스닥 |
| `updown_incls` | 상하한포함 | String | Y | 1 | 0:불 포함, 1:포함 |
| `stk_cnd` | 종목조건 | String | Y | 2 | 0:전체조회, 1:관리종목제외, 4:우선주+관리주제외, 3:우선주제외, 5:증100제외, 6:증100만보기, 7:증40만보기, 8:증30만보기, 9:증20만보기 |
| `crd_cnd` | 신용조건 | String | Y | 1 | 0:전체조회, 1:신용융자A군, 2:신용융자B군, 3:신용융자C군, 4:신용융자D군, 7:신용융자E군, 9:신용융자전체 |
| `trde_prica_cnd` | 거래대금조건 | String | Y | 4 | 0:전체조회, 3:3천만원이상, 5:5천만원이상, 10:1억원이상, 30:3억원이상, 50:5억원이상, 100:10억원이상, 300:30억원이상, 500:50억원이상, 1000:100억원이상, 3000:300억원이상, 5000:500억원이상 |
| `flu_cnd` | 등락조건 | String | Y | 1 | 1:상위, 2:하위 |
| `stex_tp` | 거래소구분 | String | Y | 1 | 1:KRX, 2:NXT 3.통합 토큰 지정시 토큰타입("Bearer") 붙혀서 호출 예) Bearer Egicyx... |

### Response

**Headers**

| Element | 한글명 | Type | Required | Length | Description |
|---------|--------|------|----------|--------|-------------|
| `api-id` | TR명 | String | Y | 10 | TR명 |
| `cont-yn` | 연속조회여부 | String | N | 1 | 다음 데이터가 있을시 Y값 전달 |
| `next-key` | 연속조회키 | String | N | 50 | 다음 데이터가 있을시 다음 키값 전달 |

---

## ka10043

**거래원매물대분석요청**

- **메뉴**: 국내주식 > 종목정보 > 거래원매물대분석요청(ka10043)
- **Method**: `POST`
- **URL**: `/api/dostk/stkinfo`

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
| `qry_dt_tp` | 조회기간구분 | String | Y | 1 | 0:기간으로 조회, 1:시작일자, 종료일자로 조회 |
| `pot_tp` | 시점구분 | String | Y | 1 | 0:당일, 1:전일 |
| `dt` | 기간 | String | Y | 4 | 5:5일, 10:10일, 20:20일, 40:40일, 60:60일, 120:120일 |
| `sort_base` | 정렬기준 | String | Y | 1 | 1:종가순, 2:날짜순 |
| `mmcm_cd` | 회원사코드 | String | Y | 3 | 회원사 코드는 ka10102 조회 |
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
| `trde_ori_prps_anly` | 거래원매물대분석 LIST N |  |  |  | 거래원매물대분석 LIST N |
| `- dt` | 일자 | String | N | 20 | 일자 |
| `- close_pric` | 종가 | String | N | 20 | 종가 |

---

## ka10052

**거래원순간거래량요청**

- **메뉴**: 국내주식 > 종목정보 > 거래원순간거래량요청(ka10052)
- **Method**: `POST`
- **URL**: `/api/dostk/stkinfo`

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
| `stk_cd` | 종목코드 | String | N | 20 | 거래소별 종목코드 (KRX:039490,NXT:039490_NX,SOR:039490_AL) |
| `mrkt_tp` | 시장구분 | String | Y | 1 | 0:전체, 1:코스피, 2:코스닥, 3:종목 |
| `qty_tp` | 수량구분 | String | Y | 3 | 0:전체, 1:1000주, 2:2000주, 3:, 5:, 10:10000주, 30: 30000주, 50: 50000주, 100: 100000주 |
| `pric_tp` | 가격구분 | String | Y | 1 | 0:전체, 1:1천원 미만, 8:1천원 이상, 2:1천원 ~ 2천원, 3:2천원 ~ 5천원, 4:5천원 ~ 1만원, 5:1만원 이상 |
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
| `trde_ori_mont_trde_` | qty 거래원순간거래량 LIST N |  |  |  | qty 거래원순간거래량 LIST N |
| `- tm` | 시간 | String | N | 20 | 시간 |
| `- stk_cd` | 종목코드 | String | N | 20 | 종목코드 |
| `- stk_nm` | 종목명 | String | N | 20 | 종목명 |

---

## ka10054

**변동성완화장치발동종목요청**

- **메뉴**: 국내주식 > 종목정보 > 변동성완화장치발동종목요청(ka10054)
- **Method**: `POST`
- **URL**: `/api/dostk/stkinfo`

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
| `mrkt_tp` | 시장구분 | String | Y | 3 | 000:전체, 001: 코스피, 101:코스닥 |
| `bf_mkrt_tp` | 장전구분 | String | Y | 1 | 0:전체, 1:정규시장,2:시간외단일가 |
| `stk_cd` | 종목코드 | String | N | 20 | 거래소별 종목코드 (KRX:039490,NXT:039490_NX,SOR:039490_AL) 공백입력시 시장구분으로 설정한 전체종목조회 |
| `motn_tp` | 발동구분 | String | Y | 1 | 0:전체, 1:정적VI, 2:동적VI, 3:동적VI + 정적VI 토큰 지정시 토큰타입("Bearer") 붙혀서 호출 예) Bearer Egicyx... |
| `skip_stk` | 제외종목 | String | Y | 9 | 전종목포함 조회시 9개 0으로 설정(000000000),전종목제외 조회시 9개 1으로 설정(111111111),9개 종목조회여부를 조회포함(0), 조회제외(1)로 설정하며 종목순서는 우선주,관리 종목,투자경고/위험,투자주의,환기종목,단기과열종목,증거금1 00%,ETF,ETN가 됨.우선주만 조회시"011111111"", 관리종목만 조회시 ""101111111"" 설정" |
| `trde_qty_tp` | 거래량구분 | String | Y | 1 | 0:사용안함, 1:사용 |
| `min_trde_qty` | 최소거래량 | String | Y | 12 | 0 주 이상, 거래량구분이 1일때만 입력(공백허용) |
| `max_trde_qty` | 최대거래량 | String | Y | 12 | 100000000 주 이하, 거래량구분이 1일때만 입력(공백허용) |
| `trde_prica_tp` | 거래대금구분 | String | Y | 1 | 0:사용안함, 1:사용 |
| `min_trde_prica` | 최소거래대금 | String | Y | 10 | 0 백만원 이상, 거래대금구분 1일때만 입력(공백허용) |
| `max_trde_prica` | 최대거래대금 | String | Y | 10 | 100000000 백만원 이하, 거래대금구분 1일때만 입력(공백허용) |
| `motn_drc` | 발동방향 | String | Y | 1 | 0:전체, 1:상승, 2:하락 |
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
| `motn_stk` | 발동종목 LIST N |  |  |  | 발동종목 LIST N |
| `- stk_cd` | 종목코드 | String | N | 20 | 종목코드 |
| `- stk_nm` | 종목명 | String | N | 40 | 종목명 |
| `- acc_trde_qty` | 누적거래량 | String | N | 20 | 누적거래량 |
| `- motn_pric` | 발동가격 | String | N | 20 | 발동가격 |
| `- dynm_dispty_rt` | 동적괴리율 | String | N | 20 | 동적괴리율 |
| `trde_cntr_proc_time` | 매매체결처리시각 | String | N | 20 | 매매체결처리시각 |
| `- virelis_time` | VI해제시각 | String | N | 20 | VI해제시각 |
| `- viaplc_tp` | VI적용구분 | String | N | 20 | VI적용구분 |
| `- dynm_stdpc` | 동적기준가격 | String | N | 20 | 동적기준가격 |
| `- static_stdpc` | 정적기준가격 | String | N | 20 | 정적기준가격 |
| `- static_dispty_rt` | 정적괴리율 | String | N | 20 | 정적괴리율 |
| `open_pric_pre_flu_rt` | 시가대비등락률 | String | N | 20 | 시가대비등락률 |
| `- vimotn_cnt` | VI발동횟수 | String | N | 20 | VI발동횟수 |
| `- stex_tp` | 거래소구분 | String | N | 20 | 거래소구분 |

---

## ka10055

**당일전일체결량요청**

- **메뉴**: 국내주식 > 종목정보 > 당일전일체결량요청(ka10055)
- **Method**: `POST`
- **URL**: `/api/dostk/stkinfo`

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
| `tdy_pred` | 당일전일 | String | Y | 1 | 1:당일, 2:전일 토큰 지정시 토큰타입("Bearer") 붙혀서 호출 예) Bearer Egicyx... |

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
| `tdy_pred_cntr_qty` | 당일전일체결량 LIST N |  |  |  | 당일전일체결량 LIST N |
| `- cntr_tm` | 체결시간 | String | N | 20 | 체결시간 |
| `- cntr_pric` | 체결가 | String | N | 20 | 체결가 |
| `- pred_pre_sig` | 전일대비기호 | String | N | 20 | 전일대비기호 |
| `- pred_pre` | 전일대비 | String | N | 20 | 전일대비 |
| `- flu_rt` | 등락율 | String | N | 20 | 등락율 |
| `- cntr_qty` | 체결량 | String | N | 20 | 체결량 |
| `- acc_trde_qty` | 누적거래량 | String | N | 20 | 누적거래량 |
| `- acc_trde_prica` | 누적거래대금 | String | N | 20 | 누적거래대금 |

---

## ka10058

**투자자별일별매매종목요청**

- **메뉴**: 국내주식 > 종목정보 > 투자자별일별매매종목요청(ka10058)
- **Method**: `POST`
- **URL**: `/api/dostk/stkinfo`

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
| `trde_tp` | 매매구분 | String | Y | 1 | 순매도:1, 순매수:2 |
| `mrkt_tp` | 시장구분 | String | Y | 3 | 001:코스피, 101:코스닥 |
| `invsr_tp` | 투자자구분 | String | Y | 4 | 8000:개인, 9000:외국인, 1000:금융투자, 3000:투신, 3100:사모펀드, 5000:기타금융, 4000:은행, 2000:보험, 6000:연기금, 7000:국가, 7100:기타법인, 9999:기관계 |
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
| `invsr_daly_trde_stk` | 투자자별일별매매종 목 LIST N |  |  |  | 투자자별일별매매종 목 LIST N |
| `- stk_cd` | 종목코드 | String | N | 20 | 종목코드 |
| `- stk_nm` | 종목명 | String | N | 40 | 종목명 |
| `- netslmt_qty` | 순매도수량 | String | N | 20 | 순매도수량 |
| `- netslmt_amt` | 순매도금액 | String | N | 20 | 순매도금액 |

---

## ka10059

**종목별투자자기관별요청**

- **메뉴**: 국내주식 > 종목정보 > 종목별투자자기관별요청(ka10059)
- **Method**: `POST`
- **URL**: `/api/dostk/stkinfo`

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
| `stk_invsr_orgn` | 종목별투자자기관별 LIST N |  |  |  | 종목별투자자기관별 LIST N |
| `- dt` | 일자 | String | N | 20 | 일자 |
| `- cur_prc` | 현재가 | String | N | 20 | 현재가 |
| `- pre_sig` | 대비기호 | String | N | 20 | 대비기호 |
| `- pred_pre` | 전일대비 | String | N | 20 | 전일대비 |
| `- flu_rt` | 등락율 | String | N | 20 | 등락율 |
| `- acc_trde_qty` | 누적거래량 | String | N | 20 | 우측 2자리 소수점자리수 |

---

## ka10061

**종목별투자자기관별합계요청**

- **메뉴**: 국내주식 > 종목정보 > 종목별투자자기관별합계요청(ka10061)
- **Method**: `POST`
- **URL**: `/api/dostk/stkinfo`

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
| `amt_qty_tp` | 금액수량구분 | String | Y | 1 | 1:금액, 2:수량 |
| `trde_tp` | 매매구분 | String | Y | 1 | 0:순매수 |
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
| `stk_invsr_orgn_tot` | 종목별투자자기관별 합계 LIST N |  |  |  | 종목별투자자기관별 합계 LIST N |
| `- ind_invsr` | 개인투자자 | String | N | 20 | 개인투자자 |
| `- frgnr_invsr` | 외국인투자자 | String | N | 20 | 외국인투자자 |
| `- orgn` | 기관계 | String | N | 20 | 기관계 |
| `- fnnc_invt` | 금융투자 | String | N | 20 | 금융투자 |

---

## ka10084

**당일전일체결요청**

- **메뉴**: 국내주식 > 종목정보 > 당일전일체결요청(ka10084)
- **Method**: `POST`
- **URL**: `/api/dostk/stkinfo`

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
| `tdy_pred` | 당일전일 | String | Y | 1 | 당일 : 1, 전일 : 2 |
| `tic_min` | 틱분 | String | Y | 1 | 0:틱, 1:분 |
| `tm` | 시간 | String | N | 4 | 조회시간 4자리, 오전 9시일 경우 0900, 오후 2시 30분일 경우 1430 토큰 지정시 토큰타입("Bearer") 붙혀서 호출 예) Bearer Egicyx... |

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
| `tdy_pred_cntr` | 당일전일체결 LIST N |  |  |  | 당일전일체결 LIST N |
| `- tm` | 시간 | String | N | 20 | 시간 |
| `- cur_prc` | 현재가 | String | N | 20 | 현재가 |
| `- pred_pre` | 전일대비 | String | N | 20 | 전일대비 |
| `- pre_rt` | 대비율 | String | N | 20 | 대비율 |
| `- pri_sel_bid_unit` | 우선매도호가단위 | String | N | 20 | 우선매도호가단위 |
| `- pri_buy_bid_unit` | 우선매수호가단위 | String | N | 20 | 우선매수호가단위 |

---

## ka10095

**관심종목정보요청**

- **메뉴**: 국내주식 > 종목정보 > 관심종목정보요청(ka10095)
- **Method**: `POST`
- **URL**: `/api/dostk/stkinfo`

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
| `stk_cd` | 종목코드 | String | Y | 20 | 거래소별 종목코드 (KRX:039490,NXT:039490_NX,SOR:039490_AL) 여러개의 종목코드 입력시 | 로 구분 토큰 지정시 토큰타입("Bearer") 붙혀서 호출 예) Bearer Egicyx... |

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
| `atn_stk_infr` | 관심종목정보 LIST N |  |  |  | 관심종목정보 LIST N |
| `- stk_cd` | 종목코드 | String | N | 20 | 종목코드 |
| `- stk_nm` | 종목명 | String | N | 40 | 종목명 |
| `- cur_prc` | 현재가 | String | N | 20 | 현재가 |
| `- base_pric` | 기준가 | String | N | 20 | 기준가 |
| `- pred_pre` | 전일대비 | String | N | 20 | 전일대비 |
| `- pred_pre_sig` | 전일대비기호 | String | N | 20 | 전일대비기호 |
| `- flu_rt` | 등락율 | String | N | 20 | 등락율 |
| `- trde_qty` | 거래량 | String | N | 20 | 거래량 |
| `- trde_prica` | 거래대금 | String | N | 20 | 거래대금 |

---

## ka10099

**종목정보 리스트**

- **메뉴**: 국내주식 > 종목정보 > 종목정보 리스트(ka10099)
- **Method**: `POST`
- **URL**: `/api/dostk/stkinfo`

### Request

**Headers**

| Element | 한글명 | Type | Required | Length | Description |
|---------|--------|------|----------|--------|-------------|
| `api-id` | TR명 | String | Y | 10 | TR명 |
| `authorization` | 접근토큰 | String | Y | 1000 | 접근토큰 |
| `cont-yn` | 연속조회여부 | String | N | 1 | 응답 Header의 연속조회여부값이 Y일 경우 다음데이터 요청시 응답 Header의 cont-yn값 세팅 |
| `next-key` | 연속조회키 | String | N | 50 | 응답 Header의 연속조회여부값이 Y일 경우 다음데이터 요청시 응답 Header의 next-key값 세팅 2 0 : 코스피, 10 : 코스닥, 30 : K-OTC, 50 : 코넥스, 60 : ETN, 70 : 손실제한 ETN, 80 : 금현물, 90 : 변동성 ETN, 2 : 인프라투융자, 3 : ELW, 4 : 뮤추얼펀드, 5 : 신주인수권, 6 : 리츠종목, 7 : 신주인수권증서, 8 : ETF, 9 : 하이일드펀드 |

**Body**

| Element | 한글명 | Type | Required | Length | Description |
|---------|--------|------|----------|--------|-------------|
| `mrkt_tp` | 시장구분 | String | Y |  | 토큰 지정시 토큰타입("Bearer") 붙혀서 호출 예) Bearer Egicyx... |

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
| `list` | 종목리스트 LIST N |  |  |  | 종목리스트 LIST N |
| `- code` | 종목코드 | String | N | 20 | 단축코드 |
| `- name` | 종목명 | String | N | 40 | 종목명 |
| `- listCount` | 상장주식수 | String | N | 20 | 상장주식수 |

---

## ka10100

**종목정보 조회**

- **메뉴**: 국내주식 > 종목정보 > 종목정보 조회(ka10100)
- **Method**: `POST`
- **URL**: `/api/dostk/stkinfo`

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
| `code` | 종목코드 | String | N |  | 종목코드 |
| `name` | 종목명 | String | N |  | 종목명 |
| `listCount` | 상장주식수 | String | N |  | 상장주식수 |
| `auditInfo` | 감리구분 | String | N |  | 감리구분 |
| `regDay` | 상장일 | String | N |  | 상장일 |
| `lastPrice` | 전일종가 | String | N |  | 전일종가 |
| `state` | 종목상태 | String | N |  | 종목상태 |
| `marketCode` | 시장구분코드 | String | N |  | 시장구분코드 |
| `marketName` | 시장명 | String | N |  | 시장명 |
| `upName` | 업종명 | String | N |  | 업종명 |
| `upSizeName` | 회사크기분류 | String | N | 40 | 단축코드 |

---

## ka10101

**업종코드 리스트**

- **메뉴**: 국내주식 > 종목정보 > 업종코드 리스트(ka10101)
- **Method**: `POST`
- **URL**: `/api/dostk/stkinfo`

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
| `mrkt_tp` | 시장구분 | String | Y | 1 | 0:코스피(거래소),1:코스닥,2:KOSPI200,4:KOSPI100,7:KRX100( 통합지수) 토큰 지정시 토큰타입("Bearer") 붙혀서 호출 예) Bearer Egicyx... |

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
| `list` | 업종코드리스트 LIST N |  |  |  | 업종코드리스트 LIST N |
| `- marketCode` | 시장구분코드 LIST N |  |  |  | 시장구분코드 LIST N |
| `- code` | 코드 | String | N |  | 코드 |
| `- name` | 업종명 | String | N |  | 업종명 |
| `- group` | 그룹 | String | N |  | 그룹 |

---

## ka10102

**회원사 리스트**

- **메뉴**: 국내주식 > 종목정보 > 회원사 리스트(ka10102)
- **Method**: `POST`
- **URL**: `/api/dostk/stkinfo`

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
| `list` | 회원사코드리스트 LIST N |  |  |  | 회원사코드리스트 LIST N |
| `- code` | 코드 | String | N |  | 코드 |
| `- name` | 업종명 | String | N |  | 업종명 |
| `- gb` | String N |  |  |  | String N |

---

## ka90003

**프로그램순매수상위50요청**

- **메뉴**: 국내주식 > 종목정보 > 프로그램순매수상위50요청(ka90003)
- **Method**: `POST`
- **URL**: `/api/dostk/stkinfo`

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
| `trde_upper_tp` | 매매상위구분 | String | Y | 1 | 1:순매도상위, 2:순매수상위 |
| `amt_qty_tp` | 금액수량구분 | String | Y | 2 | 1:금액, 2:수량 |
| `mrkt_tp` | 시장구분 | String | Y | 10 | P00101:코스피, P10102:코스닥 |
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
| `prm_netprps_upper_` | 50 프로그램순매수상위 50 LIST N |  |  |  | 50 프로그램순매수상위 50 LIST N |
| `- rank` | 순위 | String | N | 20 | 순위 |
| `- stk_cd` | 종목코드 | String | N | 20 | 종목코드 |
| `- stk_nm` | 종목명 | String | N | 40 | 종목명 |
| `- cur_prc` | 현재가 | String | N | 20 | 현재가 |
| `- flu_sig` | 등락기호 | String | N | 20 | 등락기호 |
| `- pred_pre` | 전일대비 | String | N | 20 | 전일대비 |
| `- flu_rt` | 등락율 | String | N | 20 | 등락율 |

---

## ka90004

**종목별프로그램매매현황요청**

- **메뉴**: 국내주식 > 종목정보 > 종목별프로그램매매현황요청(ka90004)
- **Method**: `POST`
- **URL**: `/api/dostk/stkinfo`

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
| `mrkt_tp` | 시장구분 | String | Y | 10 | P00101:코스피, P10102:코스닥 |
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
| `tot_1` | 매수체결수량합계 | String | N | 20 | 매수체결수량합계 |
| `tot_2` | 매수체결금액합계 | String | N | 20 | 매수체결금액합계 |
| `tot_3` | 매도체결수량합계 | String | N | 20 | 매도체결수량합계 |
| `tot_4` | 매도체결금액합계 | String | N | 20 | 매도체결금액합계 |
| `tot_5` | 순매수대금합계 | String | N | 20 | 순매수대금합계 |
| `tot_6` | 합계6 | String | N | 20 | 합계6 |
| `stk_prm_trde_prst` | 종목별프로그램매매 현황 LIST N |  |  |  | 종목별프로그램매매 현황 LIST N |
| `- stk_cd` | 종목코드 | String | N | 20 | 종목코드 |
| `- stk_nm` | 종목명 | String | N | 40 | 종목명 |

---

## kt20016

**신용융자 가능종목요청**

- **메뉴**: 국내주식 > 종목정보 > 신용융자 가능종목요청(kt20016)
- **Method**: `POST`
- **URL**: `/api/dostk/stkinfo`

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
| `crd_stk_grde_tp` | 신용종목등급구분 | String | N | 1 | %:전체, A:A군, B:B군, C:C군, D:D군, E:E군 |
| `mrkt_deal_tp` | 시장거래구분 | String | Y | 1 | %:전체, 1:코스피, 0:코스닥 |
| `stk_cd` | 종목코드 | String | N | 12 | 토큰 지정시 토큰타입("Bearer") 붙혀서 호출 예) Bearer Egicyx... |

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
| `crd_loan_able` | 신용융자가능여부 | String | N | 40 | 신용융자가능여부 |
| `crd_loan_pos_stk` | 신용융자가능종목 LIST N |  |  |  | 신용융자가능종목 LIST N |
| `- stk_cd` | 종목코드 | String | N | 12 | 종목코드 |
| `- stk_nm` | 종목명 | String | N | 40 | 종목명 |
| `- crd_assr_rt` | 신용보증금율 | String | N | 4 | 신용보증금율 |
| `- repl_pric` | 대용가 | String | N | 12 | 대용가 |
| `- pred_close_pric` | 전일종가 | String | N | 12 | 전일종가 |
| `- crd_limit_over_yn` | 신용한도초과여부 | String | N | 1 | 신용한도초과여부 |
| `- crd_limit_over_txt` | 신용한도초과 | String | N | 40 | N:공란,Y:회사한도 초과 |

---

## kt20017

**신용융자 가능문의**

- **메뉴**: 국내주식 > 종목정보 > 신용융자 가능문의(kt20017)
- **Method**: `POST`
- **URL**: `/api/dostk/stkinfo`

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
| `stk_cd` | 종목코드 | String | Y | 12 | 토큰 지정시 토큰타입("Bearer") 붙혀서 호출 예) Bearer Egicyx... |

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
| `crd_alow_yn` | 신용가능여부 | String | N | 40 | 신용가능여부 |

---

