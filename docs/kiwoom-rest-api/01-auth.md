# OAuth 인증 API

> API 수: 2개

## 목차

- [au10001 - 접근토큰 발급](#au10001)
- [au10002 - 접근토큰폐기](#au10002)

---

## au10001

**접근토큰 발급**

- **메뉴**: OAuth 인증 > 접근토큰발급 > 접근토큰 발급(au10001)
- **Method**: `POST`
- **URL**: `/oauth2/token`

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
| `grant_type` | grant_type | String | Y |  | grant_type |
| `appkey` | 앱키 | String | Y |  | 앱키 |
| `secretkey` | 시크릿키 | String | Y |  | 토큰 지정시 토큰타입("Bearer") 붙혀서 호출 예) Bearer Egicyx... client_credentials 입력 |

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
| `expires_dt` | 만료일 | String | Y |  | 만료일 |
| `token_type` | 토큰타입 | String | Y |  | 토큰타입 |
| `token` | 접근토큰 | String | Y |  | 접근토큰 |

---

## au10002

**접근토큰폐기**

- **메뉴**: OAuth 인증 > 접근토큰폐기 > 접근토큰폐기(au10002)
- **Method**: `POST`
- **URL**: `/oauth2/revoke`

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
| `appkey` | 앱키 | String | Y |  | 앱키 |
| `secretkey` | 시크릿키 | String | Y |  | 시크릿키 |
| `token` | 접근토큰 | String | Y |  | 토큰 지정시 토큰타입("Bearer") 붙혀서 호출 예) Bearer Egicyx... |

### Response

**Headers**

| Element | 한글명 | Type | Required | Length | Description |
|---------|--------|------|----------|--------|-------------|
| `api-id` | TR명 | String | Y | 10 | TR명 |
| `cont-yn` | 연속조회여부 | String | N | 1 | 다음 데이터가 있을시 Y값 전달 |
| `next-key` | 연속조회키 | String | N | 50 | 다음 데이터가 있을시 다음 키값 전달 |

---

