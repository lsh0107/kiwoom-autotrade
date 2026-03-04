# 테마 API

> API 수: 2개

## 목차

- [ka90001 - 테마그룹별요청](#ka90001)
- [ka90002 - 테마구성종목요청](#ka90002)

---

## ka90001

**테마그룹별요청**

- **메뉴**: 국내주식 > 테마 > 테마그룹별요청(ka90001)
- **Method**: `POST`
- **URL**: `/api/dostk/thme`

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
| `qry_tp` | 검색구분 | String | Y | 1 | 0:전체검색, 1:테마검색, 2:종목검색 |
| `stk_cd` | 종목코드 | String | N | 6 | 검색하려는 종목코드 |
| `date_tp` | 날짜구분 | String | Y | 2 | n일전 (1일 ~ 99일 날짜입력) |
| `thema_nm` | 테마명 | String | N | 50 | 검색하려는 테마명 |
| `flu_pl_amt_tp` | 등락수익구분 | String | Y | 1 | 1:상위기간수익률, 2:하위기간수익률, 3:상위등락률, 4:하위등락률 |
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
| `thema_grp` | 테마그룹별 LIST N |  |  |  | 테마그룹별 LIST N |
| `- thema_grp_cd` | 테마그룹코드 | String | N | 20 | 테마그룹코드 |
| `- thema_nm` | 테마명 | String | N | 20 | 테마명 |
| `- stk_num` | 종목수 | String | N | 20 | 종목수 |
| `- flu_sig` | 등락기호 | String | N | 20 | 등락기호 |
| `- flu_rt` | 등락율 | String | N | 20 | 등락율 |

---

## ka90002

**테마구성종목요청**

- **메뉴**: 국내주식 > 테마 > 테마구성종목요청(ka90002)
- **Method**: `POST`
- **URL**: `/api/dostk/thme`

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
| `date_tp` | 날짜구분 | String | N | 1 | 1일 ~ 99일 날짜입력 |
| `thema_grp_cd` | 테마그룹코드 | String | Y | 6 | 테마그룹코드 번호 |
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
| `flu_rt` | 등락률 | String | N | 20 | 등락률 |
| `dt_prft_rt` | 기간수익률 | String | N | 20 | 기간수익률 |
| `thema_comp_stk` | 테마구성종목 LIST N |  |  |  | 테마구성종목 LIST N |
| `- stk_cd` | 종목코드 | String | N | 20 | 종목코드 |
| `- stk_nm` | 종목명 | String | N | 40 | 종목명 |
| `- cur_prc` | 현재가 | String | N | 20 | 현재가 |
| `- flu_sig` | 등락기호 | String | N | 20 | 등락기호 |
| `- pred_pre` | 전일대비 | String | N | 20 | 전일대비 |
| `- flu_rt` | 등락율 | String | N | 20 | 1: 상한가, 2:상승, 3:보합, 4:하한가, 5:하락 |

---

