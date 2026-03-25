"""LLM 결정 API 테스트."""

import uuid
from datetime import date

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.llm_decision import LLMDecision


async def _create_decision(
    db: AsyncSession,
    *,
    decision_type: str = "weight_adjust",
    status: str = "pending",
    context_source: str = "overnight",
) -> LLMDecision:
    """테스트용 결정 생성 헬퍼."""
    decision = LLMDecision(
        date=date(2026, 3, 25),
        decision_type=decision_type,
        context_source=context_source,
        content={"target": "삼성전자", "weight": 0.15},
        confidence=0.85,
        status=status,
    )
    db.add(decision)
    await db.flush()
    return decision


class TestListDecisions:
    """GET /api/v1/decisions 테스트."""

    async def test_empty_list(self, auth_client: AsyncClient) -> None:
        """결정 없으면 빈 목록."""
        resp = await auth_client.get("/api/v1/decisions")
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_list_all(self, auth_client: AsyncClient, db: AsyncSession) -> None:
        """모든 결정을 반환한다."""
        await _create_decision(db, status="pending")
        await _create_decision(db, status="approved")

        resp = await auth_client.get("/api/v1/decisions")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2

    async def test_filter_by_status(self, auth_client: AsyncClient, db: AsyncSession) -> None:
        """status 필터."""
        await _create_decision(db, status="pending")
        await _create_decision(db, status="approved")

        resp = await auth_client.get("/api/v1/decisions?status=pending")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["status"] == "pending"

    async def test_requires_auth(self, client: AsyncClient) -> None:
        """미인증 요청 거부."""
        resp = await client.get("/api/v1/decisions")
        assert resp.status_code in (401, 403)


class TestApproveDecision:
    """POST /api/v1/decisions/{id}/approve 테스트."""

    async def test_approve_pending(self, auth_client: AsyncClient, db: AsyncSession) -> None:
        """pending 결정 승인."""
        decision = await _create_decision(db)

        resp = await auth_client.post(f"/api/v1/decisions/{decision.id}/approve")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "approved"
        assert data["applied_at"] is not None

    async def test_approve_already_processed(
        self, auth_client: AsyncClient, db: AsyncSession
    ) -> None:
        """이미 처리된 결정 → 409."""
        decision = await _create_decision(db, status="approved")

        resp = await auth_client.post(f"/api/v1/decisions/{decision.id}/approve")
        assert resp.status_code == 409

    async def test_approve_nonexistent(self, auth_client: AsyncClient) -> None:
        """존재하지 않는 ID → 404."""
        fake_id = uuid.uuid4()
        resp = await auth_client.post(f"/api/v1/decisions/{fake_id}/approve")
        assert resp.status_code == 404


class TestRejectDecision:
    """POST /api/v1/decisions/{id}/reject 테스트."""

    async def test_reject_pending(self, auth_client: AsyncClient, db: AsyncSession) -> None:
        """pending 결정 거부."""
        decision = await _create_decision(db)

        resp = await auth_client.post(f"/api/v1/decisions/{decision.id}/reject")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "rejected"

    async def test_reject_already_processed(
        self, auth_client: AsyncClient, db: AsyncSession
    ) -> None:
        """이미 처리된 결정 → 409."""
        decision = await _create_decision(db, status="rejected")

        resp = await auth_client.post(f"/api/v1/decisions/{decision.id}/reject")
        assert resp.status_code == 409
