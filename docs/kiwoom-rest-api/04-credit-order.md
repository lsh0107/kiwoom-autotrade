# 신용주문 API

> API 수: 4개

## 목차

- [kt10006 - 신용 매수주문](#kt10006)
- [kt10007 - 신용 매도주문](#kt10007)
- [kt10008 - 신용 정정주문](#kt10008)
- [kt10009 - 신용 취소주문](#kt10009)

---

## kt10006

**신용 매수주문**

- **메뉴**: 국내주식 > 신용주문 > 신용 매수주문(kt10006)
- **Method**: `POST`
- **URL**: `/api/dostk/crdordr`

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
| `dmst_stex_tp` | 국내거래소구분 | String | Y | 3 | KRX,NXT,SOR |
| `stk_cd` | 종목코드 | String | Y | 12 | 종목코드 |
| `ord_qty` | 주문수량 | String | Y | 12 | 주문수량 |
| `ord_uv` | 주문단가 | String | N | 12 | 주문단가 |
| `trde_tp` | 매매구분 | String | Y | 2 | 매매구분 |
| `cond_uv` | 조건단가 | String | N | 12 | 토큰 지정시 토큰타입("Bearer") 붙혀서 호출 예) Bearer Egicyx... 0:보통 , 3:시장가 , 5:조건부지정가 , 81:장마감후시간외 , 61:장시작전시간외, 62:시간외단일가 , 6:최유리지정가 , 7:최우선지정가 , 10:보통(IOC) , 13:시장가(IOC) , 16:최유리(IOC) , 20:보통(FOK) , 23:시장가(FOK) , 26:최유리(FOK) , 28:스톱지정가,29:중간가,30:중간가(IOC),31:중간가(FOK) |

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
| `ord_no` | 주문번호 | String | N | 7 | 주문번호 |
| `dmst_stex_tp` | 국내거래소구분 | String | N | 6 | 국내거래소구분 |

---

## kt10007

**신용 매도주문**

- **메뉴**: 국내주식 > 신용주문 > 신용 매도주문(kt10007)
- **Method**: `POST`
- **URL**: `/api/dostk/crdordr`

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
| `dmst_stex_tp` | 국내거래소구분 | String | Y | 3 | KRX,NXT,SOR |
| `stk_cd` | 종목코드 | String | Y | 12 | 종목코드 |
| `ord_qty` | 주문수량 | String | Y | 12 | 주문수량 |
| `ord_uv` | 주문단가 | String | N | 12 | 토큰 지정시 토큰타입("Bearer") 붙혀서 호출 예) Bearer Egicyx... |
| `trde_tp` | 매매구분 | String | Y | 2 | 0:보통 , 3:시장가 , 5:조건부지정가 , 81:장마감후시간외 , 61:장시작전시간외, 62:시간외단일가 , 6:최유리지정가 , 7:최우선지정가 , 10:보통(IOC) , 13:시장가(IOC) , 16:최유리(IOC) , 20:보통(FOK) , 23:시장가(FOK) , 26:최유리(FOK) , 28:스톱지정가,29:중간가,30:중간가(IOC),31:중간가(FOK) |
| `crd_deal_tp` | 신용거래구분 | String | Y | 2 | 33:융자 , 99:융자합 |
| `crd_loan_dt` | 대출일 | String | N | 8 | YYYYMMDD(융자일경우필수) |
| `cond_uv` | 조건단가 | String | N | 12 | 조건단가 |

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
| `ord_no` | 주문번호 | String | N | 7 | 주문번호 |
| `dmst_stex_tp` | 국내거래소구분 | String | N | 6 | 국내거래소구분 |

---

## kt10008

**신용 정정주문**

- **메뉴**: 국내주식 > 신용주문 > 신용 정정주문(kt10008)
- **Method**: `POST`
- **URL**: `/api/dostk/crdordr`

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
| `dmst_stex_tp` | 국내거래소구분 | String | Y | 3 | KRX,NXT,SOR |
| `orig_ord_no` | 원주문번호 | String | Y | 7 | 원주문번호 |
| `stk_cd` | 종목코드 | String | Y | 12 | 종목코드 |
| `mdfy_qty` | 정정수량 | String | Y | 12 | 정정수량 |
| `mdfy_uv` | 정정단가 | String | Y | 12 | 정정단가 |
| `mdfy_cond_uv` | 정정조건단가 | String | N | 12 | 토큰 지정시 토큰타입("Bearer") 붙혀서 호출 예) Bearer Egicyx... |

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
| `ord_no` | 주문번호 | String | N | 7 | 주문번호 |
| `base_orig_ord_no` | 모주문번호 | String | N | 7 | 모주문번호 |
| `mdfy_qty` | 정정수량 | String | N | 12 | 정정수량 |
| `dmst_stex_tp` | 국내거래소구분 | String | N | 6 | 국내거래소구분 |

---

## kt10009

**신용 취소주문**

- **메뉴**: 국내주식 > 신용주문 > 신용 취소주문(kt10009)
- **Method**: `POST`
- **URL**: `/api/dostk/crdordr`

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
| `dmst_stex_tp` | 국내거래소구분 | String | Y | 3 | KRX,NXT,SOR |
| `orig_ord_no` | 원주문번호 | String | Y | 7 | 원주문번호 |
| `stk_cd` | 종목코드 | String | Y | 12 | 종목코드 |
| `cncl_qty` | 취소수량 | String | Y | 12 | 토큰 지정시 토큰타입("Bearer") 붙혀서 호출 예) Bearer Egicyx... '0' 입력시 잔량 전부 취소 |

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
| `ord_no` | 주문번호 | String | N | 7 | 주문번호 |
| `base_orig_ord_no` | 모주문번호 | String | N | 7 | 모주문번호 |
| `cncl_qty` | 취소수량 | String | N | 12 | 취소수량 |

---
