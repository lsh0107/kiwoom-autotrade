"""계좌 잔고 API 테스트."""

import asyncio
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from httpx import AsyncClient

from src.broker.schemas import AccountBalance, Holding
from src.models.broker import BrokerCredential
from src.models.user import User
from src.utils.exceptions import BrokerAuthError, BrokerError, BrokerRateLimitError


@pytest.fixture
def _mock_kiwoom_client() -> AsyncMock:
    """_create_kiwoom_client를 패치한 KiwoomClient 모킹."""
    mock_client = AsyncMock()
    mock_client.get_balance.return_value = AccountBalance(
        total_eval=10000000,
        total_profit=500000,
        total_profit_pct=5.26,
        available_cash=5000000,
        holdings=[
            Holding(
                symbol="005930",
                name="삼성전자",
                quantity=10,
                avg_price=65000,
                current_price=70000,
                eval_amount=700000,
                profit=50000,
                profit_pct=7.69,
            )
        ],
    )
    mock_client.close.return_value = None
    return mock_client


class TestGetBalance:
    """잔고 조회 테스트."""

    async def test_get_balance(
        self,
        auth_client: AsyncClient,
        test_user: User,
        broker_credential: BrokerCredential,
        _mock_kiwoom_client: AsyncMock,
    ) -> None:
        """인증된 사용자가 잔고를 조회하면 200 응답."""
        with patch(
            "src.api.v1.account._create_kiwoom_client",
            return_value=_mock_kiwoom_client,
        ):
            resp = await auth_client.get("/api/v1/account/balance")

        assert resp.status_code == 200
        data = resp.json()
        assert data["total_eval"] == 10000000
        assert data["available_cash"] == 5000000
        assert data["total_profit"] == 500000
        assert len(data["holdings"]) == 1
        assert data["holdings"][0]["symbol"] == "005930"
        assert data["holdings"][0]["name"] == "삼성전자"

    async def test_get_balance_no_credential(
        self,
        auth_client: AsyncClient,
        test_user: User,
    ) -> None:
        """자격증명 없으면 422 (NO_CREDENTIALS)."""
        resp = await auth_client.get("/api/v1/account/balance")
        assert resp.status_code == 422
        assert resp.json()["error"] == "NO_CREDENTIALS"


class TestAccountUnauthenticated:
    """미인증 계좌 API 테스트."""

    async def test_unauthenticated(self, client: AsyncClient) -> None:
        """미인증 시 잔고 조회 → 401."""
        resp = await client.get("/api/v1/account/balance")
        assert resp.status_code == 401


class TestGetBalanceFailFast:
    """HOTFIX (2026-05-27) — 외부 키움 API hang/오류 시 fail-fast.

    캐시 격리: 각 테스트 시작 전 ``_balance_cache`` 클리어.
    """

    @pytest.fixture(autouse=True)
    def _clear_balance_cache(self) -> None:
        from src.api.v1 import account as account_mod

        account_mod._balance_cache.clear()

    async def _patched_call(
        self,
        auth_client: AsyncClient,
        side_effect,
        *,
        timeout_override: float | None = None,
    ):
        """공통: KiwoomClient.get_balance() 가 side_effect 를 raise 하도록 mock."""
        from src.api.v1 import account as account_mod

        mock_client = AsyncMock()
        mock_client.get_balance.side_effect = side_effect
        mock_client.close.return_value = None
        patches = [
            patch(
                "src.api.v1.account._create_kiwoom_client",
                return_value=mock_client,
            )
        ]
        if timeout_override is not None:
            patches.append(
                patch.object(
                    account_mod,
                    "BALANCE_UPSTREAM_TIMEOUT_SEC",
                    timeout_override,
                )
            )
        for p in patches:
            p.start()
        try:
            return await auth_client.get("/api/v1/account/balance"), mock_client
        finally:
            for p in patches:
                p.stop()

    async def test_upstream_hang_returns_504_within_timeout(
        self,
        auth_client: AsyncClient,
        test_user: User,
        broker_credential: BrokerCredential,
    ) -> None:
        """upstream 이 timeout 보다 오래 hang 하면 504 + 합리적 시간 내 반환."""

        async def hang(*_a, **_kw):
            await asyncio.sleep(10.0)  # timeout_override(0.2) 보다 크게.
            return

        import time as _time

        started = _time.monotonic()
        resp, _ = await self._patched_call(auth_client, side_effect=hang, timeout_override=0.2)
        elapsed = _time.monotonic() - started

        assert resp.status_code == 504
        assert "키움 잔고 API 응답 없음" in resp.json()["message"]
        # fail-fast: 사용자가 본 15~60초 hang 보다 한참 작아야 함.
        assert elapsed < 5.0, f"504 응답까지 {elapsed:.2f}s — fail-fast 위반"

    async def test_httpx_read_timeout_returns_502(
        self,
        auth_client: AsyncClient,
        test_user: User,
        broker_credential: BrokerCredential,
    ) -> None:
        """upstream httpx.ReadTimeout 은 502 로 변환."""
        resp, _ = await self._patched_call(
            auth_client, side_effect=httpx.ReadTimeout("upstream read timeout")
        )
        assert resp.status_code == 502
        assert "ReadTimeout" in resp.json()["message"]

    async def test_broker_auth_error_returns_502(
        self,
        auth_client: AsyncClient,
        test_user: User,
        broker_credential: BrokerCredential,
    ) -> None:
        """키움 토큰 오류는 502 + error_class 로깅."""
        resp, _ = await self._patched_call(
            auth_client,
            side_effect=BrokerAuthError("토큰 발급 실패: invalid app key"),
        )
        assert resp.status_code == 502
        assert "BrokerAuthError" in resp.json()["message"]

    async def test_broker_rate_limit_returns_502(
        self,
        auth_client: AsyncClient,
        test_user: User,
        broker_credential: BrokerCredential,
    ) -> None:
        """rate limit 소진은 502."""
        resp, _ = await self._patched_call(auth_client, side_effect=BrokerRateLimitError())
        assert resp.status_code == 502
        assert "BrokerRateLimitError" in resp.json()["message"]

    async def test_generic_broker_error_returns_502(
        self,
        auth_client: AsyncClient,
        test_user: User,
        broker_credential: BrokerCredential,
    ) -> None:
        """기타 broker 오류는 502."""
        resp, _ = await self._patched_call(
            auth_client, side_effect=BrokerError("[9999] 알 수 없는 키움 오류")
        )
        assert resp.status_code == 502
        assert "BrokerError" in resp.json()["message"]

    async def test_failure_does_not_populate_cache(
        self,
        auth_client: AsyncClient,
        test_user: User,
        broker_credential: BrokerCredential,
    ) -> None:
        """실패 응답은 캐시에 저장되지 않아 다음 호출에서 재시도 가능해야 함.

        정책: timeout/upstream 실패를 가짜 잔고로 조용히 처리 금지.
        """
        from src.api.v1 import account as account_mod

        account_mod._balance_cache.clear()
        resp, _ = await self._patched_call(
            auth_client,
            side_effect=BrokerError("[9999] 일시 오류"),
        )
        assert resp.status_code == 502
        assert account_mod._balance_cache == {}

    async def test_kiwoom_client_close_called_even_on_timeout(
        self,
        auth_client: AsyncClient,
        test_user: User,
        broker_credential: BrokerCredential,
    ) -> None:
        """timeout 발생해도 KiwoomClient.close 가 호출되어 connection leak 방지."""

        async def hang(*_a, **_kw):
            await asyncio.sleep(10.0)
            return

        resp, mock_client = await self._patched_call(
            auth_client, side_effect=hang, timeout_override=0.2
        )
        assert resp.status_code == 504
        mock_client.close.assert_awaited()
