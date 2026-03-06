# 실시간(WebSocket) API

> API 수: 23개

## 목차

- [ka10171 - 조건검색 목록조회](#ka10171)
- [ka10172 - 조건검색 요청 일반](#ka10172)
- [ka10173 - 조건검색 요청 실시간](#ka10173)
- [ka10174 - 조건검색 실시간 해제](#ka10174)
- [00 - 주문체결](#00)
- [04 - 잔고](#04)
- [0A - 주식기세](#0A)
- [0B - 주식체결](#0B)
- [0C - 주식우선호가](#0C)
- [0D - 주식호가잔량](#0D)
- [0E - 주식시간외호가](#0E)
- [0F - 주식당일거래원](#0F)
- [0G - ETF NAV](#0G)
- [0H - 주식예상체결](#0H)
- [0I - 국제금환산가격](#0I)
- [0J - 업종지수](#0J)
- [0U - 업종등락](#0U)
- [0g - 주식종목정보](#0g)
- [0m - ELW 이론가](#0m)
- [0s - 장시작시간](#0s)
- [0u - ELW 지표](#0u)
- [0w - 종목프로그램매매](#0w)
- [1h - VI발동/해제](#1h)

---

## ka10171

**조건검색 목록조회**

- **메뉴**: 국내주식 > 조건검색 > 조건검색 목록조회(ka10171)
- **Method**: `POST`
- **URL**: `/api/dostk/websocket`

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
| `trnm` | TR명 | String | Y | 7 | CNSRLST고정값 토큰 지정시 토큰타입("Bearer") 붙혀서 호출 예) Bearer Egicyx... |

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
| `return_code` | 결과코드 | String | N |  | 정상 : 0 |
| `return_msg` | 결과메시지 | String | N |  | 정상인 경우는 메시지 없음 |
| `trnm` | 서비스명 | String | N |  | 서비스명 |
| `data` | 조건검색식 목록 LIST N |  |  |  | 조건검색식 목록 LIST N |
| `- seq` | 조건검색식 일련번호 | String | N |  | 조건검색식 일련번호 |
| `- name` | 조건검색식 명 | String | N |  | 조건검색식 명 |

---

## ka10172

**조건검색 요청 일반**

- **메뉴**: 국내주식 > 조건검색 > 조건검색 요청 일반(ka10172)
- **Method**: `POST`
- **URL**: `/api/dostk/websocket`

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
| `trnm` | 서비스명 | String | Y | 7 | CNSRREQ 고정값 |
| `seq` | 조건검색식 일련번호 | String | Y | 3 | 조건검색식 일련번호 |
| `search_type` | 조회타입 | String | Y |  | 조회타입 |
| `stex_tp` | 거래소구분 | String | Y | 1 | K:KRX |
| `cont_yn` | 연속조회여부 | String | N | 1 | Y:연속조회요청,N:연속조회미요청 |
| `next_key` | 연속조회키 | String | N | 20 | 토큰 지정시 토큰타입("Bearer") 붙혀서 호출 예) Bearer Egicyx... 0:조건검색 |

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
| `return_code` | 결과코드 | String | N |  | 정상:0 나머지:에러 |
| `return_msg` | 결과메시지 | String | N |  | 정상인 경우는 메시지 없음 |
| `trnm` | 서비스명 | String | N |  | CNSRREQ |
| `seq` | 조건검색식 일련번호 | String | N |  | 조건검색식 일련번호 |
| `cont_yn` | 연속조회여부 | String | N |  | 연속 데이터가 존재하는경우 Y, 없으면 N |
| `next_key` | 연속조회키 | String | N |  | 연속조회여부가Y일경우 다음 조회시 필요한 조회값 |

---

## ka10173

**조건검색 요청 실시간**

- **메뉴**: 국내주식 > 조건검색 > 조건검색 요청 실시간(ka10173)
- **Method**: `POST`
- **URL**: `/api/dostk/websocket`

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
| `trnm` | 서비스명 | String | Y | 7 | CNSRREQ 고정값 |
| `seq` | 조건검색식 일련번호 | String | Y | 3 | 조건검색식 일련번호 |
| `search_type` | 조회타입 | String | Y | 1 | 1: 조건검색+실시간조건검색 |
| `stex_tp` | 거래소구분 | String | Y | 1 | K:KRX 토큰 지정시 토큰타입("Bearer") 붙혀서 호출 예) Bearer Egicyx... |

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
| `조회 데이터` |  |  |  |  |  |
| `return_code` | 결과코드 | String | N |  | 정상:0 나머지:에러 |
| `return_msg` | 결과메시지 | String | N |  | 정상인 경우는 메시지 없음 |
| `trnm` | 서비스명 | String | N |  | CNSRREQ |
| `seq` | 조건검색식 일련번호 | String | N |  | 조건검색식 일련번호 |
| `data` | 검색결과데이터 LIST N |  |  |  | 검색결과데이터 LIST N |
| `- jmcode` | 종목코드 | String | N |  | 종목코드 |
| `실시간 데이터` |  |  |  |  |  |

---

## ka10174

**조건검색 실시간 해제**

- **메뉴**: 국내주식 > 조건검색 > 조건검색 실시간 해제(ka10174)
- **Method**: `POST`
- **URL**: `/api/dostk/websocket`

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
| `trnm` | 서비스명 | String | Y | 7 | CNSRCLR 고정값 |
| `seq` | 조건검색식 일련번호 | String | Y |  | 토큰 지정시 토큰타입("Bearer") 붙혀서 호출 예) Bearer Egicyx... |

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
| `return_code` | 결과코드 | String | Y |  | 정상:0 나머지:에러 |
| `return_msg` | 결과메시지 | String | Y |  | 정상인 경우는 메시지 없음 |
| `trnm` | 서비스명 | String | Y |  | CNSRCLR 고정값 |
| `seq` | 조건검색식 일련번호 | String | Y |  | 조건검색식 일련번호 |

---

## 00

**주문체결**

- **메뉴**: 국내주식 > 실시간시세 > 주문체결(00)
- **Method**: `POST`
- **URL**: `/api/dostk/websocket`

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
| `trnm` | 서비스명 | String | Y | 10 | REG : 등록 , REMOVE : 해지 |
| `grp_no` | 그룹번호 | String | Y | 4 | 토큰 지정시 토큰타입("Bearer") 붙혀서 호출 예) Bearer Egicyx... 등록(REG)시 0:기존유지안함 1:기존유지(Default) |
| `refresh` | 기존등록유지여부 | String | Y | 1 | 0일경우 기존등록한 item/type은 해지, 1일경우 기존등록한 item/type 유지 해지(REMOVE)시 값 불필요 |
| `data` | 실시간 등록 리스트 LIST |  |  |  | 실시간 등록 리스트 LIST |
| `- item` | 실시간 등록 요소 | String | N | 100 | 실시간 등록 요소 |
| `- type` | 실시간 항목 | String | Y | 2 | TR 명(0A,0B....) |

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
| `return_code` | 결과코드 | String | N |  | 통신결과에대한 코드 (등록,해지요청시에만 값 전송 0:정상,1:오류 , 데이터 실시간 |

---

## 04

**잔고**

- **메뉴**: 국내주식 > 실시간시세 > 잔고(04)
- **Method**: `POST`
- **URL**: `/api/dostk/websocket`

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
| `trnm` | 서비스명 | String | Y | 10 | REG : 등록 , REMOVE : 해지 |
| `grp_no` | 그룹번호 | String | Y | 4 | 토큰 지정시 토큰타입("Bearer") 붙혀서 호출 예) Bearer Egicyx... 등록(REG)시 0:기존유지안함 1:기존유지(Default) |
| `refresh` | 기존등록유지여부 | String | Y | 1 | 0일경우 기존등록한 item/type은 해지, 1일경우 기존등록한 item/type 유지 해지(REMOVE)시 값 불필요 |
| `data` | 실시간 등록 리스트 LIST |  |  |  | 실시간 등록 리스트 LIST |
| `- item` | 실시간 등록 요소 | String | N | 104 | 실시간 등록 요소 |
| `- type` | 실시간 항목 | String | Y | 2 | TR 명(0A,0B....) |

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
| `return_code` | 결과코드 | String | N |  | 통신결과에대한 코드 (등록,해지요청시에만 값 전송 0:정상,1:오류 , 데이터 실시간 수신시 미전송) |
| `return_msg` | 결과메시지 | String | N |  | 통신결과에대한메시지 |

---

## 0A

**주식기세**

- **메뉴**: 국내주식 > 실시간시세 > 주식기세(0A)
- **Method**: `POST`
- **URL**: `/api/dostk/websocket`

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
| `trnm` | 서비스명 | String | Y | 10 | REG : 등록 , REMOVE : 해지 |
| `grp_no` | 그룹번호 | String | Y | 4 | 토큰 지정시 토큰타입("Bearer") 붙혀서 호출 예) Bearer Egicyx... 등록(REG)시 0:기존유지안함 1:기존유지(Default) |
| `refresh` | 기존등록유지여부 | String | Y | 1 | 0일경우 기존등록한 item/type은 해지, 1일경우 기존등록한 item/type 유지 해지(REMOVE)시 값 불필요 |
| `data` | 실시간 등록 리스트 LIST |  |  |  | 실시간 등록 리스트 LIST |
| `- item` | 실시간 등록 요소 | String | N | 100 | 거래소별 종목코드, 업종코드 (KRX:039490,NXT:039490_NX,SOR:039490_AL) |
| `- type` | 실시간 항목 | String | Y | 2 | TR 명(0A,0B....) |

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
| `return_code` | 결과코드 | String | N |  | 통신결과에대한 코드 (등록,해지요청시에만 값 전송 0:정상,1:오류 , 데이터 실시간 수신시 미전송) |

---

## 0B

**주식체결**

- **메뉴**: 국내주식 > 실시간시세 > 주식체결(0B)
- **Method**: `POST`
- **URL**: `/api/dostk/websocket`

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
| `trnm` | 서비스명 | String | Y | 10 | REG : 등록 , REMOVE : 해지 |
| `grp_no` | 그룹번호 | String | Y | 4 | 토큰 지정시 토큰타입("Bearer") 붙혀서 호출 예) Bearer Egicyx... Y 1 등록(REG)시 0:기존유지안함 1:기존유지(Default) 0일경우 기존등록한 item/type은 해지, 1일경우 기존등록한 item/type 유지 해지(REMOVE)시 값 불필요 String N 100 거래소별 종목코드, 업종코드 (KRX:039490,NXT:039490_NX,SOR:039490_AL) String Y 2 TR 명(0A,0B....) |
| `refresh` | 기존등록유지여부 | String |  |  | 기존등록유지여부 |
| `data` | 실시간 등록 리스트 LIST |  |  |  | 실시간 등록 리스트 LIST |
| `- item` | 실시간 등록 요소 |  |  |  | 실시간 등록 요소 |
| `- type` | 실시간 항목 |  |  |  | 실시간 항목 |

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
| `return_code` | 결과코드 | String | N |  | 통신결과에대한 코드 (등록,해지요청시에만 값 전송 0:정상,1:오류 , 데이터 실시간 수신시 미전송) |
| `return_msg` | 결과메시지 | String | N |  | 통신결과에대한메시지 |
| `trnm` | 서비스명 | String | N |  | 등록,해지요청시 요청값 반환 , 실시간수신시 REAL 반환 |

---

## 0C

**주식우선호가**

- **메뉴**: 국내주식 > 실시간시세 > 주식우선호가(0C)
- **Method**: `POST`
- **URL**: `/api/dostk/websocket`

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
| `trnm` | 서비스명 | String | Y | 10 | REG : 등록 , REMOVE : 해지 |
| `grp_no` | 그룹번호 | String | Y | 4 | 토큰 지정시 토큰타입("Bearer") 붙혀서 호출 예) Bearer Egicyx... Y 1 등록(REG)시 0:기존유지안함 1:기존유지(Default) 0일경우 기존등록한 item/type은 해지, 1일경우 기존등록한 item/type 유지 해지(REMOVE)시 값 불필요 String N 100 거래소별 종목코드, 업종코드 (KRX:039490,NXT:039490_NX,SOR:039490_AL) String Y 2 TR 명(0A,0B....) |
| `refresh` | 기존등록유지여부 | String |  |  | 기존등록유지여부 |
| `data` | 실시간 등록 리스트 LIST |  |  |  | 실시간 등록 리스트 LIST |
| `- item` | 실시간 등록 요소 |  |  |  | 실시간 등록 요소 |
| `- type` | 실시간 항목 |  |  |  | 실시간 항목 |

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
| `return_code` | 결과코드 | String | N |  | 통신결과에대한 코드 (등록,해지요청시에만 값 전송 0:정상,1:오류 , 데이터 실시간 수신시 미전송) |
| `return_msg` | 결과메시지 | String | N |  | 통신결과에대한메시지 |
| `trnm` | 서비스명 | String | N |  | 등록,해지요청시 요청값 반환 , 실시간수신시 REAL 반환 |

---

## 0D

**주식호가잔량**

- **메뉴**: 국내주식 > 실시간시세 > 주식호가잔량(0D)
- **Method**: `POST`
- **URL**: `/api/dostk/websocket`

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
| `trnm` | 서비스명 | String | Y | 10 | REG : 등록 , REMOVE : 해지 |
| `grp_no` | 그룹번호 | String | Y | 4 | 토큰 지정시 토큰타입("Bearer") 붙혀서 호출 예) Bearer Egicyx... Y 1 등록(REG)시 0:기존유지안함 1:기존유지(Default) 0일경우 기존등록한 item/type은 해지, 1일경우 기존등록한 item/type 유지 해지(REMOVE)시 값 불필요 String N 100 거래소별 종목코드, 업종코드 (KRX:039490,NXT:039490_NX,SOR:039490_AL) String Y 2 TR 명(0A,0B....) |
| `refresh` | 기존등록유지여부 | String |  |  | 기존등록유지여부 |
| `data` | 실시간 등록 리스트 LIST |  |  |  | 실시간 등록 리스트 LIST |
| `- item` | 실시간 등록 요소 |  |  |  | 실시간 등록 요소 |
| `- type` | 실시간 항목 |  |  |  | 실시간 항목 |

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
| `return_code` | 결과코드 | String | N |  | 통신결과에대한 코드 (등록,해지요청시에만 값 전송 0:정상,1:오류 , 데이터 실시간 수신시 미전송) |
| `return_msg` | 결과메시지 | String | N |  | 통신결과에대한메시지 |
| `trnm` | 서비스명 | String | N |  | 등록,해지요청시 요청값 반환 , 실시간수신시 REAL 반환 |

---

## 0E

**주식시간외호가**

- **메뉴**: 국내주식 > 실시간시세 > 주식시간외호가(0E)
- **Method**: `POST`
- **URL**: `/api/dostk/websocket`

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
| `trnm` | 서비스명 | String | Y | 10 | REG : 등록 , REMOVE : 해지 |
| `grp_no` | 그룹번호 | String | Y | 4 | 토큰 지정시 토큰타입("Bearer") 붙혀서 호출 예) Bearer Egicyx... Y 1 등록(REG)시 0:기존유지안함 1:기존유지(Default) 0일경우 기존등록한 item/type은 해지, 1일경우 기존등록한 item/type 유지 해지(REMOVE)시 값 불필요 String N 100 거래소별 종목코드, 업종코드 (KRX:039490,NXT:039490_NX,SOR:039490_AL) String Y 2 TR 명(0A,0B....) |
| `refresh` | 기존등록유지여부 | String |  |  | 기존등록유지여부 |
| `data` | 실시간 등록 리스트 LIST |  |  |  | 실시간 등록 리스트 LIST |
| `- item` | 실시간 등록 요소 |  |  |  | 실시간 등록 요소 |
| `- type` | 실시간 항목 |  |  |  | 실시간 항목 |

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
| `return_code` | 결과코드 | String | N |  | 통신결과에대한 코드 (등록,해지요청시에만 값 전송 0:정상,1:오류 , 데이터 실시간 수신시 미전송) |
| `return_msg` | 결과메시지 | String | N |  | 통신결과에대한메시지 |
| `trnm` | 서비스명 | String | N |  | 등록,해지요청시 요청값 반환 , 실시간수신시 REAL 반환 |

---

## 0F

**주식당일거래원**

- **메뉴**: 국내주식 > 실시간시세 > 주식당일거래원(0F)
- **Method**: `POST`
- **URL**: `/api/dostk/websocket`

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
| `trnm` | 서비스명 | String | Y | 10 | REG : 등록 , REMOVE : 해지 |
| `grp_no` | 그룹번호 | String | Y | 4 | 토큰 지정시 토큰타입("Bearer") 붙혀서 호출 예) Bearer Egicyx... Y 1 등록(REG)시 0:기존유지안함 1:기존유지(Default) 0일경우 기존등록한 item/type은 해지, 1일경우 기존등록한 item/type 유지 해지(REMOVE)시 값 불필요 String N 100 거래소별 종목코드, 업종코드 (KRX:039490,NXT:039490_NX,SOR:039490_AL) String Y 2 TR 명(0A,0B....) |
| `refresh` | 기존등록유지여부 | String |  |  | 기존등록유지여부 |
| `data` | 실시간 등록 리스트 LIST |  |  |  | 실시간 등록 리스트 LIST |
| `- item` | 실시간 등록 요소 |  |  |  | 실시간 등록 요소 |
| `- type` | 실시간 항목 |  |  |  | 실시간 항목 |

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
| `return_code` | 결과코드 | String | N |  | 통신결과에대한 코드 (등록,해지요청시에만 값 전송 0:정상,1:오류 , 데이터 실시간 수신시 미전송) |
| `return_msg` | 결과메시지 | String | N |  | 통신결과에대한메시지 |
| `trnm` | 서비스명 | String | N |  | 등록,해지요청시 요청값 반환 , 실시간수신시 REAL 반환 |

---

## 0G

**ETF NAV**

- **메뉴**: 국내주식 > 실시간시세 > ETF NAV(0G)
- **Method**: `POST`
- **URL**: `/api/dostk/websocket`

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
| `trnm` | 서비스명 | String | Y | 10 | REG : 등록 , REMOVE : 해지 |
| `grp_no` | 그룹번호 | String | Y | 4 | 토큰 지정시 토큰타입("Bearer") 붙혀서 호출 예) Bearer Egicyx... Y 1 등록(REG)시 0:기존유지안함 1:기존유지(Default) 0일경우 기존등록한 item/type은 해지, 1일경우 기존등록한 item/type 유지 해지(REMOVE)시 값 불필요 String N 100 거래소별 종목코드, 업종코드 (KRX:039490,NXT:039490_NX,SOR:039490_AL) String Y 2 TR 명(0A,0B....) |
| `refresh` | 기존등록유지여부 | String |  |  | 기존등록유지여부 |
| `data` | 실시간 등록 리스트 LIST |  |  |  | 실시간 등록 리스트 LIST |
| `- item` | 실시간 등록 요소 |  |  |  | 실시간 등록 요소 |
| `- type` | 실시간 항목 |  |  |  | 실시간 항목 |

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
| `return_code` | 결과코드 | String | N |  | 통신결과에대한 코드 (등록,해지요청시에만 값 전송 0:정상,1:오류 , 데이터 실시간 수신시 미전송) |
| `return_msg` | 결과메시지 | String | N |  | 통신결과에대한메시지 |
| `trnm` | 서비스명 | String | N |  | 등록,해지요청시 요청값 반환 , 실시간수신시 REAL 반환 |

---

## 0H

**주식예상체결**

- **메뉴**: 국내주식 > 실시간시세 > 주식예상체결(0H)
- **Method**: `POST`
- **URL**: `/api/dostk/websocket`

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
| `trnm` | 서비스명 | String | Y | 10 | REG : 등록 , REMOVE : 해지 |
| `grp_no` | 그룹번호 | String | Y | 4 | 토큰 지정시 토큰타입("Bearer") 붙혀서 호출 예) Bearer Egicyx... Y 1 등록(REG)시 0:기존유지안함 1:기존유지(Default) 0일경우 기존등록한 item/type은 해지, 1일경우 기존등록한 item/type 유지 해지(REMOVE)시 값 불필요 String N 100 거래소별 종목코드, 업종코드 (KRX:039490,NXT:039490_NX,SOR:039490_AL) String Y 2 TR 명(0A,0B....) |
| `refresh` | 기존등록유지여부 | String |  |  | 기존등록유지여부 |
| `data` | 실시간 등록 리스트 LIST |  |  |  | 실시간 등록 리스트 LIST |
| `- item` | 실시간 등록 요소 |  |  |  | 실시간 등록 요소 |
| `- type` | 실시간 항목 |  |  |  | 실시간 항목 |

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
| `return_code` | 결과코드 | String | N |  | 통신결과에대한 코드 (등록,해지요청시에만 값 전송 0:정상,1:오류 , 데이터 실시간 수신시 미전송) |
| `return_msg` | 결과메시지 | String | N |  | 통신결과에대한메시지 |
| `trnm` | 서비스명 | String | N |  | 등록,해지요청시 요청값 반환 , 실시간수신시 REAL 반환 |

---

## 0I

**국제금환산가격**

- **메뉴**: 국내주식 > 실시간시세 > 국제금환산가격(0I)
- **Method**: `POST`
- **URL**: `/api/dostk/websocket`

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
| `trnm` | 서비스명 | String | Y | 10 | REG : 등록 , REMOVE : 해지 |
| `grp_no` | 그룹번호 | String | Y | 4 | 토큰 지정시 토큰타입("Bearer") 붙혀서 호출 예) Bearer Egicyx... 1 등록(REG)시 0:기존유지안함 1:기존유지(Default) 0일경우 기존등록한 item/type은 해지, 1일경우 기존등록한 item/type 유지 해지(REMOVE)시 값 불필요 N 100 MGD: 원/g, MGU: $/온스,소수점2자리 Y 2 TR 명(0A,0B....) |
| `refresh` | 기존등록유지여부 | String | Y |  | 기존등록유지여부 |
| `data` | 실시간 등록 리스트 LIST N |  |  |  | 실시간 등록 리스트 LIST N |
| `- item` | 실시간 등록 요소 | String |  |  | 실시간 등록 요소 |
| `- type` | 실시간 항목 | String |  |  | 실시간 항목 |

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
| `return_msg` | 결과메시지 | String | N |  | 통신결과에대한메시지 |
| `trnm` | 서비스명 | String | N |  | 등록,해지요청시 요청값 반환 , 실시간수신시 REAL 반환 |
| `data` | 실시간 등록리스트 LIST N |  |  |  | 실시간 등록리스트 LIST N |
| `- type` | 실시간항목 | String | N |  | TR 명(0B,0B....) |

---

## 0J

**업종지수**

- **메뉴**: 국내주식 > 실시간시세 > 업종지수(0J)
- **Method**: `POST`
- **URL**: `/api/dostk/websocket`

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
| `trnm` | 서비스명 | String | Y | 10 | REG : 등록 , REMOVE : 해지 |
| `grp_no` | 그룹번호 | String | Y | 4 | 토큰 지정시 토큰타입("Bearer") 붙혀서 호출 예) Bearer Egicyx... Y 1 등록(REG)시 0:기존유지안함 1:기존유지(Default) 0일경우 기존등록한 item/type은 해지, 1일경우 기존등록한 item/type 유지 해지(REMOVE)시 값 불필요 String N 100 거래소별 종목코드, 업종코드 (KRX:039490,NXT:039490_NX,SOR:039490_AL) String Y 2 TR 명(0A,0B....) |
| `refresh` | 기존등록유지여부 | String |  |  | 기존등록유지여부 |
| `data` | 실시간 등록 리스트 LIST |  |  |  | 실시간 등록 리스트 LIST |
| `- item` | 실시간 등록 요소 |  |  |  | 실시간 등록 요소 |
| `- type` | 실시간 항목 |  |  |  | 실시간 항목 |

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
| `return_code` | 결과코드 | String | N |  | 통신결과에대한 코드 (등록,해지요청시에만 값 전송 0:정상,1:오류 , 데이터 실시간 수신시 미전송) |
| `return_msg` | 결과메시지 | String | N |  | 통신결과에대한메시지 |
| `trnm` | 서비스명 | String | N |  | 등록,해지요청시 요청값 반환 , 실시간수신시 REAL 반환 |

---

## 0U

**업종등락**

- **메뉴**: 국내주식 > 실시간시세 > 업종등락(0U)
- **Method**: `POST`
- **URL**: `/api/dostk/websocket`

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
| `trnm` | 서비스명 | String | Y | 10 | REG : 등록 , REMOVE : 해지 |
| `grp_no` | 그룹번호 | String | Y | 4 | 토큰 지정시 토큰타입("Bearer") 붙혀서 호출 예) Bearer Egicyx... Y 1 등록(REG)시 0:기존유지안함 1:기존유지(Default) 0일경우 기존등록한 item/type은 해지, 1일경우 기존등록한 item/type 유지 해지(REMOVE)시 값 불필요 String N 100 거래소별 종목코드, 업종코드 (KRX:039490,NXT:039490_NX,SOR:039490_AL) String Y 2 TR 명(0A,0B....) |
| `refresh` | 기존등록유지여부 | String |  |  | 기존등록유지여부 |
| `data` | 실시간 등록 리스트 LIST |  |  |  | 실시간 등록 리스트 LIST |
| `- item` | 실시간 등록 요소 |  |  |  | 실시간 등록 요소 |
| `- type` | 실시간 항목 |  |  |  | 실시간 항목 |

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
| `return_code` | 결과코드 | String | N |  | 통신결과에대한 코드 (등록,해지요청시에만 값 전송 0:정상,1:오류 , 데이터 실시간 수신시 미전송) |
| `return_msg` | 결과메시지 | String | N |  | 통신결과에대한메시지 |
| `trnm` | 서비스명 | String | N |  | 등록,해지요청시 요청값 반환 , 실시간수신시 REAL 반환 |

---

## 0g

**주식종목정보**

- **메뉴**: 국내주식 > 실시간시세 > 주식종목정보(0g)
- **Method**: `POST`
- **URL**: `/api/dostk/websocket`

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
| `trnm` | 서비스명 | String | Y | 10 | REG : 등록 , REMOVE : 해지 |
| `grp_no` | 그룹번호 | String | Y | 4 | 토큰 지정시 토큰타입("Bearer") 붙혀서 호출 예) Bearer Egicyx... Y 1 등록(REG)시 0:기존유지안함 1:기존유지(Default) 0일경우 기존등록한 item/type은 해지, 1일경우 기존등록한 item/type 유지 해지(REMOVE)시 값 불필요 String N 100 거래소별 종목코드, 업종코드 (KRX:039490,NXT:039490_NX,SOR:039490_AL) String Y 2 TR 명(0A,0B....) |
| `refresh` | 기존등록유지여부 | String |  |  | 기존등록유지여부 |
| `data` | 실시간 등록 리스트 LIST |  |  |  | 실시간 등록 리스트 LIST |
| `- item` | 실시간 등록 요소 |  |  |  | 실시간 등록 요소 |
| `- type` | 실시간 항목 |  |  |  | 실시간 항목 |

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
| `return_code` | 결과코드 | String | N |  | 통신결과에대한 코드 (등록,해지요청시에만 값 전송 0:정상,1:오류 , 데이터 실시간 수신시 미전송) |
| `return_msg` | 결과메시지 | String | N |  | 통신결과에대한메시지 |
| `trnm` | 서비스명 | String | N |  | 등록,해지요청시 요청값 반환 , 실시간수신시 REAL 반환 |

---

## 0m

**ELW 이론가**

- **메뉴**: 국내주식 > 실시간시세 > ELW 이론가(0m)
- **Method**: `POST`
- **URL**: `/api/dostk/websocket`

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
| `trnm` | 서비스명 | String | Y | 10 | REG : 등록 , REMOVE : 해지 |
| `grp_no` | 그룹번호 | String | Y | 4 | 토큰 지정시 토큰타입("Bearer") 붙혀서 호출 예) Bearer Egicyx... Y 1 등록(REG)시 0:기존유지안함 1:기존유지(Default) 0일경우 기존등록한 item/type은 해지, 1일경우 기존등록한 item/type 유지 해지(REMOVE)시 값 불필요 String N 100 거래소별 종목코드, 업종코드 (KRX:039490,NXT:039490_NX,SOR:039490_AL) String Y 2 TR 명(0A,0B....) |
| `refresh` | 기존등록유지여부 | String |  |  | 기존등록유지여부 |
| `data` | 실시간 등록 리스트 LIST |  |  |  | 실시간 등록 리스트 LIST |
| `- item` | 실시간 등록 요소 |  |  |  | 실시간 등록 요소 |
| `- type` | 실시간 항목 |  |  |  | 실시간 항목 |

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
| `return_code` | 결과코드 | String | N |  | 통신결과에대한 코드 (등록,해지요청시에만 값 전송 0:정상,1:오류 , 데이터 실시간 수신시 미전송) |
| `return_msg` | 결과메시지 | String | N |  | 통신결과에대한메시지 |
| `trnm` | 서비스명 | String | N |  | 등록,해지요청시 요청값 반환 , 실시간수신시 REAL 반환 |

---

## 0s

**장시작시간**

- **메뉴**: 국내주식 > 실시간시세 > 장시작시간(0s)
- **Method**: `POST`
- **URL**: `/api/dostk/websocket`

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
| `trnm` | 서비스명 | String | Y | 10 | REG : 등록 , REMOVE : 해지 |
| `grp_no` | 그룹번호 | String | Y | 4 | 토큰 지정시 토큰타입("Bearer") 붙혀서 호출 예) Bearer Egicyx... Y 1 등록(REG)시 0:기존유지안함 1:기존유지(Default) 0일경우 기존등록한 item/type은 해지, 1일경우 기존등록한 item/type 유지 해지(REMOVE)시 값 불필요 String N 100 거래소별 종목코드, 업종코드 (KRX:039490,NXT:039490_NX,SOR:039490_AL) String Y 2 TR 명(0A,0B....) |
| `refresh` | 기존등록유지여부 | String |  |  | 기존등록유지여부 |
| `data` | 실시간 등록 리스트 LIST |  |  |  | 실시간 등록 리스트 LIST |
| `- item` | 실시간 등록 요소 |  |  |  | 실시간 등록 요소 |
| `- type` | 실시간 항목 |  |  |  | 실시간 항목 |

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
| `return_code` | 결과코드 | String | N |  | 통신결과에대한 코드 (등록,해지요청시에만 값 전송 0:정상,1:오류 , 데이터 실시간 수신시 미전송) |
| `return_msg` | 결과메시지 | String | N |  | 통신결과에대한메시지 |
| `trnm` | 서비스명 | String | N |  | 등록,해지요청시 요청값 반환 , 실시간수신시 REAL 반환 |

---

## 0u

**ELW 지표**

- **메뉴**: 국내주식 > 실시간시세 > ELW 지표(0u)
- **Method**: `POST`
- **URL**: `/api/dostk/websocket`

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
| `trnm` | 서비스명 | String | Y | 10 | REG : 등록 , REMOVE : 해지 |
| `grp_no` | 그룹번호 | String | Y | 4 | 토큰 지정시 토큰타입("Bearer") 붙혀서 호출 예) Bearer Egicyx... Y 1 등록(REG)시 0:기존유지안함 1:기존유지(Default) 0일경우 기존등록한 item/type은 해지, 1일경우 기존등록한 item/type 유지 해지(REMOVE)시 값 불필요 String N 100 거래소별 종목코드, 업종코드 (KRX:039490,NXT:039490_NX,SOR:039490_AL) String Y 2 TR 명(0A,0B....) |
| `refresh` | 기존등록유지여부 | String |  |  | 기존등록유지여부 |
| `data` | 실시간 등록 리스트 LIST |  |  |  | 실시간 등록 리스트 LIST |
| `- item` | 실시간 등록 요소 |  |  |  | 실시간 등록 요소 |
| `- type` | 실시간 항목 |  |  |  | 실시간 항목 |

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
| `return_code` | 결과코드 | String | N |  | 통신결과에대한 코드 (등록,해지요청시에만 값 전송 0:정상,1:오류 , 데이터 실시간 수신시 미전송) |
| `return_msg` | 결과메시지 | String | N |  | 통신결과에대한메시지 |
| `trnm` | 서비스명 | String | N |  | 등록,해지요청시 요청값 반환 , 실시간수신시 REAL 반환 |

---

## 0w

**종목프로그램매매**

- **메뉴**: 국내주식 > 실시간시세 > 종목프로그램매매(0w)
- **Method**: `POST`
- **URL**: `/api/dostk/websocket`

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
| `trnm` | 서비스명 | String | Y | 10 | REG : 등록 , REMOVE : 해지 |
| `grp_no` | 그룹번호 | String | Y | 4 | 토큰 지정시 토큰타입("Bearer") 붙혀서 호출 예) Bearer Egicyx... Y 1 등록(REG)시 0:기존유지안함 1:기존유지(Default) 0일경우 기존등록한 item/type은 해지, 1일경우 기존등록한 item/type 유지 해지(REMOVE)시 값 불필요 String N 100 거래소별 종목코드, 업종코드 (KRX:039490,NXT:039490_NX,SOR:039490_AL) String Y 2 TR 명(0A,0B....) |
| `refresh` | 기존등록유지여부 | String |  |  | 기존등록유지여부 |
| `data` | 실시간 등록 리스트 LIST |  |  |  | 실시간 등록 리스트 LIST |
| `- item` | 실시간 등록 요소 |  |  |  | 실시간 등록 요소 |
| `- type` | 실시간 항목 |  |  |  | 실시간 항목 |

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
| `return_code` | 결과코드 | String | N |  | 통신결과에대한 코드 (등록,해지요청시에만 값 전송 0:정상,1:오류 , 데이터 실시간 수신시 미전송) |
| `return_msg` | 결과메시지 | String | N |  | 통신결과에대한메시지 |
| `trnm` | 서비스명 | String | N |  | 등록,해지요청시 요청값 반환 , 실시간수신시 REAL 반환 |

---

## 1h

**VI발동/해제**

- **메뉴**: 국내주식 > 실시간시세 > VI발동/해제(1h)
- **Method**: `POST`
- **URL**: `/api/dostk/websocket`

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
| `trnm` | 서비스명 | String | Y | 10 | REG : 등록 , REMOVE : 해지 |
| `grp_no` | 그룹번호 | String | Y | 4 | 토큰 지정시 토큰타입("Bearer") 붙혀서 호출 예) Bearer Egicyx... Y 1 등록(REG)시 0:기존유지안함 1:기존유지(Default) 0일경우 기존등록한 item/type은 해지, 1일경우 기존등록한 item/type 유지 해지(REMOVE)시 값 불필요 String N 100 거래소별 종목코드, 업종코드 (KRX:039490,NXT:039490_NX,SOR:039490_AL) String Y 2 TR 명(0A,0B....) |
| `refresh` | 기존등록유지여부 | String |  |  | 기존등록유지여부 |
| `data` | 실시간 등록 리스트 LIST |  |  |  | 실시간 등록 리스트 LIST |
| `- item` | 실시간 등록 요소 |  |  |  | 실시간 등록 요소 |
| `- type` | 실시간 항목 |  |  |  | 실시간 항목 |

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
| `return_code` | 결과코드 | String | N |  | 통신결과에대한 코드 (등록,해지요청시에만 값 전송 0:정상,1:오류 , 데이터 실시간 수신시 미전송) |
| `return_msg` | 결과메시지 | String | N |  | 통신결과에대한메시지 |
| `trnm` | 서비스명 | String | N |  | 등록,해지요청시 요청값 반환 , 실시간수신시 REAL 반환 |

---
