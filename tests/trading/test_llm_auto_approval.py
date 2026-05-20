"""LLM 자동 승인 모듈 테스트."""

from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.llm_decision import LLMDecision
from src.trading.llm_auto_approval import (
    _validate_decision,
    _validate_strategy_param_hint,
    auto_approve_pending,
)


def _make_decision(
    *,
    decision_type: str = "strategy_param_hint",
    confidence: float | None = 0.8,
    content: dict | None = None,
    status: str = "pending",
    context_source: str = "overnight",
) -> LLMDecision:
    return LLMDecision(
        date=date(2026, 5, 8),
        decision_type=decision_type,
        context_source=context_source,
        content=content or {"params": {"volume_ratio": 1.2}},
        confidence=confidence,
        status=status,
        raw_response="",
    )


# ── _validate_strategy_param_hint ───────────────────────────────────────────


class TestValidateStrategyParamHint:
    def test_valid_whitelist_in_range(self) -> None:
        ok, reason = _validate_strategy_param_hint({"params": {"volume_ratio": 1.0}})
        assert ok
        assert reason == ""

    def test_invalid_key_outside_whitelist(self) -> None:
        ok, reason = _validate_strategy_param_hint({"params": {"unknown_key": 0.5}})
        assert not ok
        assert "whitelist" in reason

    def test_invalid_value_out_of_range(self) -> None:
        ok, reason = _validate_strategy_param_hint({"params": {"volume_ratio": 5.0}})
        assert not ok
        assert "범위" in reason

    def test_strategy_meta_keys_skipped(self) -> None:
        # strategy/reason 같은 메타 키는 무시
        ok, _reason = _validate_strategy_param_hint(
            {"strategy": "momentum", "reason": "test", "params": {"atr_stop_mult": 2.0}}
        )
        assert ok

    def test_empty_params_rejected(self) -> None:
        ok, reason = _validate_strategy_param_hint({})
        assert not ok
        assert "비어있" in reason

    def test_flat_dict_format_supported(self) -> None:
        # params 키 없이 직접 키-값
        ok, _ = _validate_strategy_param_hint({"volume_ratio": 1.5})
        assert ok


# ── _validate_decision ──────────────────────────────────────────────────────


class TestValidateDecision:
    def test_low_confidence_rejected(self) -> None:
        d = _make_decision(confidence=0.3)
        ok, reason = _validate_decision(d, min_confidence=0.6)
        assert not ok
        assert "confidence" in reason

    def test_none_confidence_rejected(self) -> None:
        d = _make_decision(confidence=None)
        ok, _reason = _validate_decision(d, min_confidence=0.6)
        assert not ok

    def test_unsupported_type_rejected(self) -> None:
        d = _make_decision(decision_type="weight_adjust", confidence=0.9)
        ok, reason = _validate_decision(d, min_confidence=0.6)
        assert not ok
        assert "unsupported" in reason

    def test_symbol_bias_freeform_passes(self) -> None:
        d = _make_decision(
            decision_type="symbol_bias",
            confidence=0.8,
            content={"symbol": "005930", "bias": "+0.2"},
        )
        ok, _reason = _validate_decision(d, min_confidence=0.6)
        assert ok

    def test_strategy_param_hint_invalid_content_rejected(self) -> None:
        d = _make_decision(confidence=0.9, content={"params": {"unknown": 1.0}})
        ok, _reason = _validate_decision(d, min_confidence=0.6)
        assert not ok


# ── auto_approve_pending (DB 통합) ──────────────────────────────────────────


@pytest.mark.asyncio
class TestAutoApprovePending:
    async def test_approves_high_confidence_valid(self, db: AsyncSession) -> None:
        d = _make_decision(confidence=0.8)
        db.add(d)
        await db.commit()

        counts = await auto_approve_pending(db=db, min_confidence=0.6)
        assert counts["approved"] == 1
        assert counts["rejected"] == 0

        await db.refresh(d)
        assert d.status == "approved"

    async def test_rejects_low_confidence(self, db: AsyncSession) -> None:
        d = _make_decision(confidence=0.3)
        db.add(d)
        await db.commit()

        counts = await auto_approve_pending(db=db, min_confidence=0.6)
        assert counts["rejected"] == 1
        assert counts["approved"] == 0

        await db.refresh(d)
        assert d.status == "auto_rejected"

    async def test_skips_when_manual_rejection_exists(self, db: AsyncSession) -> None:
        # 같은 date+type에 manual rejected가 있으면 skip
        manual = _make_decision(confidence=0.9, status="rejected")
        pending = _make_decision(confidence=0.9)
        db.add_all([manual, pending])
        await db.commit()

        counts = await auto_approve_pending(db=db, min_confidence=0.6)
        assert counts["skipped"] == 1
        assert counts["approved"] == 0

        await db.refresh(pending)
        assert pending.status == "pending"  # 유지

    async def test_max_per_run_caps_processing(self, db: AsyncSession) -> None:
        for _ in range(5):
            db.add(_make_decision(confidence=0.8))
        await db.commit()

        counts = await auto_approve_pending(db=db, min_confidence=0.6, max_per_run=2)
        assert counts["approved"] == 2

        # 나머지 3건 pending 유지
        result = await db.execute(select(LLMDecision).where(LLMDecision.status == "pending"))
        assert len(list(result.scalars().all())) == 3

    async def test_skips_ai_hedge_high_confidence(self, db: AsyncSession) -> None:
        # ai_hedge context_source는 confidence가 임계값 이상이어도 자동 승인되지 않고 skip.
        d = _make_decision(
            decision_type="symbol_bias",
            confidence=0.9,
            content={"symbol": "005930", "bias": "block_buy"},
            context_source="ai_hedge",
        )
        db.add(d)
        await db.commit()

        counts = await auto_approve_pending(db=db, min_confidence=0.6)
        assert counts["skipped"] == 1
        assert counts["approved"] == 0
        assert counts["rejected"] == 0

        await db.refresh(d)
        assert d.status == "pending"

    async def test_skips_ai_hedge_low_confidence(self, db: AsyncSession) -> None:
        # ai_hedge는 confidence가 낮아도 auto_rejected 되지 않고 pending 유지.
        d = _make_decision(
            decision_type="symbol_bias",
            confidence=0.3,
            content={"symbol": "005930", "bias": "block_buy"},
            context_source="ai_hedge",
        )
        db.add(d)
        await db.commit()

        counts = await auto_approve_pending(db=db, min_confidence=0.6)
        assert counts["skipped"] == 1
        assert counts["rejected"] == 0
        assert counts["approved"] == 0

        await db.refresh(d)
        assert d.status == "pending"

    async def test_overnight_still_processed_alongside_ai_hedge(self, db: AsyncSession) -> None:
        # ai_hedge skip이 도입돼도 overnight 자동 승인은 그대로 동작.
        ovn = _make_decision(confidence=0.8, context_source="overnight")
        aih = _make_decision(
            decision_type="symbol_bias",
            confidence=0.9,
            content={"symbol": "005930", "bias": "block_buy"},
            context_source="ai_hedge",
        )
        db.add_all([ovn, aih])
        await db.commit()

        counts = await auto_approve_pending(db=db, min_confidence=0.6)
        assert counts["approved"] == 1
        assert counts["skipped"] == 1
        assert counts["rejected"] == 0

        await db.refresh(ovn)
        await db.refresh(aih)
        assert ovn.status == "approved"
        assert aih.status == "pending"
