"""전략 파라미터 설정 API 테스트."""

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.strategy_config import StrategyConfig, StrategyConfigSuggestion


class TestGetStrategyConfig:
    """GET /api/v1/settings/strategy 테스트."""

    async def test_get_empty_config(self, auth_client: AsyncClient) -> None:
        """파라미터 없으면 빈 목록."""
        resp = await auth_client.get("/api/v1/settings/strategy")
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_get_existing_config(self, auth_client: AsyncClient, db: AsyncSession) -> None:
        """저장된 파라미터 조회."""
        cfg = StrategyConfig(
            key="atr_stop_mult",
            value=1.5,
            description="ATR 손절 승수",
            updated_by="system",
        )
        db.add(cfg)
        await db.flush()

        resp = await auth_client.get("/api/v1/settings/strategy")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["key"] == "atr_stop_mult"
        assert data[0]["value"] == 1.5

    async def test_requires_auth(self, client: AsyncClient) -> None:
        """미인증 요청 거부."""
        resp = await client.get("/api/v1/settings/strategy")
        assert resp.status_code in (401, 403)


class TestUpdateStrategyConfig:
    """PUT /api/v1/settings/strategy 테스트."""

    async def test_create_new_config(self, admin_client: AsyncClient) -> None:
        """존재하지 않는 key → 신규 생성."""
        resp = await admin_client.put(
            "/api/v1/settings/strategy",
            json={
                "items": [
                    {
                        "key": "max_positions",
                        "value": 5,
                        "description": "최대 포지션",
                        "updated_by": "user",
                    }
                ]
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["key"] == "max_positions"
        assert data[0]["value"] == 5
        assert data[0]["updated_by"] == "user"

    async def test_update_existing_config(
        self, admin_client: AsyncClient, db: AsyncSession
    ) -> None:
        """기존 key → value 업데이트."""
        cfg = StrategyConfig(
            key="volume_ratio",
            value=1.5,
            description="거래량 배수",
            updated_by="system",
        )
        db.add(cfg)
        await db.flush()

        resp = await admin_client.put(
            "/api/v1/settings/strategy",
            json={
                "items": [
                    {
                        "key": "volume_ratio",
                        "value": 2.0,
                        "description": "",
                        "updated_by": "user",
                    }
                ]
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data[0]["value"] == 2.0
        assert data[0]["updated_by"] == "user"

    async def test_update_multiple_items(self, admin_client: AsyncClient) -> None:
        """여러 항목 동시 수정."""
        resp = await admin_client.put(
            "/api/v1/settings/strategy",
            json={
                "items": [
                    {"key": "take_profit", "value": 0.02, "description": "", "updated_by": "user"},
                    {"key": "stop_loss", "value": -0.01, "description": "", "updated_by": "user"},
                ]
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        keys = {item["key"] for item in data}
        assert "take_profit" in keys
        assert "stop_loss" in keys

    async def test_update_requires_admin(self, auth_client: AsyncClient) -> None:
        """일반 사용자 → 권한 부족 거부."""
        resp = await auth_client.put(
            "/api/v1/settings/strategy",
            json={"items": [{"key": "k", "value": 1, "description": "", "updated_by": "user"}]},
        )
        assert resp.status_code == 403

    async def test_update_requires_auth(self, client: AsyncClient) -> None:
        """미인증 요청 거부."""
        resp = await client.put(
            "/api/v1/settings/strategy",
            json={"items": [{"key": "k", "value": 1, "description": "", "updated_by": "user"}]},
        )
        assert resp.status_code in (401, 403)


class TestStrategyConfigSuggestions:
    """제안 관련 엔드포인트 테스트."""

    async def test_list_pending_suggestions_empty(self, auth_client: AsyncClient) -> None:
        """제안 없으면 빈 목록."""
        resp = await auth_client.get("/api/v1/settings/strategy/suggestions")
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_list_pending_suggestions(
        self, auth_client: AsyncClient, db: AsyncSession
    ) -> None:
        """pending 제안만 반환 (approved 제외)."""
        pending = StrategyConfigSuggestion(
            config_key="atr_stop_mult",
            current_value=1.5,
            suggested_value=2.0,
            reason="테스트 제안",
            source="param_tuner",
            status="pending",
        )
        approved = StrategyConfigSuggestion(
            config_key="volume_ratio",
            current_value=1.5,
            suggested_value=2.0,
            reason="이미 승인됨",
            source="param_tuner",
            status="approved",
        )
        db.add(pending)
        db.add(approved)
        await db.flush()

        resp = await auth_client.get("/api/v1/settings/strategy/suggestions")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["config_key"] == "atr_stop_mult"
        assert data[0]["status"] == "pending"

    async def test_approve_suggestion(self, auth_client: AsyncClient, db: AsyncSession) -> None:
        """제안 승인 → status=approved, strategy_config 업데이트."""
        suggestion = StrategyConfigSuggestion(
            config_key="max_positions",
            current_value=3,
            suggested_value=5,
            reason="분산 투자",
            source="postmarket_review",
            status="pending",
        )
        db.add(suggestion)
        await db.flush()

        resp = await auth_client.post(
            f"/api/v1/settings/strategy/suggestions/{suggestion.id}/approve",
            json={"reviewed_by": "test_user"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "approved"
        assert data["reviewed_by"] == "test_user"

        # strategy_config에 반영됐는지 확인
        from sqlalchemy import select

        result = await db.execute(
            select(StrategyConfig).where(StrategyConfig.key == "max_positions")
        )
        cfg = result.scalar_one_or_none()
        assert cfg is not None
        assert cfg.value == 5

    async def test_reject_suggestion(self, auth_client: AsyncClient, db: AsyncSession) -> None:
        """제안 거부 → status=rejected."""
        suggestion = StrategyConfigSuggestion(
            config_key="stop_loss",
            current_value=-0.005,
            suggested_value=-0.010,
            reason="손절 강화",
            source="param_tuner",
            status="pending",
        )
        db.add(suggestion)
        await db.flush()

        resp = await auth_client.post(
            f"/api/v1/settings/strategy/suggestions/{suggestion.id}/reject",
            json={"reviewed_by": "user"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "rejected"

    async def test_approve_already_processed_suggestion(
        self, auth_client: AsyncClient, db: AsyncSession
    ) -> None:
        """이미 처리된 제안 재승인 → 409."""
        suggestion = StrategyConfigSuggestion(
            config_key="take_profit",
            current_value=0.015,
            suggested_value=0.020,
            reason="수익 상향",
            source="param_tuner",
            status="rejected",
        )
        db.add(suggestion)
        await db.flush()

        resp = await auth_client.post(
            f"/api/v1/settings/strategy/suggestions/{suggestion.id}/approve",
            json={"reviewed_by": "user"},
        )
        assert resp.status_code == 409

    async def test_approve_nonexistent_suggestion(self, auth_client: AsyncClient) -> None:
        """존재하지 않는 제안 ID → 404."""
        import uuid

        fake_id = uuid.uuid4()
        resp = await auth_client.post(
            f"/api/v1/settings/strategy/suggestions/{fake_id}/approve",
            json={"reviewed_by": "user"},
        )
        assert resp.status_code == 404
