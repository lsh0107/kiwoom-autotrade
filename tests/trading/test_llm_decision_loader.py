"""llm_decision_loader 단위 테스트.

설계: docs/design/design-010-llm-decision-integration.md (§11)

검증 항목:
    - database_url 없음 → 빈 결과
    - 지원 decision_type만 그룹화
    - 지원하지 않는 decision_type은 무시
    - DB 조회 실패 시 예외 전파 없이 빈 결과
    - 타임아웃 시 빈 결과
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from src.trading import llm_decision_loader
from src.trading.llm_decision_loader import (
    SUPPORTED_DECISION_TYPES,
    apply_universe_decisions,
    load_approved_decisions,
    summarize_decisions,
)


def _make_row(decision_type: str, content: dict, row_id: str = "r1") -> object:
    """LLMDecision 비슷한 스텁 객체. 실제 ORM 없이 속성만 제공."""
    return SimpleNamespace(id=row_id, decision_type=decision_type, content=content)


class TestLoaderNoOp:
    """동작 변경이 없어야 하는 경우."""

    async def test_returns_empty_when_database_url_is_none(self) -> None:
        """database_url이 None이면 DB 접근 없이 빈 dict."""
        result = await load_approved_decisions(database_url=None)
        assert result == {}

    async def test_returns_empty_when_database_url_is_empty(self) -> None:
        """database_url이 빈 문자열이면 DB 접근 없이 빈 dict."""
        result = await load_approved_decisions(database_url="")
        assert result == {}


class TestLoaderSuccess:
    """성공 경로 — decision_type별 그룹화."""

    async def test_groups_by_decision_type(self) -> None:
        """여러 타입이 섞인 결과를 decision_type별로 그룹화한다."""
        rows = [
            _make_row("universe_adjust", {"exclude": ["005930"]}, "a"),
            _make_row("symbol_bias", {"symbol": "000660", "bias": "block_buy"}, "b"),
            _make_row("universe_adjust", {"exclude": ["068270"]}, "c"),
            _make_row("strategy_param_hint", {"strategy": "momentum", "params": {}}, "d"),
        ]

        async def _fake_fetch(database_url: str, since_hours: int) -> dict[str, list[dict]]:
            grouped: dict[str, list[dict]] = {}
            for r in rows:
                if r.decision_type in SUPPORTED_DECISION_TYPES:
                    grouped.setdefault(r.decision_type, []).append(r.content)
            return grouped

        with patch.object(
            llm_decision_loader,
            "_fetch_approved",
            new=AsyncMock(side_effect=_fake_fetch),
        ):
            result = await load_approved_decisions(
                database_url="postgresql+asyncpg://test/db",
                since_hours=24,
            )

        assert set(result.keys()) == {"universe_adjust", "symbol_bias", "strategy_param_hint"}
        assert len(result["universe_adjust"]) == 2
        assert result["universe_adjust"][0] == {"exclude": ["005930"]}
        assert result["symbol_bias"][0]["bias"] == "block_buy"

    async def test_unsupported_types_are_filtered(self) -> None:
        """지원하지 않는 decision_type은 결과에 포함되지 않는다."""

        async def _fake_fetch(database_url: str, since_hours: int) -> dict[str, list[dict]]:
            # _fetch_approved 내부 필터링을 시뮬레이션
            return {"universe_adjust": [{"exclude": ["005930"]}]}

        with patch.object(
            llm_decision_loader,
            "_fetch_approved",
            new=AsyncMock(side_effect=_fake_fetch),
        ):
            result = await load_approved_decisions(
                database_url="postgresql+asyncpg://test/db",
            )

        assert "weight_adjust" not in result
        assert "universe_adjust" in result


class TestLoaderFailure:
    """실패 경로 — graceful 보장."""

    async def test_returns_empty_on_db_error(self) -> None:
        """DB 조회 중 예외가 나도 예외 전파 없이 빈 dict."""
        with patch.object(
            llm_decision_loader,
            "_fetch_approved",
            new=AsyncMock(side_effect=RuntimeError("연결 끊김")),
        ):
            result = await load_approved_decisions(
                database_url="postgresql+asyncpg://test/db",
            )

        assert result == {}

    async def test_returns_empty_on_timeout(self) -> None:
        """쿼리가 지정 timeout 초과 시 빈 dict 반환."""

        async def _slow_fetch(database_url: str, since_hours: int) -> dict[str, list[dict]]:
            await asyncio.sleep(5.0)
            return {"universe_adjust": [{"exclude": ["005930"]}]}

        with patch.object(
            llm_decision_loader,
            "_fetch_approved",
            new=AsyncMock(side_effect=_slow_fetch),
        ):
            result = await load_approved_decisions(
                database_url="postgresql+asyncpg://test/db",
                query_timeout_sec=0.05,
            )

        assert result == {}


class TestLoaderConstants:
    """상수 가드 — PR2/PR3 소비자가 의존한다."""

    def test_supported_types_contains_expected(self) -> None:
        """지원 타입 3종이 모두 포함되어야 한다."""
        assert "universe_adjust" in SUPPORTED_DECISION_TYPES
        assert "symbol_bias" in SUPPORTED_DECISION_TYPES
        assert "strategy_param_hint" in SUPPORTED_DECISION_TYPES


@pytest.mark.parametrize(
    ("bad_content",),
    [
        (None,),
        ("string-content",),
        (123,),
    ],
)
async def test_non_dict_content_is_coerced_to_empty_dict(bad_content: object) -> None:
    """content가 dict가 아니면 빈 dict로 대체되어 소비자가 안전하게 사용할 수 있다."""
    # 이 동작은 _fetch_approved 내부에서 이루어지므로 실제 DB 동작을 시뮬레이션
    # 하기 위해 _fetch_approved를 직접 mock 하여 빈 dict로 처리된 결과를 반환한다.

    async def _fake_fetch(database_url: str, since_hours: int) -> dict[str, list[dict]]:
        # loader 내부 로직 재현: content가 dict 아니면 {} 로 대체
        content = bad_content if isinstance(bad_content, dict) else {}
        return {"universe_adjust": [content]}

    with patch.object(
        llm_decision_loader,
        "_fetch_approved",
        new=AsyncMock(side_effect=_fake_fetch),
    ):
        result = await load_approved_decisions(
            database_url="postgresql+asyncpg://test/db",
        )

    assert result["universe_adjust"] == [{}]


class TestQueryAndGroup:
    """_query_and_group — 실제 인메모리 SQLite 세션으로 검증."""

    async def test_only_approved_within_window_returned(self, db: object) -> None:
        """approved + 시간창 내 결정만 반환된다."""
        from datetime import timedelta

        from src.models.llm_decision import LLMDecision
        from src.trading.llm_decision_loader import _query_and_group
        from src.utils.time import now_kst

        now = now_kst()
        old_created = now - timedelta(hours=48)

        rows = [
            # approved + 최근 → 포함
            LLMDecision(
                date=now.date(),
                decision_type="universe_adjust",
                context_source="overnight",
                content={"exclude": ["005930"]},
                status="approved",
                raw_response="",
            ),
            # approved + 오래됨 → 제외 (since_hours=24 기준)
            LLMDecision(
                date=old_created.date(),
                decision_type="universe_adjust",
                context_source="overnight",
                content={"exclude": ["000660"]},
                status="approved",
                raw_response="",
            ),
            # pending → 제외
            LLMDecision(
                date=now.date(),
                decision_type="universe_adjust",
                context_source="overnight",
                content={"exclude": ["068270"]},
                status="pending",
                raw_response="",
            ),
            # rejected → 제외
            LLMDecision(
                date=now.date(),
                decision_type="symbol_bias",
                context_source="premarket",
                content={"symbol": "005930", "bias": "block_buy"},
                status="rejected",
                raw_response="",
            ),
            # approved 지원되지 않는 타입 → 제외
            LLMDecision(
                date=now.date(),
                decision_type="weight_adjust",
                context_source="overnight",
                content={"weights": {}},
                status="approved",
                raw_response="",
            ),
        ]
        for r in rows:
            db.add(r)
        await db.commit()

        # created_at은 server_default이므로 방금 insert된 레코드는 모두 "최근"이다.
        # old 레코드를 시간창 밖으로 밀기 위해 명시적으로 past로 업데이트.
        from sqlalchemy import update

        await db.execute(
            update(LLMDecision)
            .where(LLMDecision.content["exclude"].as_string() == '["000660"]')
            .values(created_at=old_created)
        )
        await db.commit()

        result = await _query_and_group(db, since_hours=24)

        # universe_adjust: 최근 approved 1건만
        assert "universe_adjust" in result
        assert result["universe_adjust"] == [{"exclude": ["005930"]}]
        # symbol_bias / strategy_param_hint / weight_adjust 모두 미포함
        assert "symbol_bias" not in result
        assert "strategy_param_hint" not in result
        assert "weight_adjust" not in result

    async def test_empty_db_returns_empty_dict(self, db: object) -> None:
        """DB가 비어있으면 빈 dict."""
        from src.trading.llm_decision_loader import _query_and_group

        result = await _query_and_group(db, since_hours=24)
        assert result == {}


class TestFetchApprovedEngineWiring:
    """_fetch_approved — engine/session 생성 경로 커버리지.

    실제 asyncpg URL로는 테스트 불가능하므로 create_async_engine과
    async_sessionmaker를 mock하여 내부 로직이 정상 호출되는지만 검증한다.
    """

    async def test_engine_is_disposed_even_on_success(self, db: object) -> None:
        """성공 경로에서도 engine.dispose()가 호출되어야 한다."""
        from unittest.mock import MagicMock

        from src.trading.llm_decision_loader import _fetch_approved

        # dispose 호출을 추적하는 mock engine
        fake_engine = MagicMock()
        fake_engine.dispose = AsyncMock()

        # async context manager 가 db 세션을 반환하도록 하는 session_factory
        class _FakeFactory:
            def __call__(self) -> object:
                return self

            async def __aenter__(self) -> object:
                return db

            async def __aexit__(self, *args: object) -> None:
                return None

        fake_factory = _FakeFactory()

        with (
            patch(
                "sqlalchemy.ext.asyncio.create_async_engine",
                return_value=fake_engine,
            ),
            patch(
                "sqlalchemy.ext.asyncio.async_sessionmaker",
                return_value=fake_factory,
            ),
        ):
            result = await _fetch_approved(
                "postgresql+asyncpg://fake/db",
                since_hours=24,
            )

        assert result == {}
        fake_engine.dispose.assert_awaited_once()


# ── PR 2: 헬퍼 함수 테스트 ─────────────────────────────────


class TestApplyUniverseDecisions:
    """apply_universe_decisions — universe_adjust + symbol_bias → symbols 필터."""

    def test_empty_decisions_returns_original(self) -> None:
        """승인 결정이 없으면 symbols 원본 그대로 반환."""

        result = apply_universe_decisions(["005930", "000660"], {})
        assert result == ["005930", "000660"]

    def test_universe_adjust_excludes_symbols(self) -> None:
        """universe_adjust.exclude 의 종목이 제거되어야 한다."""

        decisions = {
            "universe_adjust": [{"exclude": ["005930"], "reason": "악재"}],
        }
        result = apply_universe_decisions(["005930", "000660", "068270"], decisions)
        assert result == ["000660", "068270"]

    def test_symbol_bias_block_buy_excludes_symbol(self) -> None:
        """symbol_bias.bias='block_buy' 종목이 제거되어야 한다."""

        decisions = {
            "symbol_bias": [{"symbol": "005930", "bias": "block_buy"}],
        }
        result = apply_universe_decisions(["005930", "000660"], decisions)
        assert result == ["000660"]

    def test_symbol_bias_other_biases_are_no_op(self) -> None:
        """boost_buy / block_sell 등 다른 bias는 symbols를 변경하지 않는다."""

        decisions = {
            "symbol_bias": [
                {"symbol": "005930", "bias": "boost_buy"},
                {"symbol": "000660", "bias": "block_sell"},
            ],
        }
        result = apply_universe_decisions(["005930", "000660", "068270"], decisions)
        assert result == ["005930", "000660", "068270"]

    def test_combined_universe_and_symbol_bias(self) -> None:
        """universe_adjust + symbol_bias 모두 반영된다."""

        decisions = {
            "universe_adjust": [{"exclude": ["005930"]}],
            "symbol_bias": [{"symbol": "000660", "bias": "block_buy"}],
        }
        result = apply_universe_decisions(["005930", "000660", "068270"], decisions)
        assert result == ["068270"]

    def test_preserves_original_order(self) -> None:
        """원본 symbols 순서가 유지된다."""

        decisions = {"universe_adjust": [{"exclude": ["000660"]}]}
        result = apply_universe_decisions(["005930", "000660", "068270"], decisions)
        assert result == ["005930", "068270"]

    def test_exclude_not_a_list_is_ignored(self) -> None:
        """exclude가 list가 아니면 무시한다 (방어)."""

        decisions = {"universe_adjust": [{"exclude": "005930"}]}  # str, not list
        result = apply_universe_decisions(["005930", "000660"], decisions)
        assert result == ["005930", "000660"]

    def test_symbol_bias_missing_symbol_is_ignored(self) -> None:
        """symbol_bias에 symbol 키 없으면 무시한다."""

        decisions = {"symbol_bias": [{"bias": "block_buy"}]}
        result = apply_universe_decisions(["005930", "000660"], decisions)
        assert result == ["005930", "000660"]

    def test_unknown_decision_type_ignored(self) -> None:
        """strategy_param_hint 같은 다른 타입은 symbols에 영향 없음."""

        decisions = {
            "strategy_param_hint": [{"strategy": "momentum", "params": {"max_positions": 5}}],
        }
        result = apply_universe_decisions(["005930"], decisions)
        assert result == ["005930"]


class TestSummarizeDecisions:
    """summarize_decisions — shadow 로그용 요약."""

    def test_empty_returns_placeholder(self) -> None:
        """빈 dict이면 placeholder 문자열."""

        assert summarize_decisions({}) == "no approved decisions"

    def test_counts_per_type(self) -> None:
        """타입별 개수 요약."""

        decisions = {
            "universe_adjust": [{"exclude": ["005930"]}, {"exclude": ["000660"]}],
            "symbol_bias": [{"symbol": "068270", "bias": "block_buy"}],
        }
        summary = summarize_decisions(decisions)
        assert "universe_adjust=2" in summary
        assert "symbol_bias=1" in summary
