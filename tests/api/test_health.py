"""헬스체크 엔드포인트 테스트.

Docker healthcheck 대상. 컨테이너 unhealthy 재발 방지용 회귀 테스트다.
"""

from httpx import AsyncClient


class TestHealthCheck:
    """/api/health 엔드포인트 동작 검증."""

    async def test_health_returns_200(self, client: AsyncClient) -> None:
        """헬스체크는 인증 없이 200을 반환해야 한다."""
        response = await client.get("/api/health")
        assert response.status_code == 200

    async def test_health_returns_status_ok(self, client: AsyncClient) -> None:
        """응답 본문에 status=ok가 포함되어야 한다."""
        response = await client.get("/api/health")
        body = response.json()
        assert body["status"] == "ok"

    async def test_health_returns_version(self, client: AsyncClient) -> None:
        """응답 본문에 version 필드가 포함되어야 한다."""
        response = await client.get("/api/health")
        body = response.json()
        assert "version" in body
        assert isinstance(body["version"], str)

    async def test_health_returns_trading_mode(self, client: AsyncClient) -> None:
        """응답 본문에 trading_mode가 mock 또는 real로 포함되어야 한다."""
        response = await client.get("/api/health")
        body = response.json()
        assert body["trading_mode"] in {"mock", "real"}

    async def test_health_no_auth_required(self, client: AsyncClient) -> None:
        """헬스체크는 인증 쿠키 없이도 통과해야 한다(Docker healthcheck 호환)."""
        # 쿠키 없는 client로 직접 호출
        response = await client.get("/api/health")
        # 401/403이 아니어야 함 (Docker healthcheck가 2xx를 기대)
        assert response.status_code == 200
