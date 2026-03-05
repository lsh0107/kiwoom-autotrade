#!/usr/bin/env python3
"""키움 모의투자 REST API 라이브 테스트 스크립트.

모의투자 API에 실제 HTTP 요청을 보내 응답 포맷을 검증한다.
KiwoomClient를 거치지 않고 httpx로 직접 호출.

사용법:
    python scripts/test_kiwoom_live.py

필수 환경변수:
    KIWOOM_MOCK_APP_KEY: 모의투자 앱 키
    KIWOOM_MOCK_APP_SECRET: 모의투자 앱 시크릿
"""

import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx

# ── 설정 ──────────────────────────────────────────

MOCK_BASE_URL = "https://mockapi.kiwoom.com"
TEST_SYMBOL = "KRX:005930"  # 삼성전자
RESULTS_DIR = Path("docs/kiwoom-rest-api")


def get_env_or_exit(key: str) -> str:
    """환경변수를 읽거나 없으면 종료."""
    value = os.environ.get(key, "")
    if not value:
        print(f"[ERROR] 환경변수 {key}가 설정되지 않았습니다.")
        print("  .env 파일에 설정하거나 export로 지정하세요.")
        sys.exit(1)
    return value


# ── 결과 수집 ─────────────────────────────────────

results: list[dict[str, Any]] = []


def record(
    test_name: str,
    api_id: str,
    url: str,
    *,
    status_code: int,
    response_body: dict[str, Any],
    passed: bool,
    checks: dict[str, bool],
    error: str = "",
    elapsed_ms: float = 0,
) -> None:
    """테스트 결과를 기록한다."""
    result = {
        "test": test_name,
        "api_id": api_id,
        "url": url,
        "status_code": status_code,
        "passed": passed,
        "checks": checks,
        "error": error,
        "elapsed_ms": round(elapsed_ms, 1),
        "response_body": response_body,
        "timestamp": datetime.now().isoformat(),
    }
    results.append(result)

    status = "PASS" if passed else "FAIL"
    print(f"  [{status}] {test_name} ({api_id}) - {elapsed_ms:.0f}ms")
    if not passed and error:
        print(f"    → {error}")
    for check_name, check_result in checks.items():
        mark = "v" if check_result else "x"
        print(f"    [{mark}] {check_name}")


# ── 테스트 ─────────────────────────────────────────


def test_token(client: httpx.Client, app_key: str, app_secret: str) -> str | None:
    """1. 토큰 발급 테스트 (au10001)."""
    print("\n== 1. 토큰 발급 (au10001) ==")

    url = "/oauth2/token"
    headers = {
        "api-id": "au10001",
        "content-type": "application/json;charset=UTF-8",
    }
    body = {
        "grant_type": "client_credentials",
        "appkey": app_key,
        "secretkey": app_secret,
    }

    start = time.monotonic()
    try:
        resp = client.post(url, headers=headers, json=body)
        elapsed = (time.monotonic() - start) * 1000
        data = resp.json()
    except Exception as e:
        record(
            "토큰 발급",
            "au10001",
            url,
            status_code=0,
            response_body={},
            passed=False,
            checks={},
            error=str(e),
        )
        return None

    checks = {
        "token 필드 존재": "token" in data,
        "token_type 필드 존재": "token_type" in data,
        "expires_dt 필드 존재": "expires_dt" in data,
        "HTTP 200": resp.status_code == 200,
    }
    passed = all(checks.values())

    # 토큰 값 마스킹 후 저장 (보안)
    safe_data = {**data}
    if "token" in safe_data:
        token_val = safe_data["token"]
        safe_data["token"] = token_val[:8] + "***REDACTED***" if len(token_val) > 8 else "***"

    record(
        "토큰 발급",
        "au10001",
        url,
        status_code=resp.status_code,
        response_body=safe_data,
        passed=passed,
        checks=checks,
        elapsed_ms=elapsed,
    )

    return data.get("token") if passed else None


def test_quote(client: httpx.Client, token: str) -> None:
    """2. 현재가 조회 테스트 (ka10007)."""
    print("\n== 2. 현재가 조회 (ka10007) ==")

    url = "/api/dostk/mrkcond"
    headers = {
        "api-id": "ka10007",
        "authorization": f"Bearer {token}",
        "content-type": "application/json;charset=UTF-8",
    }
    body = {"stk_cd": TEST_SYMBOL}

    start = time.monotonic()
    try:
        resp = client.post(url, headers=headers, json=body)
        elapsed = (time.monotonic() - start) * 1000
        data = resp.json()
    except Exception as e:
        record(
            "현재가 조회",
            "ka10007",
            url,
            status_code=0,
            response_body={},
            passed=False,
            checks={},
            error=str(e),
        )
        return

    checks = {
        "stk_nm 필드 존재": "stk_nm" in data,
        "cur_prc 필드 존재": "cur_prc" in data,
        "pred_close_pric 필드 존재": "pred_close_pric" in data,
        "HTTP 200": resp.status_code == 200,
        "return_code 성공": data.get("return_code", -1) == 0,
    }
    passed = all(checks.values())

    record(
        "현재가 조회",
        "ka10007",
        url,
        status_code=resp.status_code,
        response_body=data,
        passed=passed,
        checks=checks,
        elapsed_ms=elapsed,
    )


def test_orderbook(client: httpx.Client, token: str) -> None:
    """3. 호가 조회 테스트 (ka10004)."""
    print("\n== 3. 호가 조회 (ka10004) ==")

    url = "/api/dostk/mrkcond"
    headers = {
        "api-id": "ka10004",
        "authorization": f"Bearer {token}",
        "content-type": "application/json;charset=UTF-8",
    }
    body = {"stk_cd": TEST_SYMBOL}

    start = time.monotonic()
    try:
        resp = client.post(url, headers=headers, json=body)
        elapsed = (time.monotonic() - start) * 1000
        data = resp.json()
    except Exception as e:
        record(
            "호가 조회",
            "ka10004",
            url,
            status_code=0,
            response_body={},
            passed=False,
            checks={},
            error=str(e),
        )
        return

    checks = {
        "sel_fpr_bid 필드 존재": "sel_fpr_bid" in data,
        "buy_fpr_bid 필드 존재": "buy_fpr_bid" in data,
        "sel_fpr_req 필드 존재": "sel_fpr_req" in data,
        "HTTP 200": resp.status_code == 200,
        "return_code 성공": data.get("return_code", -1) == 0,
    }
    passed = all(checks.values())

    record(
        "호가 조회",
        "ka10004",
        url,
        status_code=resp.status_code,
        response_body=data,
        passed=passed,
        checks=checks,
        elapsed_ms=elapsed,
    )


def test_balance(client: httpx.Client, token: str) -> None:
    """4. 잔고 조회 테스트 (ka10085)."""
    print("\n== 4. 잔고 조회 (ka10085) ==")

    url = "/api/dostk/acnt"
    headers = {
        "api-id": "ka10085",
        "authorization": f"Bearer {token}",
        "content-type": "application/json;charset=UTF-8",
    }

    body = {"stex_tp": "0"}  # 0=통합

    start = time.monotonic()
    try:
        resp = client.post(url, headers=headers, json=body)
        elapsed = (time.monotonic() - start) * 1000
        data = resp.json()
    except Exception as e:
        record(
            "잔고 조회",
            "ka10085",
            url,
            status_code=0,
            response_body={},
            passed=False,
            checks={},
            error=str(e),
        )
        return

    # 응답 구조 확인: 리스트 or 객체
    is_list = isinstance(data.get("stocks", data.get("output")), list)
    checks = {
        "HTTP 200": resp.status_code == 200,
        "응답 구조 (stocks/output이 리스트 또는 존재)": is_list or data.get("return_code", -1) == 0,
        "return_code 성공": data.get("return_code", -1) == 0,
    }
    passed = all(checks.values())

    record(
        "잔고 조회",
        "ka10085",
        url,
        status_code=resp.status_code,
        response_body=data,
        passed=passed,
        checks=checks,
        elapsed_ms=elapsed,
    )


def test_error_response(client: httpx.Client) -> None:
    """5. 에러 응답 테스트 (잘못된 토큰)."""
    print("\n== 5. 에러 응답 (잘못된 토큰) ==")

    url = "/api/dostk/mrkcond"
    headers = {
        "api-id": "ka10007",
        "authorization": "Bearer invalid_token_for_testing",
        "content-type": "application/json;charset=UTF-8",
    }
    body = {"stk_cd": TEST_SYMBOL}

    start = time.monotonic()
    try:
        resp = client.post(url, headers=headers, json=body)
        elapsed = (time.monotonic() - start) * 1000
        data = resp.json()
    except Exception as e:
        record(
            "에러 응답",
            "ka10007",
            url,
            status_code=0,
            response_body={},
            passed=False,
            checks={},
            error=str(e),
        )
        return

    checks = {
        "return_code 필드 존재": "return_code" in data,
        "return_msg 필드 존재": "return_msg" in data,
        "return_code 비-0 (에러)": data.get("return_code", 0) != 0,
    }
    passed = all(checks.values())

    record(
        "에러 응답",
        "ka10007",
        url,
        status_code=resp.status_code,
        response_body=data,
        passed=passed,
        checks=checks,
        elapsed_ms=elapsed,
    )


# ── 메인 ──────────────────────────────────────────


def main() -> None:
    """테스트 실행."""
    print("=" * 60)
    print("키움 모의투자 REST API 라이브 테스트")
    print("=" * 60)

    # .env 로드 (dotenv 있으면 사용)
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except ImportError:
        pass

    app_key = get_env_or_exit("KIWOOM_MOCK_APP_KEY")
    app_secret = get_env_or_exit("KIWOOM_MOCK_APP_SECRET")

    print(f"Base URL: {MOCK_BASE_URL}")
    print(f"App Key: {app_key[:4]}{'*' * (len(app_key) - 4)}")
    print(f"Test Symbol: {TEST_SYMBOL}")

    client = httpx.Client(
        base_url=MOCK_BASE_URL,
        timeout=httpx.Timeout(15.0, connect=5.0),
    )

    try:
        # 1. 토큰 발급
        token = test_token(client, app_key, app_secret)

        if token:
            # 2~4: 토큰 있을 때만 실행
            test_quote(client, token)
            test_orderbook(client, token)
            test_balance(client, token)

        # 5. 에러 응답 (토큰 무관)
        test_error_response(client)

    finally:
        client.close()

    # ── 결과 요약 ───────────────────────────────
    print("\n" + "=" * 60)
    total = len(results)
    passed = sum(1 for r in results if r["passed"])
    failed = total - passed
    print(f"결과: {passed}/{total} 통과, {failed} 실패")
    print("=" * 60)

    # ── 결과 저장 ───────────────────────────────
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    output_path = RESULTS_DIR / "live-test-results.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "run_at": datetime.now().isoformat(),
                "base_url": MOCK_BASE_URL,
                "test_symbol": TEST_SYMBOL,
                "summary": {"total": total, "passed": passed, "failed": failed},
                "tests": results,
            },
            f,
            ensure_ascii=False,
            indent=2,
        )
    print(f"\n결과 저장: {output_path}")


if __name__ == "__main__":
    main()
