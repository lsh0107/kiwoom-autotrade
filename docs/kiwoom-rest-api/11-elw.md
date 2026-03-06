# ELW API

> API 수: 11개

## 목차

- [ka10048 - ELW일별민감도지표요청](#ka10048)
- [ka10050 - ELW민감도지표요청](#ka10050)
- [ka30001 - ELW가격급등락요청](#ka30001)
- [ka30002 - 거래원별ELW순매매상위요청](#ka30002)
- [ka30003 - ELWLP보유일별추이요청](#ka30003)
- [ka30004 - ELW괴리율요청](#ka30004)
- [ka30005 - ELW조건검색요청](#ka30005)
- [ka30009 - ELW등락율순위요청](#ka30009)
- [ka30010 - ELW잔량순위요청](#ka30010)
- [ka30011 - ELW근접율요청](#ka30011)
- [ka30012 - ELW종목상세정보요청](#ka30012)

---

## ka10048

**ELW일별민감도지표요청**

- **메뉴**: 국내주식 > ELW > ELW일별민감도지표요청(ka10048)
- **Method**: `POST`
- **URL**: `/api/dostk/elw`

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
| `elwdaly_snst_ix` | ELW일별민감도지표 LIST N |  |  |  | ELW일별민감도지표 LIST N |
| `- dt` | 일자 | String | N | 20 | 일자 |
| `- iv` | IV | String | N | 20 | IV |
| `- delta` | 델타 | String | N | 20 | 델타 |
| `- gam` | 감마 | String | N | 20 | 감마 |
| `- theta` | 쎄타 | String | N | 20 | 쎄타 |
| `- vega` | 베가 | String | N | 20 | 베가 |
| `- law` | 로 | String | N | 20 | 로 |
| `- lp` | LP | String | N | 20 | LP |

---

## ka10050

**ELW민감도지표요청**

- **메뉴**: 국내주식 > ELW > ELW민감도지표요청(ka10050)
- **Method**: `POST`
- **URL**: `/api/dostk/elw`

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
| `elwsnst_ix_array` | ELW민감도지표배열 LIST N |  |  |  | ELW민감도지표배열 LIST N |
| `- cntr_tm` | 체결시간 | String | N | 20 | 체결시간 |
| `- cur_prc` | 현재가 | String | N | 20 | 현재가 |
| `- elwtheory_pric` | ELW이론가 | String | N | 20 | ELW이론가 |
| `- iv` | IV | String | N | 20 | IV |
| `- delta` | 델타 | String | N | 20 | 델타 |
| `- gam` | 감마 | String | N | 20 | 감마 |
| `- theta` | 쎄타 | String | N | 20 | 쎄타 |
| `- vega` | 베가 | String | N | 20 | 베가 |
| `- law` | 로 | String | N | 20 | 로 |
| `- lp` | LP | String | N | 20 | LP |

---

## ka30001

**ELW가격급등락요청**

- **메뉴**: 국내주식 > ELW > ELW가격급등락요청(ka30001)
- **Method**: `POST`
- **URL**: `/api/dostk/elw`

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
| `flu_tp` | 등락구분 | String | Y | 1 | 1:급등, 2:급락 |
| `tm_tp` | 시간구분 | String | Y | 1 | 1:분전, 2:일전 |
| `tm` | 시간 | String | Y | 2 | 분 혹은 일입력 (예 1, 3, 5) |
| `trde_qty_tp` | 거래량구분 | String | Y | 4 | 0:전체, 10:만주이상, 50:5만주이상, 100:10만주이상, 300:30만주이상, 500:50만주이상, 1000:백만주이상 |
| `isscomp_cd` | 발행사코드 | String | Y | 12 | 전체:000000000000, 한국투자증권:3, 미래대우:5, 신영:6, NK투자증권:12, KB증권:17 |
| `bsis_aset_cd` | 기초자산코드 | String | Y | 12 | 전체:000000000000, KOSPI200:201, KOSDAQ150:150, 삼성전자:005930, KT:030200.. |
| `rght_tp` | 권리구분 | String | Y | 3 | 000:전체, 001:콜, 002:풋, 003:DC, 004:DP, 005:EX, 006:조기종료콜, 007:조기종료풋 |
| `lpcd` | LP코드 | String | Y | 12 | 전체:000000000000, 한국투자증권:3, 미래대우:5, 신영:6, NK투자증권:12, KB증권:17 |
| `trde_end_elwskip` | 거래종료ELW제외 | String | Y | 1 | 0:포함, 1:제외 토큰 지정시 토큰타입("Bearer") 붙혀서 호출 예) Bearer Egicyx... |

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
| `base_pric_tm` | 기준가시간 | String | N | 20 | 기준가시간 |

---

## ka30002

**거래원별ELW순매매상위요청**

- **메뉴**: 국내주식 > ELW > 거래원별ELW순매매상위요청(ka30002)
- **Method**: `POST`
- **URL**: `/api/dostk/elw`

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
| `isscomp_cd` | 발행사코드 | String | Y | 3 | 3자리, 영웅문4 0273화면참조 (교보:001, 신한금융투자:002, 한국투자증권:003, 대신:004, 미래대우:005, ,,,) |
| `trde_qty_tp` | 거래량구분 | String | Y | 4 | 0:전체, 5:5천주, 10:만주, 50:5만주, 100:10만주, 500:50만주, 1000:백만주 |
| `trde_tp` | 매매구분 | String | Y | 1 | 1:순매수, 2:순매도 |
| `dt` | 기간 | String | Y | 2 | 1:전일, 5:5일, 10:10일, 40:40일, 60:60일 |
| `trde_end_elwskip` | 거래종료ELW제외 | String | Y | 1 | 0:포함, 1:제외 토큰 지정시 토큰타입("Bearer") 붙혀서 호출 예) Bearer Egicyx... |

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
| `trde_ori_elwnettrde_` | upper 거래원별ELW순매매 상위 LIST N |  |  |  | upper 거래원별ELW순매매 상위 LIST N |
| `- stk_cd` | 종목코드 | String | N | 20 | 종목코드 |
| `- stk_nm` | 종목명 | String | N | 40 | 종목명 |
| `- stkpc_flu` | 주가등락 | String | N | 20 | 주가등락 |
| `- flu_rt` | 등락율 | String | N | 20 | 등락율 |
| `- trde_qty` | 거래량 | String | N | 20 | 거래량 |

---

## ka30003

**ELWLP보유일별추이요청**

- **메뉴**: 국내주식 > ELW > ELWLP보유일별추이요청(ka30003)
- **Method**: `POST`
- **URL**: `/api/dostk/elw`

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
| `bsis_aset_cd` | 기초자산코드 | String | Y | 12 | 기초자산코드 |
| `base_dt` | 기준일자 | String | Y | 8 | 토큰 지정시 토큰타입("Bearer") 붙혀서 호출 예) Bearer Egicyx... YYYYMMDD |

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
| `elwlpposs_daly_trnsn` | ELWLP보유일별추이 LIST N |  |  |  | ELWLP보유일별추이 LIST N |
| `- dt` | 일자 | String | N | 20 | 일자 |
| `- cur_prc` | 현재가 | String | N | 20 | 현재가 |
| `- pre_tp` | 대비구분 | String | N | 20 | 대비구분 |
| `- pred_pre` | 전일대비 | String | N | 20 | 전일대비 |
| `- flu_rt` | 등락율 | String | N | 20 | 등락율 |
| `- trde_qty` | 거래량 | String | N | 20 | 거래량 |
| `- trde_prica` | 거래대금 | String | N | 20 | 거래대금 |
| `- chg_qty` | 변동수량 | String | N | 20 | 변동수량 |
| `- lprmnd_qty` | LP보유수량 | String | N | 20 | LP보유수량 |

---

## ka30004

**ELW괴리율요청**

- **메뉴**: 국내주식 > ELW > ELW괴리율요청(ka30004)
- **Method**: `POST`
- **URL**: `/api/dostk/elw`

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
| `isscomp_cd` | 발행사코드 | String | Y | 12 | 전체:000000000000, 한국투자증권:3, 미래대우:5, 신영:6, NK투자증권:12, KB증권:17 |
| `bsis_aset_cd` | 기초자산코드 | String | Y | 12 | 전체:000000000000, KOSPI200:201, KOSDAQ150:150, 삼성전자:005930, KT:030200.. |
| `rght_tp` | 권리구분 | String | Y | 3 | 000: 전체, 001: 콜, 002: 풋, 003: DC, 004: DP, 005: EX, 006: 조기종료콜, 007: 조기종료풋 |
| `lpcd` | LP코드 | String | Y | 12 | 전체:000000000000, 한국투자증권:3, 미래대우:5, 신영:6, NK투자증권:12, KB증권:17 |
| `trde_end_elwskip` | 거래종료ELW제외 | String | Y | 1 | 1:거래종료ELW제외, 0:거래종료ELW포함 토큰 지정시 토큰타입("Bearer") 붙혀서 호출 예) Bearer Egicyx... |

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
| `elwdispty_rt` | ELW괴리율 LIST N |  |  |  | ELW괴리율 LIST N |
| `- stk_cd` | 종목코드 | String | N | 20 | 종목코드 |
| `- isscomp_nm` | 발행사명 | String | N | 20 | 발행사명 |
| `- sqnc` | 회차 | String | N | 20 | 회차 |
| `- base_aset_nm` | 기초자산명 | String | N | 20 | 기초자산명 |

---

## ka30005

**ELW조건검색요청**

- **메뉴**: 국내주식 > ELW > ELW조건검색요청(ka30005)
- **Method**: `POST`
- **URL**: `/api/dostk/elw`

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
| `isscomp_cd` | 발행사코드 | String | Y | 12 | 12자리입력(전체:000000000000, 한국투자증권:000,,,3, 미래대우:000,,,5, 신영:000,,,6, NK투자증권:000,,,12, KB증권:000,,,17) |
| `bsis_aset_cd` | 기초자산코드 | String | Y | 12 | 전체일때만 12자리입력(전체:000000000000, KOSPI200:201, KOSDAQ150:150, 삼정전자:005930, KT:030200,,) |
| `rght_tp` | 권리구분 | String | Y | 1 | 0:전체, 1:콜, 2:풋, 3:DC, 4:DP, 5:EX, 6:조기종료콜, 7:조기종료풋 |
| `lpcd` | LP코드 | String | Y | 12 | 전체일때만 12자리입력(전체:000000000000, 한국투자증권:003, 미래대우:005, 신영:006, NK투자증권:012, KB증권:017) |
| `sort_tp` | 정렬구분 | String | Y | 1 | 0:정렬없음, 1:상승율순, 2:상승폭순, 3:하락율순, 4:하락폭순, 5:거래량순, 6:거래대금순, 7:잔존일순 토큰 지정시 토큰타입("Bearer") 붙혀서 호출 예) Bearer Egicyx... |

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
| `elwcnd_qry` | ELW조건검색 LIST N |  |  |  | ELW조건검색 LIST N |
| `- stk_cd` | 종목코드 | String | N | 20 | 종목코드 |
| `- isscomp_nm` | 발행사명 | String | N | 20 | 발행사명 |
| `- sqnc` | 회차 | String | N | 20 | 회차 |

---

## ka30009

**ELW등락율순위요청**

- **메뉴**: 국내주식 > ELW > ELW등락율순위요청(ka30009)
- **Method**: `POST`
- **URL**: `/api/dostk/elw`

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
| `sort_tp` | 정렬구분 | String | Y | 1 | 1:상승률, 2:상승폭, 3:하락률, 4:하락폭 |
| `rght_tp` | 권리구분 | String | Y | 3 | 000:전체, 001:콜, 002:풋, 003:DC, 004:DP, 006:조기종료콜, 007:조기종료풋 |
| `trde_end_skip` | 거래종료제외 | String | Y | 1 | 1:거래종료제외, 0:거래종료포함 토큰 지정시 토큰타입("Bearer") 붙혀서 호출 예) Bearer Egicyx... |

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
| `elwflu_rt_rank` | ELW등락율순위 LIST N |  |  |  | ELW등락율순위 LIST N |
| `- rank` | 순위 | String | N | 20 | 순위 |
| `- stk_cd` | 종목코드 | String | N | 20 | 종목코드 |
| `- stk_nm` | 종목명 | String | N | 40 | 종목명 |
| `- cur_prc` | 현재가 | String | N | 20 | 현재가 |
| `- pre_sig` | 대비기호 | String | N | 20 | 대비기호 |
| `- pred_pre` | 전일대비 | String | N | 20 | 전일대비 |
| `- flu_rt` | 등락률 | String | N | 20 | 등락률 |
| `- sel_req` | 매도잔량 | String | N | 20 | 매도잔량 |

---

## ka30010

**ELW잔량순위요청**

- **메뉴**: 국내주식 > ELW > ELW잔량순위요청(ka30010)
- **Method**: `POST`
- **URL**: `/api/dostk/elw`

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
| `sort_tp` | 정렬구분 | String | Y | 1 | 1:순매수잔량상위, 2: 순매도 잔량상위 |
| `rght_tp` | 권리구분 | String | Y | 3 | 000: 전체, 001: 콜, 002: 풋, 003: DC, 004: DP, 006: 조기종료콜, 007: 조기종료풋 |
| `trde_end_skip` | 거래종료제외 | String | Y | 1 | 1:거래종료제외, 0:거래종료포함 토큰 지정시 토큰타입("Bearer") 붙혀서 호출 예) Bearer Egicyx... |

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
| `elwreq_rank` | ELW잔량순위 LIST N |  |  |  | ELW잔량순위 LIST N |
| `- stk_cd` | 종목코드 | String | N | 20 | 종목코드 |
| `- rank` | 순위 | String | N | 20 | 순위 |
| `- stk_nm` | 종목명 | String | N | 40 | 종목명 |
| `- cur_prc` | 현재가 | String | N | 20 | 현재가 |
| `- pre_sig` | 대비기호 | String | N | 20 | 대비기호 |
| `- pred_pre` | 전일대비 | String | N | 20 | 전일대비 |
| `- flu_rt` | 등락률 | String | N | 20 | 등락률 |
| `- trde_qty` | 거래량 | String | N | 20 | 거래량 |

---

## ka30011

**ELW근접율요청**

- **메뉴**: 국내주식 > ELW > ELW근접율요청(ka30011)
- **Method**: `POST`
- **URL**: `/api/dostk/elw`

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
| `elwalacc_rt` | ELW근접율 LIST N |  |  |  | ELW근접율 LIST N |
| `- stk_cd` | 종목코드 | String | N | 20 | 종목코드 |
| `- stk_nm` | 종목명 | String | N | 40 | 종목명 |
| `- cur_prc` | 현재가 | String | N | 20 | 현재가 |
| `- pre_sig` | 대비기호 | String | N | 20 | 대비기호 |
| `- pred_pre` | 전일대비 | String | N | 20 | 전일대비 |
| `- flu_rt` | 등락율 | String | N | 20 | 등락율 |
| `- acc_trde_qty` | 누적거래량 | String | N | 20 | 누적거래량 |
| `- alacc_rt` | 근접율 | String | N | 20 | 근접율 |

---

## ka30012

**ELW종목상세정보요청**

- **메뉴**: 국내주식 > ELW > ELW종목상세정보요청(ka30012)
- **Method**: `POST`
- **URL**: `/api/dostk/elw`

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
| `aset_cd` | 자산코드 | String | N | 20 | 자산코드 |
| `cur_prc` | 현재가 | String | N | 20 | 현재가 |
| `pred_pre_sig` | 전일대비기호 | String | N | 20 | 전일대비기호 |
| `pred_pre` | 전일대비 | String | N | 20 | 전일대비 |
| `flu_rt` | 등락율 | String | N | 20 | 등락율 |
| `lpmmcm_nm` | LP회원사명 | String | N | 20 | LP회원사명 |
| `lpmmcm_nm_1` | LP회원사명1 | String | N | 20 | LP회원사명1 |
| `lpmmcm_nm_2` | LP회원사명2 | String | N | 20 | LP회원사명2 |
| `elwrght_cntn` | ELW권리내용 | String | N | 20 | ELW권리내용 |
| `elwexpr_evlt_pric` | ELW만기평가가격 | String | N | 20 | ELW만기평가가격 |
| `elwtheory_pric` | ELW이론가 | String | N | 20 | ELW이론가 |

---
