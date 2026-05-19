"""LLM 결정 API 테스트."""

import uuid
from datetime import date

from httpx import AsyncClient
from sqlalchemy import select
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


class TestCreateDecisionDrafts:
    """POST /api/v1/decisions/drafts 테스트."""

    async def test_create_symbol_bias_draft(
        self, auth_client: AsyncClient, db: AsyncSession
    ) -> None:
        """AI hedge draft를 pending LLMDecision으로 저장한다."""
        payload = [
            {
                "date": "2026-05-19",
                "decision_type": "symbol_bias",
                "context_source": "ai_hedge",
                "content": {
                    "symbol": "005930",
                    "bias": "block_buy",
                    "source": "kr-ai-hedge",
                    "reason": "종목 비중 한도 초과",
                },
                "confidence": 0.5,
                "status": "pending",
                "raw_response": '{"symbol":"005930"}',
            }
        ]

        resp = await auth_client.post("/api/v1/decisions/drafts", json=payload)

        assert resp.status_code == 201
        data = resp.json()
        assert len(data) == 1
        assert data[0]["status"] == "pending"
        assert data[0]["decision_type"] == "symbol_bias"
        assert data[0]["content"]["bias"] == "block_buy"
        assert data[0]["applied_at"] is None

        result = await db.execute(
            select(LLMDecision).where(LLMDecision.id == uuid.UUID(data[0]["id"]))
        )
        row = result.scalar_one()
        assert row.status == "pending"
        assert row.content["symbol"] == "005930"

    async def test_create_multiple_drafts(self, auth_client: AsyncClient) -> None:
        """여러 draft를 한 번에 저장한다."""
        payload = [
            {
                "date": "2026-05-19",
                "decision_type": "symbol_bias",
                "context_source": "ai_hedge",
                "content": {"symbol": "005930", "bias": "block_buy"},
                "confidence": 0.5,
            },
            {
                "date": "2026-05-19",
                "decision_type": "universe_adjust",
                "context_source": "ai_hedge",
                "content": {"exclude": ["000660"]},
                "confidence": 0.7,
            },
        ]

        resp = await auth_client.post("/api/v1/decisions/drafts", json=payload)

        assert resp.status_code == 201
        assert len(resp.json()) == 2

    async def test_rejects_approved_status_injection(self, auth_client: AsyncClient) -> None:
        """외부 draft가 approved/applied 상태를 주입할 수 없다."""
        payload = [
            {
                "date": "2026-05-19",
                "decision_type": "symbol_bias",
                "context_source": "ai_hedge",
                "content": {"symbol": "005930", "bias": "block_buy"},
                "confidence": 0.5,
                "status": "approved",
            }
        ]

        resp = await auth_client.post("/api/v1/decisions/drafts", json=payload)

        assert resp.status_code == 422

    async def test_rejects_invalid_symbol_bias(self, auth_client: AsyncClient) -> None:
        """symbol_bias는 6자리 한국 종목코드만 허용한다."""
        payload = [
            {
                "date": "2026-05-19",
                "decision_type": "symbol_bias",
                "context_source": "ai_hedge",
                "content": {"symbol": "AAPL", "bias": "block_buy"},
                "confidence": 0.5,
            }
        ]

        resp = await auth_client.post("/api/v1/decisions/drafts", json=payload)

        assert resp.status_code == 422

    async def test_rejects_empty_draft_list(self, auth_client: AsyncClient) -> None:
        """빈 draft 목록은 거부한다."""
        resp = await auth_client.post("/api/v1/decisions/drafts", json=[])

        assert resp.status_code == 422

    async def test_requires_auth(self, client: AsyncClient) -> None:
        """미인증 draft 생성 요청 거부."""
        resp = await client.post("/api/v1/decisions/drafts", json=[])

        assert resp.status_code in (401, 403)


class TestApproveDecision:
    """POST /api/v1/decisions/{id}/approve 테스트."""

    async def test_approve_pending(self, auth_client: AsyncClient, db: AsyncSession) -> None:
        """pending 결정 승인 — applied_at은 세팅되지 않는다 (approve ≠ applied)."""
        decision = await _create_decision(db)

        resp = await auth_client.post(f"/api/v1/decisions/{decision.id}/approve")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "approved"
        assert data["applied_at"] is None

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


class TestMarkDecisionsApplied:
    """mark_decisions_applied 단위 테스트."""

    async def test_mark_applied_updates_status_and_timestamp(self, db: AsyncSession) -> None:
        """mark_decisions_applied 호출 시 status=applied, applied_at 채워진다."""
        from src.trading.llm_decision_loader import mark_decisions_applied

        d1 = await _create_decision(db, status="approved")
        d2 = await _create_decision(db, status="approved")
        await db.flush()

        await mark_decisions_applied(db, [d1.id, d2.id])
        await db.flush()

        # DB에서 다시 읽기
        await db.refresh(d1)
        await db.refresh(d2)
        assert d1.status == "applied"
        assert d1.applied_at is not None
        assert d2.status == "applied"
        assert d2.applied_at is not None

    async def test_mark_applied_empty_list_noop(self, db: AsyncSession) -> None:
        """빈 리스트는 no-op."""
        from src.trading.llm_decision_loader import mark_decisions_applied

        await mark_decisions_applied(db, [])  # 예외 없이 통과
