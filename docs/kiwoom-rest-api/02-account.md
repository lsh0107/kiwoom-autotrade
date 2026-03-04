# 계좌 API

> API 수: 33개

## 목차

- [ka00001 - 계좌번호조회](#ka00001)
- [ka01690 - 일별잔고수익률](#ka01690)
- [ka10072 - 일자별종목별실현손익요청_일자](#ka10072)
- [ka10073 - 일자별종목별실현손익요청_기간](#ka10073)
- [ka10074 - 일자별실현손익요청](#ka10074)
- [ka10075 - 미체결요청](#ka10075)
- [ka10076 - 체결요청](#ka10076)
- [ka10077 - 당일실현손익상세요청](#ka10077)
- [ka10085 - 계좌수익률요청](#ka10085)
- [ka10088 - 미체결 분할주문 상세](#ka10088)
- [ka10170 - 당일매매일지요청](#ka10170)
- [kt00001 - 예수금상세현황요청](#kt00001)
- [kt00002 - 일별추정예탁자산현황요청](#kt00002)
- [kt00003 - 추정자산조회요청](#kt00003)
- [kt00004 - 계좌평가현황요청](#kt00004)
- [kt00005 - 체결잔고요청](#kt00005)
- [kt00007 - 계좌별주문체결내역상세요청](#kt00007)
- [kt00008 - 계좌별익일결제예정내역요청](#kt00008)
- [kt00009 - 계좌별주문체결현황요청](#kt00009)
- [kt00010 - 주문인출가능금액요청](#kt00010)
- [kt00011 - 증거금율별주문가능수량조회요청](#kt00011)
- [kt00012 - 신용보증금율별주문가능수량조회요청](#kt00012)
- [kt00013 - 증거금세부내역조회요청](#kt00013)
- [kt00015 - 위탁종합거래내역요청](#kt00015)
- [kt00016 - 일별계좌수익률상세현황요청](#kt00016)
- [kt00017 - 계좌별당일현황요청](#kt00017)
- [kt00018 - 계좌평가잔고내역요청](#kt00018)
- [kt50020 - 금현물 잔고확인](#kt50020)
- [kt50021 - 금현물 예수금](#kt50021)
- [kt50030 - 금현물 주문체결전체조회](#kt50030)
- [kt50031 - 금현물 주문체결조회](#kt50031)
- [kt50032 - 금현물 거래내역조회](#kt50032)
- [kt50075 - 금현물 미체결조회](#kt50075)

---

## ka00001

**계좌번호조회**

- **메뉴**: 국내주식 > 계좌 > 계좌번호조회(ka00001)
- **Method**: `POST`
- **URL**: `/api/dostk/acnt`

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
| `acctNo` | 계좌번호 | String | N | 20 | 계좌번호 |

---

## ka01690

**일별잔고수익률**

- **메뉴**: 국내주식 > 계좌 > 일별잔고수익률(ka01690)
- **Method**: `POST`
- **URL**: `/api/dostk/acnt`

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
| `qry_dt` | 조회일자 | String | Y | 8 | 토큰 지정시 토큰타입("Bearer") 붙혀서 호출 예) Bearer Egicyx... |

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
| `dt` | 일자 | String | N | 20 | 일자 |
| `tot_buy_amt` | 총 매입가 | String | N | 20 | 총 매입가 |
| `tot_evlt_amt` | 총 평가금액 | String | N | 20 | 총 평가금액 |
| `tot_evltv_prft` | 총 평가손익 | String | N | 20 | 총 평가손익 |
| `tot_prft_rt` | 수익률 | String | N | 20 | 수익률 |
| `dbst_bal` | 예수금 | String | N | 20 | 예수금 |
| `day_stk_asst` | 추정자산 | String | N | 20 | 추정자산 |
| `buy_wght` | 현금비중 | String | N | 20 | 현금비중 |
| `day_bal_rt` | 일별잔고수익률 LIST N |  |  |  | 일별잔고수익률 LIST N |
| `- cur_prc` | 현재가 | String | N | 20 | 현재가 |
| `- stk_cd` | 종목코드 | String | N | 20 | 종목코드 |

---

## ka10072

**일자별종목별실현손익요청_일자**

- **메뉴**: 국내주식 > 계좌 > 일자별종목별실현손익요청_일자(ka10072)
- **Method**: `POST`
- **URL**: `/api/dostk/acnt`

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
| `stk_cd` | 종목코드 | String | N | 6 | 종목코드 |
| `strt_dt` | 시작일자 | String | Y | 8 | 토큰 지정시 토큰타입("Bearer") 붙혀서 호출 예) Bearer Egicyx... YYYYMMDD |

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
| `dt_stk_div_rlzt_pl` | 일자별종목별실현손 익 LIST N |  |  |  | 일자별종목별실현손 익 LIST N |
| `- stk_nm` | 종목명 | String | N | 40 | 종목명 |
| `- cntr_qty` | 체결량 | String | N | 20 | 체결량 |
| `- buy_uv` | 매입단가 | String | N | 20 | 매입단가 |
| `- cntr_pric` | 체결가 | String | N | 20 | 체결가 |
| `- tdy_sel_pl` | 당일매도손익 | String | N | 20 | 당일매도손익 |
| `- pl_rt` | 손익율 | String | N | 20 | 손익율 |
| `- stk_cd` | 종목코드 | String | N | 20 | 종목코드 |
| `- tdy_trde_cmsn` | 당일매매수수료 | String | N | 20 | 당일매매수수료 |
| `- tdy_trde_tax` | 당일매매세금 | String | N | 20 | 당일매매세금 |

---

## ka10073

**일자별종목별실현손익요청_기간**

- **메뉴**: 국내주식 > 계좌 > 일자별종목별실현손익요청_기간(ka10073)
- **Method**: `POST`
- **URL**: `/api/dostk/acnt`

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
| `stk_cd` | 종목코드 | String | N | 6 | 종목코드 |
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
| `dt_stk_rlzt_pl` | 일자별종목별실현손 익 LIST N |  |  |  | 일자별종목별실현손 익 LIST N |
| `- dt` | 일자 | String | N | 20 | 일자 |
| `- tdy_htssel_cmsn` | 당일hts매도수수료 | String | N | 20 | 당일hts매도수수료 |
| `- stk_nm` | 종목명 | String | N | 40 | 종목명 |
| `- cntr_qty` | 체결량 | String | N | 20 | 체결량 |
| `- buy_uv` | 매입단가 | String | N | 20 | 매입단가 |
| `- cntr_pric` | 체결가 | String | N | 20 | 체결가 |
| `- tdy_sel_pl` | 당일매도손익 | String | N | 20 | 당일매도손익 |
| `- pl_rt` | 손익율 | String | N | 20 | 손익율 |

---

## ka10074

**일자별실현손익요청**

- **메뉴**: 국내주식 > 계좌 > 일자별실현손익요청(ka10074)
- **Method**: `POST`
- **URL**: `/api/dostk/acnt`

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
| `strt_dt` | 시작일자 | String | Y | 8 | 시작일자 |
| `end_dt` | 종료일자 | String | Y | 8 | 토큰 지정시 토큰타입("Bearer") 붙혀서 호출 예) Bearer Egicyx... |

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
| `tot_buy_amt` | 총매수금액 | String | N |  | 총매수금액 |
| `tot_sell_amt` | 총매도금액 | String | N |  | 총매도금액 |
| `rlzt_pl` | 실현손익 | String | N |  | 실현손익 |
| `trde_cmsn` | 매매수수료 | String | N |  | 매매수수료 |
| `trde_tax` | 매매세금 | String | N |  | 매매세금 |
| `dt_rlzt_pl` | 일자별실현손익 LIST N |  |  |  | 일자별실현손익 LIST N |
| `- dt` | 일자 | String | N | 20 | 일자 |
| `- buy_amt` | 매수금액 | String | N | 20 | 매수금액 |
| `- sell_amt` | 매도금액 | String | N | 20 | 매도금액 |
| `- tdy_sel_pl` | 당일매도손익 | String | N | 20 | 당일매도손익 |

---

## ka10075

**미체결요청**

- **메뉴**: 국내주식 > 계좌 > 미체결요청(ka10075)
- **Method**: `POST`
- **URL**: `/api/dostk/acnt`

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
| `all_stk_tp` | 전체종목구분 | String | Y | 1 | 0:전체, 1:종목 |
| `trde_tp` | 매매구분 | String | Y | 1 | 0:전체, 1:매도, 2:매수 |
| `stk_cd` | 종목코드 | String | N | 6 | 종목코드 |
| `stex_tp` | 거래소구분 | String | Y | 1 | 토큰 지정시 토큰타입("Bearer") 붙혀서 호출 예) Bearer Egicyx... 0 : 통합, 1 : KRX, 2 : NXT |

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
| `oso` | 미체결 LIST N |  |  |  | 미체결 LIST N |
| `- acnt_no` | 계좌번호 | String | N | 20 | 계좌번호 |
| `- ord_no` | 주문번호 | String | N | 20 | 주문번호 |
| `- mang_empno` | 관리사번 | String | N | 20 | 관리사번 |
| `- stk_cd` | 종목코드 | String | N | 20 | 종목코드 |
| `- tsk_tp` | 업무구분 | String | N | 20 | 업무구분 |
| `- ord_stt` | 주문상태 | String | N | 20 | 주문상태 |
| `- stk_nm` | 종목명 | String | N | 40 | 종목명 |

---

## ka10076

**체결요청**

- **메뉴**: 국내주식 > 계좌 > 체결요청(ka10076)
- **Method**: `POST`
- **URL**: `/api/dostk/acnt`

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
| `stk_cd` | 종목코드 | String | N | 6 | 종목코드 |
| `qry_tp` | 조회구분 | String | Y | 1 | 0:전체, 1:종목 |
| `sell_tp` | 매도수구분 | String | Y | 1 | 0:전체, 1:매도, 2:매수 |
| `ord_no` | 주문번호 | String | N | 10 | 검색 기준 값으로 입력한 주문번호 보다 과거에 체결된 내역이 조회됩니다. |
| `stex_tp` | 거래소구분 | String | Y | 1 | 0 : 통합, 1 : KRX, 2 : NXT 토큰 지정시 토큰타입("Bearer") 붙혀서 호출 예) Bearer Egicyx... |

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
| `cntr` | 체결 LIST N |  |  |  | 체결 LIST N |
| `- ord_no` | 주문번호 | String | N | 20 | 주문번호 |
| `- stk_nm` | 종목명 | String | N | 40 | 종목명 |
| `- io_tp_nm` | 주문구분 | String | N | 20 | 주문구분 |
| `- ord_pric` | 주문가격 | String | N | 20 | 주문가격 |
| `- ord_qty` | 주문수량 | String | N | 20 | 주문수량 |
| `- cntr_pric` | 체결가 | String | N | 20 | 체결가 |

---

## ka10077

**당일실현손익상세요청**

- **메뉴**: 국내주식 > 계좌 > 당일실현손익상세요청(ka10077)
- **Method**: `POST`
- **URL**: `/api/dostk/acnt`

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
| `tdy_rlzt_pl` | 당일실현손익 | String | N |  | 당일실현손익 |
| `tdy_rlzt_pl_dtl` | 당일실현손익상세 LIST N |  |  |  | 당일실현손익상세 LIST N |
| `- stk_nm` | 종목명 | String | N | 40 | 종목명 |
| `- cntr_qty` | 체결량 | String | N | 20 | 체결량 |
| `- buy_uv` | 매입단가 | String | N | 20 | 매입단가 |
| `- cntr_pric` | 체결가 | String | N | 20 | 체결가 |
| `- tdy_sel_pl` | 당일매도손익 | String | N | 20 | 당일매도손익 |
| `- pl_rt` | 손익율 | String | N | 20 | 손익율 |
| `- tdy_trde_cmsn` | 당일매매수수료 | String | N | 20 | 당일매매수수료 |
| `- tdy_trde_tax` | 당일매매세금 | String | N | 20 | 당일매매세금 |
| `- stk_cd` | 종목코드 | String | N | 20 | 종목코드 |

---

## ka10085

**계좌수익률요청**

- **메뉴**: 국내주식 > 계좌 > 계좌수익률요청(ka10085)
- **Method**: `POST`
- **URL**: `/api/dostk/acnt`

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
| `stex_tp` | 거래소구분 | String | Y | 1 | 0 : 통합, 1 : KRX, 2 : NXT 토큰 지정시 토큰타입("Bearer") 붙혀서 호출 예) Bearer Egicyx... |

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
| `acnt_prft_rt` | 계좌수익률 LIST N |  |  |  | 계좌수익률 LIST N |
| `- dt` | 일자 | String | N | 20 | 일자 |
| `- stk_cd` | 종목코드 | String | N | 20 | 종목코드 |
| `- stk_nm` | 종목명 | String | N | 40 | 종목명 |
| `- cur_prc` | 현재가 | String | N | 20 | 현재가 |
| `- pur_pric` | 매입가 | String | N | 20 | 매입가 |
| `- pur_amt` | 매입금액 | String | N | 20 | 매입금액 |
| `- rmnd_qty` | 보유수량 | String | N | 20 | 보유수량 |
| `- tdy_sel_pl` | 당일매도손익 | String | N | 20 | 당일매도손익 |
| `- tdy_trde_cmsn` | 당일매매수수료 | String | N | 20 | 당일매매수수료 |
| `- tdy_trde_tax` | 당일매매세금 | String | N | 20 | 당일매매세금 |

---

## ka10088

**미체결 분할주문 상세**

- **메뉴**: 국내주식 > 계좌 > 미체결 분할주문 상세(ka10088)
- **Method**: `POST`
- **URL**: `/api/dostk/acnt`

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
| `ord_no` | 주문번호 | String | Y | 20 | 토큰 지정시 토큰타입("Bearer") 붙혀서 호출 예) Bearer Egicyx... |

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
| `osop` | 미체결분할주문리스 트 LIST N |  |  |  | 미체결분할주문리스 트 LIST N |
| `- stk_cd` | 종목코드 | String | N | 20 | 종목코드 |
| `- stk_nm` | 종목명 | String | N | 40 | 종목명 |
| `- ord_no` | 주문번호 | String | N | 20 | 주문번호 |
| `- ord_qty` | 주문수량 | String | N | 20 | 주문수량 |
| `- ord_pric` | 주문가격 | String | N | 20 | 주문가격 |
| `- osop_qty` | 미체결수량 | String | N | 20 | 미체결수량 |
| `- io_tp_nm` | 주문구분 | String | N | 20 | 주문구분 |
| `- trde_tp` | 매매구분 | String | N | 20 | 매매구분 |
| `- sell_tp` | 매도/수 구분 | String | N | 20 | 매도/수 구분 |
| `- cntr_qty` | 체결량 | String | N | 20 | 체결량 |

---

## ka10170

**당일매매일지요청**

- **메뉴**: 국내주식 > 계좌 > 당일매매일지요청(ka10170)
- **Method**: `POST`
- **URL**: `/api/dostk/acnt`

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
| `base_dt` | 기준일자 | String | N | 8 | YYYYMMDD(공백입력시 금일데이터,최근 2개월까지 제공) |
| `ottks_tp` | 단주구분 | String | Y | 1 | 1:당일매수에 대한 당일매도,2:당일매도 전체 |
| `ch_crd_tp` | 현금신용구분 | String | Y | 1 | 0:전체, 1:현금매매만, 2:신용매매만 토큰 지정시 토큰타입("Bearer") 붙혀서 호출 예) Bearer Egicyx... |

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
| `tot_sell_amt` | 총매도금액 | String | N |  | 총매도금액 |
| `tot_buy_amt` | 총매수금액 | String | N |  | 총매수금액 |
| `tot_cmsn_tax` | 총수수료_세금 | String | N |  | 총수수료_세금 |
| `tot_exct_amt` | 총정산금액 | String | N |  | 총정산금액 |
| `tot_pl_amt` | 총손익금액 | String | N |  | 총손익금액 |
| `tot_prft_rt` | 총수익률 | String | N |  | 총수익률 |
| `tdy_trde_diary` | 당일매매일지 LIST N |  |  |  | 당일매매일지 LIST N |
| `- stk_nm` | 종목명 | String | N |  | 종목명 |
| `- buy_avg_pric` | 매수평균가 | String | N | 40 | 매수평균가 |

---

## kt00001

**예수금상세현황요청**

- **메뉴**: 국내주식 > 계좌 > 예수금상세현황요청(kt00001)
- **Method**: `POST`
- **URL**: `/api/dostk/acnt`

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
| `qry_tp` | 조회구분 | String | Y | 1 | 3:추정조회, 2:일반조회 토큰 지정시 토큰타입("Bearer") 붙혀서 호출 예) Bearer Egicyx... |

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
| `entr` | 예수금 | String | N | 15 | 예수금 |
| `profa_ch` | 주식증거금현금 | String | N | 15 | 주식증거금현금 |
| `bncr_profa_ch` | 수익증권증거금현금 | String | N | 15 | 수익증권증거금현금 |
| `nxdy_bncr_sell_exct` | 익일수익증권매도정 산대금 | String | N | 15 | 익일수익증권매도정 산대금 |
| `fc_stk_krw_repl_set_a` | mt 해외주식원화대용설 정금 | String | N | 15 | mt 해외주식원화대용설 정금 |
| `crd_grnta_ch` | 신용보증금현금 | String | N | 15 | 신용보증금현금 |
| `crd_grnt_ch` | 신용담보금현금 | String | N | 15 | 신용담보금현금 |
| `add_grnt_ch` | 추가담보금현금 | String | N | 15 | 추가담보금현금 |
| `etc_profa` | 기타증거금 | String | N | 15 | 기타증거금 |
| `uncl_stk_amt` | 미수확보금 | String | N | 15 | 미수확보금 |

---

## kt00002

**일별추정예탁자산현황요청**

- **메뉴**: 국내주식 > 계좌 > 일별추정예탁자산현황요청(kt00002)
- **Method**: `POST`
- **URL**: `/api/dostk/acnt`

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
| `start_dt` | 시작조회기간 | String | Y | 8 | YYYYMMDD |
| `end_dt` | 종료조회기간 | String | Y | 8 | YYYYMMDD 토큰 지정시 토큰타입("Bearer") 붙혀서 호출 예) Bearer Egicyx... |

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
| `daly_prsm_dpst_aset` | _amt_prst 일별추정예탁자산현 황 LIST N |  |  |  | _amt_prst 일별추정예탁자산현 황 LIST N |
| `- dt` | 일자 | String | N | 8 | 일자 |
| `- entr` | 예수금 | String | N | 12 | 예수금 |
| `- grnt_use_amt` | 담보대출금 | String | N | 12 | 담보대출금 |
| `- crd_loan` | 신용융자금 | String | N | 12 | 신용융자금 |
| `- ls_grnt` | 대주담보금 | String | N | 12 | 대주담보금 |
| `- repl_amt` | 대용금 | String | N | 12 | 대용금 |
| `prsm_dpst_aset_amt` | 추정예탁자산 | String | N | 12 | 추정예탁자산 |
| `- prsm_dpst_aset_a` | mt_bncr_skip 추정예탁자산수익증 권제외 | String | N | 12 | mt_bncr_skip 추정예탁자산수익증 권제외 |

---

## kt00003

**추정자산조회요청**

- **메뉴**: 국내주식 > 계좌 > 추정자산조회요청(kt00003)
- **Method**: `POST`
- **URL**: `/api/dostk/acnt`

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
| `qry_tp` | 상장폐지조회구분 | String | Y | 1 | 0:전체, 1:상장폐지종목제외 토큰 지정시 토큰타입("Bearer") 붙혀서 호출 예) Bearer Egicyx... |

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
| `prsm_dpst_aset_amt` | 추정예탁자산 | String | N | 12 | 추정예탁자산 |

---

## kt00004

**계좌평가현황요청**

- **메뉴**: 국내주식 > 계좌 > 계좌평가현황요청(kt00004)
- **Method**: `POST`
- **URL**: `/api/dostk/acnt`

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
| `qry_tp` | 상장폐지조회구분 | String | Y | 1 | 0:전체, 1:상장폐지종목제외 |
| `dmst_stex_tp` | 국내거래소구분 | String | Y | 6 | KRX:한국거래소,NXT:넥스트트레이드 토큰 지정시 토큰타입("Bearer") 붙혀서 호출 예) Bearer Egicyx... |

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
| `acnt_nm` | 계좌명 | String | N | 30 | 계좌명 |
| `brch_nm` | 지점명 | String | N | 30 | 지점명 |
| `entr` | 예수금 | String | N | 12 | 예수금 |
| `d2_entra` | D+2추정예수금 | String | N | 12 | D+2추정예수금 |
| `tot_est_amt` | 유가잔고평가액 | String | N | 12 | 유가잔고평가액 |
| `aset_evlt_amt` | 예탁자산평가액 | String | N | 12 | 예탁자산평가액 |
| `tot_pur_amt` | 총매입금액 | String | N | 12 | 총매입금액 |
| `prsm_dpst_aset_amt` | 추정예탁자산 | String | N | 12 | 추정예탁자산 |
| `tot_grnt_sella` | 매도담보대출금 | String | N | 12 | 매도담보대출금 |
| `tdy_lspft_amt` | 당일투자원금 | String | N | 12 | 당일투자원금 |

---

## kt00005

**체결잔고요청**

- **메뉴**: 국내주식 > 계좌 > 체결잔고요청(kt00005)
- **Method**: `POST`
- **URL**: `/api/dostk/acnt`

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
| `dmst_stex_tp` | 국내거래소구분 | String | Y | 6 | KRX:한국거래소,NXT:넥스트트레이드 토큰 지정시 토큰타입("Bearer") 붙혀서 호출 예) Bearer Egicyx... |

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
| `entr` | 예수금 | String | N | 12 | 예수금 |
| `entr_d1` | 예수금D+1 | String | N | 12 | 예수금D+1 |
| `entr_d2` | 예수금D+2 | String | N | 12 | 예수금D+2 |
| `pymn_alow_amt` | 출금가능금액 | String | N | 12 | 출금가능금액 |
| `uncl_stk_amt` | 미수확보금 | String | N | 12 | 미수확보금 |
| `repl_amt` | 대용금 | String | N | 12 | 대용금 |
| `rght_repl_amt` | 권리대용금 | String | N | 12 | 권리대용금 |
| `ord_alowa` | 주문가능현금 | String | N | 12 | 주문가능현금 |
| `ch_uncla` | 현금미수금 | String | N | 12 | 현금미수금 |
| `crd_int_npay_gold` | 신용이자미납금 | String | N | 12 | 신용이자미납금 |
| `etc_loana` | 기타대여금 | String | N | 12 | 기타대여금 |

---

## kt00007

**계좌별주문체결내역상세요청**

- **메뉴**: 국내주식 > 계좌 > 계좌별주문체결내역상세요청(kt00007)
- **Method**: `POST`
- **URL**: `/api/dostk/acnt`

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
| `ord_dt` | 주문일자 | String | N | 8 | YYYYMMDD |
| `qry_tp` | 조회구분 | String | Y | 1 | 1:주문순, 2:역순, 3:미체결, 4:체결내역만 |
| `stk_bond_tp` | 주식채권구분 | String | Y | 1 | 0:전체, 1:주식, 2:채권 |
| `sell_tp` | 매도수구분 | String | Y | 1 | 0:전체, 1:매도, 2:매수 |
| `stk_cd` | 종목코드 | String | N | 12 | 공백허용 (공백일때 전체종목) |
| `fr_ord_no` | 시작주문번호 | String | N | 7 | 공백허용 (공백일때 전체주문) |
| `dmst_stex_tp` | 국내거래소구분 | String | Y | 6 | %:(전체),KRX:한국거래소,NXT:넥스트트레이드,SOR:최선주문 집행 토큰 지정시 토큰타입("Bearer") 붙혀서 호출 예) Bearer Egicyx... |

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
| `acnt_ord_cntr_prps_` | dtl 계좌별주문체결내역 상세 LIST N |  |  |  | dtl 계좌별주문체결내역 상세 LIST N |
| `- ord_no` | 주문번호 | String | N | 7 | 주문번호 |
| `- stk_cd` | 종목번호 | String | N | 12 | 종목번호 |
| `- trde_tp` | 매매구분 | String | N | 20 | 매매구분 |

---

## kt00008

**계좌별익일결제예정내역요청**

- **메뉴**: 국내주식 > 계좌 > 계좌별익일결제예정내역요청(kt00008)
- **Method**: `POST`
- **URL**: `/api/dostk/acnt`

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
| `strt_dcd_seq` | 시작결제번호 | String | N | 7 | 토큰 지정시 토큰타입("Bearer") 붙혀서 호출 예) Bearer Egicyx... |

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
| `trde_dt` | 매매일자 | String | N | 8 | 매매일자 |
| `setl_dt` | 결제일자 | String | N | 8 | 결제일자 |
| `sell_amt_sum` | 매도정산합 | String | N | 12 | 매도정산합 |
| `buy_amt_sum` | 매수정산합 | String | N | 12 | 매수정산합 |
| `acnt_nxdy_setl_frcs_p` | rps_array 계좌별익일결제예정 내역배열 LIST N |  |  |  | rps_array 계좌별익일결제예정 내역배열 LIST N |
| `- seq` | 일련번호 | String | N | 7 | 일련번호 |
| `- stk_cd` | 종목번호 | String | N | 12 | 종목번호 |
| `- loan_dt` | 대출일 | String | N | 8 | 대출일 |
| `- qty` | 수량 | String | N | 12 | 수량 |
| `- engg_amt` | 약정금액 | String | N | 12 | 약정금액 |
| `- cmsn` | 수수료 | String | N | 12 | 수수료 |

---

## kt00009

**계좌별주문체결현황요청**

- **메뉴**: 국내주식 > 계좌 > 계좌별주문체결현황요청(kt00009)
- **Method**: `POST`
- **URL**: `/api/dostk/acnt`

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
| `ord_dt` | 주문일자 | String | N | 8 | YYYYMMDD |
| `stk_bond_tp` | 주식채권구분 | String | Y | 1 | 0:전체, 1:주식, 2:채권 |
| `mrkt_tp` | 시장구분 | String | Y | 1 | 0:전체, 1:코스피, 2:코스닥, 3:OTCBB, 4:ECN |
| `sell_tp` | 매도수구분 | String | Y | 1 | 0:전체, 1:매도, 2:매수 |
| `qry_tp` | 조회구분 | String | Y | 1 | 0:전체, 1:체결 |
| `stk_cd` | 종목코드 | String | N | 12 | 전문 조회할 종목코드 |
| `fr_ord_no` | 시작주문번호 | String | N | 7 | 시작주문번호 |
| `dmst_stex_tp` | 국내거래소구분 | String | Y | 6 | %:(전체),KRX:한국거래소,NXT:넥스트트레이드,SOR:최선주문 집행 토큰 지정시 토큰타입("Bearer") 붙혀서 호출 예) Bearer Egicyx... |

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
| `sell_grntl_engg_amt` | 매도약정금액 | String | N | 12 | 매도약정금액 |
| `buy_engg_amt` | 매수약정금액 | String | N | 12 | 매수약정금액 |
| `engg_amt` | 약정금액 | String | N | 12 | 약정금액 |
| `acnt_ord_cntr_prst_a` | 계좌별주문체결현황 LIST N |  |  |  | 계좌별주문체결현황 LIST N |

---

## kt00010

**주문인출가능금액요청**

- **메뉴**: 국내주식 > 계좌 > 주문인출가능금액요청(kt00010)
- **Method**: `POST`
- **URL**: `/api/dostk/acnt`

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
| `io_amt` | 입출금액 | String | N | 12 | 입출금액 |
| `stk_cd` | 종목번호 | String | Y | 12 | 종목번호 |
| `trde_tp` | 매매구분 | String | Y | 1 | 매매구분 |
| `trde_qty` | 매매수량 | String | N | 10 | 매매수량 |
| `uv` | 매수가격 | String | Y | 10 | 매수가격 |
| `exp_buy_unp` | 예상매수단가 | String | N | 10 | 토큰 지정시 토큰타입("Bearer") 붙혀서 호출 예) Bearer Egicyx... 1:매도, 2:매수 |

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
| `profa_20ord_alow_a` | mt 증거금20%주문가능 금액 | String | N | 12 | mt 증거금20%주문가능 금액 |
| `profa_20ord_alowq` | 증거금20%주문가능 수량 | String | N | 10 | 증거금20%주문가능 수량 |
| `profa_30ord_alow_a` | mt 증거금30%주문가능 금액 | String | N | 12 | mt 증거금30%주문가능 금액 |
| `profa_30ord_alowq` | 증거금30%주문가능 수량 | String | N | 10 | 증거금30%주문가능 수량 |

---

## kt00011

**증거금율별주문가능수량조회요청**

- **메뉴**: 국내주식 > 계좌 > 증거금율별주문가능수량조회요청(kt00011)
- **Method**: `POST`
- **URL**: `/api/dostk/acnt`

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
| `stk_cd` | 종목번호 | String | Y | 12 | 종목번호 |
| `uv` | 매수가격 | String | N | 10 | 토큰 지정시 토큰타입("Bearer") 붙혀서 호출 예) Bearer Egicyx... |

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
| `stk_profa_rt` | 종목증거금율 | String | N | 15 | 종목증거금율 |
| `profa_rt` | 계좌증거금율 | String | N | 15 | 계좌증거금율 |
| `aplc_rt` | 적용증거금율 | String | N | 15 | 적용증거금율 |
| `profa_20ord_alow_a` | mt 증거금20%주문가능 금액 | String | N | 12 | mt 증거금20%주문가능 금액 |
| `profa_20ord_alowq` | 증거금20%주문가능 수량 | String | N | 12 | 증거금20%주문가능 수량 |
| `profa_20pred_reu_a` | mt 증거금20%전일재사 용금액 | String | N | 12 | mt 증거금20%전일재사 용금액 |
| `profa_20tdy_reu_amt` | 증거금20%금일재사 용금액 | String | N | 12 | 증거금20%금일재사 용금액 |
| `profa_30ord_alow_a` | mt 증거금30%주문가능 금액 | String | N | 12 | mt 증거금30%주문가능 금액 |

---

## kt00012

**신용보증금율별주문가능수량조회요청**

- **메뉴**: 국내주식 > 계좌 > 신용보증금율별주문가능수량조회요청(kt00012)
- **Method**: `POST`
- **URL**: `/api/dostk/acnt`

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
| `stk_cd` | 종목번호 | String | Y | 12 | 종목번호 |
| `uv` | 매수가격 | String | N | 10 | 토큰 지정시 토큰타입("Bearer") 붙혀서 호출 예) Bearer Egicyx... |

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
| `stk_assr_rt` | 종목보증금율 | String | N | 1 | 종목보증금율 |
| `stk_assr_rt_nm` | 종목보증금율명 | String | N | 4 | 종목보증금율명 |
| `assr_30ord_alow_am` | t 보증금30%주문가능 금액 | String | N | 12 | t 보증금30%주문가능 금액 |
| `assr_30ord_alowq` | 보증금30%주문가능 수량 | String | N | 12 | 보증금30%주문가능 수량 |
| `assr_30pred_reu_amt` | 보증금30%전일재사 용금액 | String | N | 12 | 보증금30%전일재사 용금액 |
| `assr_30tdy_reu_amt` | 보증금30%금일재사 용금액 | String | N | 12 | 보증금30%금일재사 용금액 |
| `assr_40ord_alow_am` | t 보증금40%주문가능 금액 | String | N | 12 | t 보증금40%주문가능 금액 |
| `assr_40ord_alowq` | 보증금40%주문가능 | String | N | 12 | 보증금40%주문가능 |

---

## kt00013

**증거금세부내역조회요청**

- **메뉴**: 국내주식 > 계좌 > 증거금세부내역조회요청(kt00013)
- **Method**: `POST`
- **URL**: `/api/dostk/acnt`

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
| `tdy_reu_objt_amt` | 금일재사용대상금액 | String | N | 15 | 금일재사용대상금액 |
| `tdy_reu_use_amt` | 금일재사용사용금액 | String | N | 15 | 금일재사용사용금액 |
| `tdy_reu_alowa` | 금일재사용가능금액 | String | N | 15 | 금일재사용가능금액 |
| `tdy_reu_lmtt_amt` | 금일재사용제한금액 | String | N | 15 | 금일재사용제한금액 |
| `tdy_reu_alowa_fin` | 금일재사용가능금액 최종 | String | N | 15 | 금일재사용가능금액 최종 |
| `pred_reu_objt_amt` | 전일재사용대상금액 | String | N | 15 | 전일재사용대상금액 |
| `pred_reu_use_amt` | 전일재사용사용금액 | String | N | 15 | 전일재사용사용금액 |
| `pred_reu_alowa` | 전일재사용가능금액 | String | N | 15 | 전일재사용가능금액 |
| `pred_reu_lmtt_amt` | 전일재사용제한금액 | String | N | 15 | 전일재사용제한금액 |
| `pred_reu_alowa_fin` | 전일재사용가능금액 최종 | String | N | 15 | 전일재사용가능금액 최종 |
| `ch_amt` | 현금금액 | String | N | 15 | 현금금액 |

---

## kt00015

**위탁종합거래내역요청**

- **메뉴**: 국내주식 > 계좌 > 위탁종합거래내역요청(kt00015)
- **Method**: `POST`
- **URL**: `/api/dostk/acnt`

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
| `strt_dt` | 시작일자 | String | Y | 8 | 시작일자 |
| `end_dt` | 종료일자 | String | Y | 8 | 종료일자 |
| `tp` | String Y 1 |  |  |  | String Y 1 |
| `stk_cd` | 종목코드 | String | N | 12 | 종목코드 |
| `crnc_cd` | 통화코드 | String | N | 3 | 통화코드 |
| `gds_tp` | 상품구분 | String | Y | 1 | 상품구분 |
| `frgn_stex_code` | 해외거래소코드 | String | N | 10 | 해외거래소코드 |
| `dmst_stex_tp` | 국내거래소구분 | String | Y | 6 | 토큰 지정시 토큰타입("Bearer") 붙혀서 호출 예) Bearer Egicyx... 0:전체,1:입출금,2:입출고,3:매매,4:매수,5:매도,6:입금,7:출금,A: 예탁담보대출입금,B:매도담보대출입금,C:현금상환(융자,담보 상환),F:환전,M:입출금+환전,G:외화매수,H:외화매도,I:환전정 산입금,J:환전정산출금 0:전체, 1:국내주식, 2:수익증권, 3:해외주식, 4:금융상품 %:(전체),KRX:한국거래소,NXT:넥스트트레이드 |

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
| `trst_ovrl_trde_prps_a` | rray 위탁종합거래내역배 열 LIST N |  |  |  | rray 위탁종합거래내역배 열 LIST N |
| `- trde_dt` | 거래일자 | String | N | 8 | 거래일자 |

---

## kt00016

**일별계좌수익률상세현황요청**

- **메뉴**: 국내주식 > 계좌 > 일별계좌수익률상세현황요청(kt00016)
- **Method**: `POST`
- **URL**: `/api/dostk/acnt`

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
| `fr_dt` | 평가시작일 | String | Y | 8 | 평가시작일 |
| `to_dt` | 평가종료일 | String | Y | 8 | 토큰 지정시 토큰타입("Bearer") 붙혀서 호출 예) Bearer Egicyx... |

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
| `mang_empno` | 관리사원번호 | String | N | 8 | 관리사원번호 |
| `mngr_nm` | 관리자명 | String | N | 8 | 관리자명 |
| `dept_nm` | 관리자지점 | String | N | 30 | 관리자지점 |
| `entr_fr` | 예수금_초 | String | N | 30 | 예수금_초 |
| `entr_to` | 예수금_말 | String | N | 12 | 예수금_말 |
| `scrt_evlt_amt_fr` | 유가증권평가금액_초 | String | N | 12 | 유가증권평가금액_초 |
| `scrt_evlt_amt_to` | 유가증권평가금액_말 | String | N | 12 | 유가증권평가금액_말 |
| `ls_grnt_fr` | 대주담보금_초 | String | N | 12 | 대주담보금_초 |
| `ls_grnt_to` | 대주담보금_말 | String | N | 12 | 대주담보금_말 |
| `crd_loan_fr` | 신용융자금_초 | String | N | 12 | 신용융자금_초 |

---

## kt00017

**계좌별당일현황요청**

- **메뉴**: 국내주식 > 계좌 > 계좌별당일현황요청(kt00017)
- **Method**: `POST`
- **URL**: `/api/dostk/acnt`

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
| `d2_entra` | D+2추정예수금 | String | N | 12 | D+2추정예수금 |
| `crd_int_npay_gold` | 신용이자미납금 | String | N | 12 | 신용이자미납금 |
| `etc_loana` | 기타대여금 | String | N | 12 | 기타대여금 |
| `gnrl_stk_evlt_amt_d2` | 일반주식평가금액D+ 2 | String | N | 12 | 일반주식평가금액D+ 2 |
| `dpst_grnt_use_amt_d` | 2 예탁담보대출금D+2 | String | N | 12 | 2 예탁담보대출금D+2 |
| `crd_stk_evlt_amt_d2` | 예탁담보주식평가금 액D+2 | String | N | 12 | 예탁담보주식평가금 액D+2 |
| `crd_loan_d2` | 신용융자금D+2 | String | N | 12 | 신용융자금D+2 |
| `crd_loan_evlta_d2` | 신용융자평가금D+2 | String | N | 12 | 신용융자평가금D+2 |
| `crd_ls_grnt_d2` | 신용대주담보금D+2 | String | N | 12 | 신용대주담보금D+2 |
| `crd_ls_evlta_d2` | 신용대주평가금D+2 | String | N | 12 | 신용대주평가금D+2 |
| `ina_amt` | 입금금액 | String | N | 12 | 입금금액 |

---

## kt00018

**계좌평가잔고내역요청**

- **메뉴**: 국내주식 > 계좌 > 계좌평가잔고내역요청(kt00018)
- **Method**: `POST`
- **URL**: `/api/dostk/acnt`

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
| `qry_tp` | 조회구분 | String | Y | 1 | 1:합산, 2:개별 |
| `dmst_stex_tp` | 국내거래소구분 | String | Y | 6 | KRX:한국거래소,NXT:넥스트트레이드 토큰 지정시 토큰타입("Bearer") 붙혀서 호출 예) Bearer Egicyx... |

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
| `tot_pur_amt` | 총매입금액 | String | N | 15 | 총매입금액 |
| `tot_evlt_amt` | 총평가금액 | String | N | 15 | 총평가금액 |
| `tot_evlt_pl` | 총평가손익금액 | String | N | 15 | 총평가손익금액 |
| `tot_prft_rt` | 총수익률(%) | String | N | 12 | 총수익률(%) |
| `prsm_dpst_aset_amt` | 추정예탁자산 | String | N | 15 | 추정예탁자산 |
| `tot_loan_amt` | 총대출금 | String | N | 15 | 총대출금 |
| `tot_crd_loan_amt` | 총융자금액 | String | N | 15 | 총융자금액 |
| `tot_crd_ls_amt` | 총대주금액 | String | N | 15 | 총대주금액 |
| `acnt_evlt_remn_indv_` | tot 계좌평가잔고개별합 산 LIST N |  |  |  | tot 계좌평가잔고개별합 산 LIST N |
| `- stk_cd` | 종목번호 | String | N | 12 | 종목번호 |

---

## kt50020

**금현물 잔고확인**

- **메뉴**: 국내주식 > 계좌 > 금현물 잔고확인(kt50020)
- **Method**: `POST`
- **URL**: `/api/dostk/acnt`

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
| `tot_entr` | 예수금 | String | N | 12 | 예수금 |
| `net_entr` | 추정예수금 | String | N | 12 | 추정예수금 |
| `tot_est_amt` | 잔고평가액 | String | N | 12 | 잔고평가액 |
| `net_amt` | 예탁자산평가액 | String | N | 12 | 예탁자산평가액 |
| `tot_book_amt2` | 총매입금액 | String | N | 12 | 총매입금액 |
| `tot_dep_amt` | 추정예탁자산 | String | N | 12 | 추정예탁자산 |
| `paym_alowa` | 출금가능금액 | String | N | 12 | 출금가능금액 |
| `pl_amt` | 실현손익 | String | N | 12 | 실현손익 |
| `gold_acnt_evlt_prst` | 금현물계좌평가현황 LIST N |  |  |  | 금현물계좌평가현황 LIST N |
| `- stk_cd` | 종목코드 | String | N | 30 | 종목코드 |
| `- stk_nm` | 종목명 | String | N | 12 | 종목명 |
| `- real_qty` | 보유수량 | String | N | 12 | 보유수량 |

---

## kt50021

**금현물 예수금**

- **메뉴**: 국내주식 > 계좌 > 금현물 예수금(kt50021)
- **Method**: `POST`
- **URL**: `/api/dostk/acnt`

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
| `entra` | 예수금 | String | N | 15 | 예수금 |
| `profa_ch` | 증거금현금 | String | N | 15 | 증거금현금 |
| `chck_ina_amt` | 수표입금액 | String | N | 15 | 수표입금액 |
| `etc_loan` | 기타대여금 | String | N | 15 | 기타대여금 |
| `etc_loan_dlfe` | 기타대여금연체료 | String | N | 15 | 기타대여금연체료 |
| `etc_loan_tot` | 기타대여금합계 | String | N | 15 | 기타대여금합계 |
| `prsm_entra` | 추정예수금 | String | N | 15 | 추정예수금 |
| `buy_exct_amt` | 매수정산금 | String | N | 15 | 매수정산금 |
| `sell_exct_amt` | 매도정산금 | String | N | 15 | 매도정산금 |
| `sell_buy_exct_amt` | 매도매수정산금 | String | N | 15 | 매도매수정산금 |
| `dly_amt` | 미수변제소요금 | String | N | 15 | 미수변제소요금 |
| `prsm_pymn_alow_a` | mt 추정출금가능금액 | String | N | 15 | mt 추정출금가능금액 |

---

## kt50030

**금현물 주문체결전체조회**

- **메뉴**: 국내주식 > 계좌 > 금현물 주문체결전체조회(kt50030)
- **Method**: `POST`
- **URL**: `/api/dostk/acnt`

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
| `ord_dt` | 주문일자 | String | Y | 8 | 주문일자 |
| `qry_tp` | 조회구분 | String | N | 1 | 조회구분 |
| `mrkt_deal_tp` | 시장구분 | String | Y | 1 | 시장구분 |
| `stk_bond_tp` | 주식채권구분 | String | Y | 1 | 0:전체, 1:주식, 2:채권 |
| `slby_tp` | 매도수구분 | String | Y | 1 | 0:전체, 1:매도, 2:매수 |
| `stk_cd` | 종목코드 | String | N | 12 | 종목코드 |
| `fr_ord_no` | 시작주문번호 | String | N | 7 | 시작주문번호 |
| `dmst_stex_tp` | 국내거래소구분 | String | N | 6 | 토큰 지정시 토큰타입("Bearer") 붙혀서 호출 예) Bearer Egicyx... 1: 주문순, 2: 역순 %:(전체), KRX, NXT, SOR |

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
| `acnt_ord_cntr_prst` | 계좌별주문체결현황 LIST N |  |  |  | 계좌별주문체결현황 LIST N |
| `- stk_bond_tp` | 주식채권구분 | String | N | 1 | 주식채권구분 |
| `- ord_no` | 주문번호 | String | N | 7 | 주문번호 |
| `- stk_cd` | 상품코드 | String | N | 12 | 상품코드 |

---

## kt50031

**금현물 주문체결조회**

- **메뉴**: 국내주식 > 계좌 > 금현물 주문체결조회(kt50031)
- **Method**: `POST`
- **URL**: `/api/dostk/acnt`

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
| `ord_dt` | 주문일자 | String | N | 8 | YYYYMMDD |
| `qry_tp` | 조회구분 | String | Y | 1 | 1:주문순, 2:역순, 3:미체결, 4:체결내역만 |
| `stk_bond_tp` | 주식채권구분 | String | Y | 1 | 0:전체, 1:주식, 2:채권 |
| `sell_tp` | 매도수구분 | String | Y | 1 | 0:전체, 1:매도, 2:매수 |
| `stk_cd` | 종목코드 | String | N | 12 | 공백허용 (공백일때 전체종목) |
| `fr_ord_no` | 시작주문번호 | String | N | 7 | 공백허용 (공백일때 전체주문) |
| `dmst_stex_tp` | 국내거래소구분 | String | Y | 6 | %:(전체),KRX:한국거래소,NXT:넥스트트레이드,SOR:최선주문 집행 토큰 지정시 토큰타입("Bearer") 붙혀서 호출 예) Bearer Egicyx... |

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
| `acnt_ord_cntr_prps_` | dtl 계좌별주문체결내역 상세 LIST N |  |  |  | dtl 계좌별주문체결내역 상세 LIST N |
| `- ord_no` | 주문번호 | String | N | 7 | 주문번호 |
| `- stk_cd` | 종목번호 | String | N | 12 | 종목번호 |
| `- trde_tp` | 매매구분 | String | N | 20 | 매매구분 |

---

## kt50032

**금현물 거래내역조회**

- **메뉴**: 국내주식 > 계좌 > 금현물 거래내역조회(kt50032)
- **Method**: `POST`
- **URL**: `/api/dostk/acnt`

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
| `strt_dt` | 시작일자 | String | N | 8 | 시작일자 |
| `end_dt` | 종료일자 | String | N | 8 | 종료일자 |
| `tp` | String N 1 |  |  |  | String N 1 |
| `stk_cd` | 종목코드 | String | N | 12 | 토큰 지정시 토큰타입("Bearer") 붙혀서 호출 예) Bearer Egicyx... 0:전체, 1:입출금, 2:출고, 3:매매, 4:매수, 5:매도, 6:입금, 7:출금 |

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
| `acnt_print` | 계좌번호 | String | N | 62 | 계좌번호 출력용 |
| `gold_trde_hist` | 금현물거래내역 LIST N |  |  |  | 금현물거래내역 LIST N |
| `- deal_dt` | 거래일자 | String | N |  | 거래일자 |
| `- deal_no` | 거래번호 | String | N |  | 거래번호 |
| `- rmrk_nm` | 적요명 | String | N |  | 적요명 |
| `- deal_qty` | 거래수량 | String | N |  | 거래수량 |
| `- gold_spot_vat` | 금현물부가가치세 | String | N |  | 금현물부가가치세 |
| `- exct_amt` | 정산금액 | String | N |  | 정산금액 |

---

## kt50075

**금현물 미체결조회**

- **메뉴**: 국내주식 > 계좌 > 금현물 미체결조회(kt50075)
- **Method**: `POST`
- **URL**: `/api/dostk/acnt`

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
| `ord_dt` | 주문일자 | String | Y | 8 | 주문일자 |
| `qry_tp` | 조회구분 | String | N | 1 | 조회구분 |
| `mrkt_deal_tp` | 시장구분 | String | Y | 1 | 시장구분 |
| `stk_bond_tp` | 주식채권구분 | String | Y | 1 | 0:전체, 1:주식, 2:채권 |
| `sell_tp` | 매도수구분 | String | Y | 1 | 0:전체, 1:매도, 2:매수 |
| `stk_cd` | 종목코드 | String | N | 12 | 종목코드 |
| `fr_ord_no` | 시작주문번호 | String | N | 7 | 시작주문번호 |
| `dmst_stex_tp` | 국내거래소구분 | String | N | 6 | 토큰 지정시 토큰타입("Bearer") 붙혀서 호출 예) Bearer Egicyx... 1: 주문순, 2: 역순 %:(전체), KRX, NXT, SOR |

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
| `acnt_ord_oso_prst` | 계좌별주문미체결현 황 LIST N |  |  |  | 계좌별주문미체결현 황 LIST N |
| `- stk_bond_tp` | 주식채권구분 | String | N | 1 | 주식채권구분 |
| `- ord_no` | 주문번호 | String | N | 7 | 주문번호 |
| `- stk_cd` | 상품코드 | String | N | 12 | 상품코드 |

---

