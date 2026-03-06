# 키움증권 REST API 레퍼런스

> 키움증권 REST API PDF(528p)에서 자동 추출한 API 레퍼런스
> 총 207개 API

## 기본 정보

| 항목 | 값 |
|------|----|
| 운영 도메인 | `https://api.kiwoom.com` |
| 모의투자 도메인 | `https://mockapi.kiwoom.com` (KRX만 지원) |
| Content-Type | `application/json;charset=UTF-8` |
| Format | JSON |
| Method | POST (전체) |

## API 호출 제한 (Rate Limits)

> 출처: 커뮤니티/라이브러리 소스 + 유튜브 "주식코딩" 채널 (공식 문서에 구체적 수치 미공개)

### REST API

| 항목 | 제한 | 비고 |
|------|------|------|
| REST API 호출 | **초당 20건** (추정) | 조회+주문 통합 (커뮤니티 기반) |
| 모의투자 API 호출 | **초당 5건** (추정) | 모의투자 도메인 |
| Access Token 유효기간 | **24시간** | 자동 갱신 로직 권장 |
| 미접속 시 자동해지 | **3개월** | 매월 첫영업일 해지 |

### WebSocket 실시간

| 항목 | 제한 | 비고 |
|------|------|------|
| 실시간 등록 종목 | **최대 100개** | per connection, grp_no 기반 |
| WebSocket 동시 구독 | **40종목** (per connection) | kiwoom-restful 문서 기반 |
| WebSocket 연결 수 | **1개** | per connection |
| 실시간 코드 등록 | **100개/그룹** (grp_no) | 여러 그룹 사용 가능 |

### 주요 제약사항 & 우회 방안

1. **100개 종목 제한이 핵심 병목**: 100개 이상 종목을 실시간 트래킹하려면 별도 방안 필요
2. **우회 방안**: LS증권 WebSocket (등록 제한 없음)으로 실시간 시세 수신, 주문은 키움 REST API 유지
3. **성능 주의**: 1,000개+ 종목 동시 트래킹 시 시스템 리소스(CPU/메모리) 부족 가능
4. **안전 마진 권장**: 실제 구현 시 95개 정도로 제한 설정 (100개 경계에서의 불안정 방지)

> 상세 리서치: `.claude/memory/research-rate-limits-and-queues.md` 참조

## 공통 헤더

모든 API 요청에 공통으로 사용되는 헤더:

| Header | 설명 | Required |
|--------|------|----------|
| `api-id` | TR명 (API ID) | Y |
| `authorization` | 접근토큰 (Bearer {token}) | Y |
| `cont-yn` | 연속조회 여부 (Y/N) | N |
| `next-key` | 연속조회 키 | N |

## URL 경로 체계

| URL | 카테고리 | API 수 |
|-----|----------|--------|
| `/api/dostk/acnt` | 계좌 | 33 |
| `/api/dostk/chart` | 차트 | 21 |
| `/api/dostk/crdordr` | 신용주문 | 4 |
| `/api/dostk/elw` | ELW | 11 |
| `/api/dostk/etf` | ETF | 9 |
| `/api/dostk/frgnistt` | 기관/외국인 | 4 |
| `/api/dostk/mrkcond` | 시세/시장조건 | 25 |
| `/api/dostk/ordr` | 주문 | 8 |
| `/api/dostk/rkinfo` | 순위정보 | 23 |
| `/api/dostk/sect` | 업종 | 6 |
| `/api/dostk/shsa` | 공매도 | 1 |
| `/api/dostk/slb` | 대차거래 | 4 |
| `/api/dostk/stkinfo` | 종목정보 | 31 |
| `/api/dostk/thme` | 테마 | 2 |
| `/api/dostk/websocket` | 실시간(WebSocket) | 23 |
| `/oauth2/revoke` | OAuth 인증 | 1 |
| `/oauth2/token` | OAuth 인증 | 1 |

## 오류코드

| 코드 | 메시지 |
|------|--------|
| `1501` | API ID가 Null이거나 값이 없습니다 |
| `1504` | 해당 URI에서는 지원하는 API ID가 아닙니다 |
| `1505` | 해당 API ID는 존재하지 않습니다 |
| `1511` | 필수 입력 값에 값이 존재하지 않습니다 |
| `1512` | Http header에 값이 설정되지 않았거나 읽을 수 없습니다 |
| `1513` | Http Header에 authorization 필드가 설정되어 있어야 합니다 |
| `1514` | authorization 필드 형식이 맞지 않습니다 |
| `1515` | authorization Grant Type이 미리 정의된 형식이 아닙니다 |
| `1516` | authorization Token이 정의되어 있지 않습니다 |
| `1517` | 입력 값 형식이 올바르지 않습니다 |
| `1687` | 재귀 호출이 발생하여 API 호출을 제한합니다 |
| `1700` | **허용된 요청 개수를 초과하였습니다** (Rate Limit) |
| `1901` | 시장 코드값이 존재하지 않습니다 |
| `1902` | 종목 정보가 없습니다 |
| `1999` | 예기치 못한 에러가 발생했습니다 |
| `8001` | App Key와 Secret Key 검증에 실패했습니다 |
| `8002` | App Key와 Secret Key 검증에 실패했습니다 (상세) |
| `8003` | Access Token을 조회하는데 실패했습니다 |
| `8005` | Token이 유효하지 않습니다 |
| `8006` | Access Token을 생성하는데 실패했습니다 |
| `8009` | Access Token을 발급하는데 실패했습니다 |
| `8010` | Token 발급 IP와 서비스 요청 IP가 동일하지 않습니다 |
| `8011` | grant_type이 들어오지 않았습니다 |
| `8012` | grant_type의 값이 맞지 않습니다 |
| `8015` | Access Token을 폐기하는데 실패했습니다 |
| `8016` | 폐기 시 Token이 들어오지 않았습니다 |
| `8020` | appkey 또는 secretkey가 들어오지 않았습니다 |
| `8030` | 투자구분(실전/모의)이 달라서 Appkey를 사용할 수 없습니다 |
| `8031` | 투자구분(실전/모의)이 달라서 Token을 사용할 수 없습니다 |
| `8040` | 단말기 인증에 실패했습니다 |
| `8050` | 지정단말기 인증에 실패했습니다 |
| `8103` | 토큰 인증 또는 단말기인증에 실패했습니다 |

> **백엔드 개발 핵심**: `1700` (Rate Limit 초과) 에러 시 재시도 로직 필수. `8005` (토큰 무효) 시 토큰 재발급.

## 카테고리별 문서

### [OAuth 인증](01-auth.md) (2개)

- `au10001` 접근토큰 발급 — `POST /oauth2/token`
- `au10002` 접근토큰폐기 — `POST /oauth2/revoke`

### [계좌](02-account.md) (33개)

- `ka00001` 계좌번호조회 — `POST /api/dostk/acnt`
- `ka01690` 일별잔고수익률 — `POST /api/dostk/acnt`
- `ka10072` 일자별종목별실현손익요청_일자 — `POST /api/dostk/acnt`
- `ka10073` 일자별종목별실현손익요청_기간 — `POST /api/dostk/acnt`
- `ka10074` 일자별실현손익요청 — `POST /api/dostk/acnt`
- `ka10075` 미체결요청 — `POST /api/dostk/acnt`
- `ka10076` 체결요청 — `POST /api/dostk/acnt`
- `ka10077` 당일실현손익상세요청 — `POST /api/dostk/acnt`
- `ka10085` 계좌수익률요청 — `POST /api/dostk/acnt`
- `ka10088` 미체결 분할주문 상세 — `POST /api/dostk/acnt`
- `ka10170` 당일매매일지요청 — `POST /api/dostk/acnt`
- `kt00001` 예수금상세현황요청 — `POST /api/dostk/acnt`
- `kt00002` 일별추정예탁자산현황요청 — `POST /api/dostk/acnt`
- `kt00003` 추정자산조회요청 — `POST /api/dostk/acnt`
- `kt00004` 계좌평가현황요청 — `POST /api/dostk/acnt`
- `kt00005` 체결잔고요청 — `POST /api/dostk/acnt`
- `kt00007` 계좌별주문체결내역상세요청 — `POST /api/dostk/acnt`
- `kt00008` 계좌별익일결제예정내역요청 — `POST /api/dostk/acnt`
- `kt00009` 계좌별주문체결현황요청 — `POST /api/dostk/acnt`
- `kt00010` 주문인출가능금액요청 — `POST /api/dostk/acnt`
- `kt00011` 증거금율별주문가능수량조회요청 — `POST /api/dostk/acnt`
- `kt00012` 신용보증금율별주문가능수량조회요청 — `POST /api/dostk/acnt`
- `kt00013` 증거금세부내역조회요청 — `POST /api/dostk/acnt`
- `kt00015` 위탁종합거래내역요청 — `POST /api/dostk/acnt`
- `kt00016` 일별계좌수익률상세현황요청 — `POST /api/dostk/acnt`
- `kt00017` 계좌별당일현황요청 — `POST /api/dostk/acnt`
- `kt00018` 계좌평가잔고내역요청 — `POST /api/dostk/acnt`
- `kt50020` 금현물 잔고확인 — `POST /api/dostk/acnt`
- `kt50021` 금현물 예수금 — `POST /api/dostk/acnt`
- `kt50030` 금현물 주문체결전체조회 — `POST /api/dostk/acnt`
- `kt50031` 금현물 주문체결조회 — `POST /api/dostk/acnt`
- `kt50032` 금현물 거래내역조회 — `POST /api/dostk/acnt`
- `kt50075` 금현물 미체결조회 — `POST /api/dostk/acnt`

### [주문](03-order.md) (8개)

- `kt10000` 주식 매수주문 — `POST /api/dostk/ordr`
- `kt10001` 주식 매도주문 — `POST /api/dostk/ordr`
- `kt10002` 주식 정정주문 — `POST /api/dostk/ordr`
- `kt10003` 주식 취소주문 — `POST /api/dostk/ordr`
- `kt50000` 금현물 매수주문 — `POST /api/dostk/ordr`
- `kt50001` 금현물 매도주문 — `POST /api/dostk/ordr`
- `kt50002` 금현물 정정주문 — `POST /api/dostk/ordr`
- `kt50003` 금현물 취소주문 — `POST /api/dostk/ordr`

### [신용주문](04-credit-order.md) (4개)

- `kt10006` 신용 매수주문 — `POST /api/dostk/crdordr`
- `kt10007` 신용 매도주문 — `POST /api/dostk/crdordr`
- `kt10008` 신용 정정주문 — `POST /api/dostk/crdordr`
- `kt10009` 신용 취소주문 — `POST /api/dostk/crdordr`

### [시세/시장조건](05-market.md) (25개)

- `ka10004` 주식호가요청 — `POST /api/dostk/mrkcond`
- `ka10005` 주식일주월시분요청 — `POST /api/dostk/mrkcond`
- `ka10006` 주식시분요청 — `POST /api/dostk/mrkcond`
- `ka10007` 시세표성정보요청 — `POST /api/dostk/mrkcond`
- `ka10011` 신주인수권전체시세요청 — `POST /api/dostk/mrkcond`
- `ka10044` 일별기관매매종목요청 — `POST /api/dostk/mrkcond`
- `ka10045` 종목별기관매매추이요청 — `POST /api/dostk/mrkcond`
- `ka10046` 체결강도추이시간별요청 — `POST /api/dostk/mrkcond`
- `ka10047` 체결강도추이일별요청 — `POST /api/dostk/mrkcond`
- `ka10063` 장중투자자별매매요청 — `POST /api/dostk/mrkcond`
- `ka10066` 장마감후투자자별매매요청 — `POST /api/dostk/mrkcond`
- `ka10078` 증권사별종목매매동향요청 — `POST /api/dostk/mrkcond`
- `ka10086` 일별주가요청 — `POST /api/dostk/mrkcond`
- `ka10087` 시간외단일가요청 — `POST /api/dostk/mrkcond`
- `ka50010` 금현물체결추이 — `POST /api/dostk/mrkcond`
- `ka50012` 금현물일별추이 — `POST /api/dostk/mrkcond`
- `ka50087` 금현물예상체결 — `POST /api/dostk/mrkcond`
- `ka50100` 금현물 시세정보 — `POST /api/dostk/mrkcond`
- `ka50101` 금현물 호가 — `POST /api/dostk/mrkcond`
- `ka90005` 프로그램매매추이요청 시간대별 — `POST /api/dostk/mrkcond`
- `ka90006` 프로그램매매차익잔고추이요청 — `POST /api/dostk/mrkcond`
- `ka90007` 프로그램매매누적추이요청 — `POST /api/dostk/mrkcond`
- `ka90008` 종목시간별프로그램매매추이요청 — `POST /api/dostk/mrkcond`
- `ka90010` 프로그램매매추이요청 일자별 — `POST /api/dostk/mrkcond`
- `ka90013` 종목일별프로그램매매추이요청 — `POST /api/dostk/mrkcond`

### [종목정보](06-stock-info.md) (31개)

- `ka00198` 실시간종목조회순위 — `POST /api/dostk/stkinfo`
- `ka10001` 주식기본정보요청 — `POST /api/dostk/stkinfo`
- `ka10002` 주식거래원요청 — `POST /api/dostk/stkinfo`
- `ka10003` 체결정보요청 — `POST /api/dostk/stkinfo`
- `ka10013` 신용매매동향요청 — `POST /api/dostk/stkinfo`
- `ka10015` 일별거래상세요청 — `POST /api/dostk/stkinfo`
- `ka10016` 신고저가요청 — `POST /api/dostk/stkinfo`
- `ka10017` 상하한가요청 — `POST /api/dostk/stkinfo`
- `ka10018` 고저가근접요청 — `POST /api/dostk/stkinfo`
- `ka10019` 가격급등락요청 — `POST /api/dostk/stkinfo`
- `ka10024` 거래량갱신요청 — `POST /api/dostk/stkinfo`
- `ka10025` 매물대집중요청 — `POST /api/dostk/stkinfo`
- `ka10026` 고저PER요청 — `POST /api/dostk/stkinfo`
- `ka10028` 시가대비등락률요청 — `POST /api/dostk/stkinfo`
- `ka10043` 거래원매물대분석요청 — `POST /api/dostk/stkinfo`
- `ka10052` 거래원순간거래량요청 — `POST /api/dostk/stkinfo`
- `ka10054` 변동성완화장치발동종목요청 — `POST /api/dostk/stkinfo`
- `ka10055` 당일전일체결량요청 — `POST /api/dostk/stkinfo`
- `ka10058` 투자자별일별매매종목요청 — `POST /api/dostk/stkinfo`
- `ka10059` 종목별투자자기관별요청 — `POST /api/dostk/stkinfo`
- `ka10061` 종목별투자자기관별합계요청 — `POST /api/dostk/stkinfo`
- `ka10084` 당일전일체결요청 — `POST /api/dostk/stkinfo`
- `ka10095` 관심종목정보요청 — `POST /api/dostk/stkinfo`
- `ka10099` 종목정보 리스트 — `POST /api/dostk/stkinfo`
- `ka10100` 종목정보 조회 — `POST /api/dostk/stkinfo`
- `ka10101` 업종코드 리스트 — `POST /api/dostk/stkinfo`
- `ka10102` 회원사 리스트 — `POST /api/dostk/stkinfo`
- `ka90003` 프로그램순매수상위50요청 — `POST /api/dostk/stkinfo`
- `ka90004` 종목별프로그램매매현황요청 — `POST /api/dostk/stkinfo`
- `kt20016` 신용융자 가능종목요청 — `POST /api/dostk/stkinfo`
- `kt20017` 신용융자 가능문의 — `POST /api/dostk/stkinfo`

### [순위정보](07-ranking.md) (23개)

- `ka10020` 호가잔량상위요청 — `POST /api/dostk/rkinfo`
- `ka10021` 호가잔량급증요청 — `POST /api/dostk/rkinfo`
- `ka10022` 잔량율급증요청 — `POST /api/dostk/rkinfo`
- `ka10023` 거래량급증요청 — `POST /api/dostk/rkinfo`
- `ka10027` 전일대비등락률상위요청 — `POST /api/dostk/rkinfo`
- `ka10029` 예상체결등락률상위요청 — `POST /api/dostk/rkinfo`
- `ka10030` 당일거래량상위요청 — `POST /api/dostk/rkinfo`
- `ka10031` 전일거래량상위요청 — `POST /api/dostk/rkinfo`
- `ka10032` 거래대금상위요청 — `POST /api/dostk/rkinfo`
- `ka10033` 신용비율상위요청 — `POST /api/dostk/rkinfo`
- `ka10034` 외인기간별매매상위요청 — `POST /api/dostk/rkinfo`
- `ka10035` 외인연속순매매상위요청 — `POST /api/dostk/rkinfo`
- `ka10036` 외인한도소진율증가상위 — `POST /api/dostk/rkinfo`
- `ka10037` 외국계창구매매상위요청 — `POST /api/dostk/rkinfo`
- `ka10038` 종목별증권사순위요청 — `POST /api/dostk/rkinfo`
- `ka10039` 증권사별매매상위요청 — `POST /api/dostk/rkinfo`
- `ka10040` 당일주요거래원요청 — `POST /api/dostk/rkinfo`
- `ka10042` 순매수거래원순위요청 — `POST /api/dostk/rkinfo`
- `ka10053` 당일상위이탈원요청 — `POST /api/dostk/rkinfo`
- `ka10062` 동일순매매순위요청 — `POST /api/dostk/rkinfo`
- `ka10065` 장중투자자별매매상위요청 — `POST /api/dostk/rkinfo`
- `ka10098` 시간외단일가등락율순위요청 — `POST /api/dostk/rkinfo`
- `ka90009` 외국인기관매매상위요청 — `POST /api/dostk/rkinfo`

### [차트](08-chart.md) (21개)

- `ka10060` 종목별투자자기관별차트요청 — `POST /api/dostk/chart`
- `ka10064` 장중투자자별매매차트요청 — `POST /api/dostk/chart`
- `ka10079` 주식틱차트조회요청 — `POST /api/dostk/chart`
- `ka10080` 주식분봉차트조회요청 — `POST /api/dostk/chart`
- `ka10081` 주식일봉차트조회요청 — `POST /api/dostk/chart`
- `ka10082` 주식주봉차트조회요청 — `POST /api/dostk/chart`
- `ka10083` 주식월봉차트조회요청 — `POST /api/dostk/chart`
- `ka10094` 주식년봉차트조회요청 — `POST /api/dostk/chart`
- `ka20004` 업종틱차트조회요청 — `POST /api/dostk/chart`
- `ka20005` 업종분봉조회요청 — `POST /api/dostk/chart`
- `ka20006` 업종일봉조회요청 — `POST /api/dostk/chart`
- `ka20007` 업종주봉조회요청 — `POST /api/dostk/chart`
- `ka20008` 업종월봉조회요청 — `POST /api/dostk/chart`
- `ka20019` 업종년봉조회요청 — `POST /api/dostk/chart`
- `ka50079` 금현물틱차트조회요청 — `POST /api/dostk/chart`
- `ka50080` 금현물분봉차트조회요청 — `POST /api/dostk/chart`
- `ka50081` 금현물일봉차트조회요청 — `POST /api/dostk/chart`
- `ka50082` 금현물주봉차트조회요청 — `POST /api/dostk/chart`
- `ka50083` 금현물월봉차트조회요청 — `POST /api/dostk/chart`
- `ka50091` 금현물당일틱차트조회요청 — `POST /api/dostk/chart`
- `ka50092` 금현물당일분봉차트조회요청 — `POST /api/dostk/chart`

### [업종](09-sector.md) (6개)

- `ka10010` 업종프로그램요청 — `POST /api/dostk/sect`
- `ka10051` 업종별투자자순매수요청 — `POST /api/dostk/sect`
- `ka20001` 업종현재가요청 — `POST /api/dostk/sect`
- `ka20002` 업종별주가요청 — `POST /api/dostk/sect`
- `ka20003` 전업종지수요청 — `POST /api/dostk/sect`
- `ka20009` 업종현재가일별요청 — `POST /api/dostk/sect`

### [기관/외국인](10-institution.md) (4개)

- `ka10008` 주식외국인종목별매매동향 — `POST /api/dostk/frgnistt`
- `ka10009` 주식기관요청 — `POST /api/dostk/frgnistt`
- `ka10131` 기관외국인연속매매현황요청 — `POST /api/dostk/frgnistt`
- `ka52301` 금현물투자자현황 — `POST /api/dostk/frgnistt`

### [ELW](11-elw.md) (11개)

- `ka10048` ELW일별민감도지표요청 — `POST /api/dostk/elw`
- `ka10050` ELW민감도지표요청 — `POST /api/dostk/elw`
- `ka30001` ELW가격급등락요청 — `POST /api/dostk/elw`
- `ka30002` 거래원별ELW순매매상위요청 — `POST /api/dostk/elw`
- `ka30003` ELWLP보유일별추이요청 — `POST /api/dostk/elw`
- `ka30004` ELW괴리율요청 — `POST /api/dostk/elw`
- `ka30005` ELW조건검색요청 — `POST /api/dostk/elw`
- `ka30009` ELW등락율순위요청 — `POST /api/dostk/elw`
- `ka30010` ELW잔량순위요청 — `POST /api/dostk/elw`
- `ka30011` ELW근접율요청 — `POST /api/dostk/elw`
- `ka30012` ELW종목상세정보요청 — `POST /api/dostk/elw`

### [ETF](12-etf.md) (9개)

- `ka40001` ETF수익율요청 — `POST /api/dostk/etf`
- `ka40002` ETF종목정보요청 — `POST /api/dostk/etf`
- `ka40003` ETF일별추이요청 — `POST /api/dostk/etf`
- `ka40004` ETF전체시세요청 — `POST /api/dostk/etf`
- `ka40006` ETF시간대별추이요청 — `POST /api/dostk/etf`
- `ka40007` ETF시간대별체결요청 — `POST /api/dostk/etf`
- `ka40008` ETF일자별체결요청 — `POST /api/dostk/etf`
- `ka40009` ETF시간대별체결요청 — `POST /api/dostk/etf`
- `ka40010` ETF시간대별추이요청 — `POST /api/dostk/etf`

### [대차거래](13-slb.md) (4개)

- `ka10068` 대차거래추이요청 — `POST /api/dostk/slb`
- `ka10069` 대차거래상위10종목요청 — `POST /api/dostk/slb`
- `ka20068` 대차거래추이요청(종목별) — `POST /api/dostk/slb`
- `ka90012` 대차거래내역요청 — `POST /api/dostk/slb`

### [공매도](14-short-sell.md) (1개)

- `ka10014` 공매도추이요청 — `POST /api/dostk/shsa`

### [테마](15-theme.md) (2개)

- `ka90001` 테마그룹별요청 — `POST /api/dostk/thme`
- `ka90002` 테마구성종목요청 — `POST /api/dostk/thme`

### [실시간(WebSocket)](16-websocket.md) (23개)

- `ka10171` 조건검색 목록조회 — `POST /api/dostk/websocket`
- `ka10172` 조건검색 요청 일반 — `POST /api/dostk/websocket`
- `ka10173` 조건검색 요청 실시간 — `POST /api/dostk/websocket`
- `ka10174` 조건검색 실시간 해제 — `POST /api/dostk/websocket`
- `00` 주문체결 — `POST /api/dostk/websocket`
- `04` 잔고 — `POST /api/dostk/websocket`
- `0A` 주식기세 — `POST /api/dostk/websocket`
- `0B` 주식체결 — `POST /api/dostk/websocket`
- `0C` 주식우선호가 — `POST /api/dostk/websocket`
- `0D` 주식호가잔량 — `POST /api/dostk/websocket`
- `0E` 주식시간외호가 — `POST /api/dostk/websocket`
- `0F` 주식당일거래원 — `POST /api/dostk/websocket`
- `0G` ETF NAV — `POST /api/dostk/websocket`
- `0H` 주식예상체결 — `POST /api/dostk/websocket`
- `0I` 국제금환산가격 — `POST /api/dostk/websocket`
- `0J` 업종지수 — `POST /api/dostk/websocket`
- `0U` 업종등락 — `POST /api/dostk/websocket`
- `0g` 주식종목정보 — `POST /api/dostk/websocket`
- `0m` ELW 이론가 — `POST /api/dostk/websocket`
- `0s` 장시작시간 — `POST /api/dostk/websocket`
- `0u` ELW 지표 — `POST /api/dostk/websocket`
- `0w` 종목프로그램매매 — `POST /api/dostk/websocket`
- `1h` VI발동/해제 — `POST /api/dostk/websocket`
