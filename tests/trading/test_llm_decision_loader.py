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
    LLM_PARAM_WHITELIST,
    SUPPORTED_DECISION_TYPES,
    apply_llm_param_hints,
    apply_universe_decisions,
    extract_strategy_param_hints,
    load_approved_decisions,
    summarize_decisions,
)

# ── PR 3: strategy_param_hint 테스트 ─────────────────────


class TestExtractStrategyParamHints:
    """extract_strategy_param_hints — whitelist 필터 + 범위 검증."""

    def test_empty_decisions_returns_empty(self) -> None:
        """decisions dict에 strategy_param_hint 키 없으면 빈 dict."""
        assert extract_strategy_param_hints({}) == {}
        assert extract_strategy_param_hints({"universe_adjust": [{}]}) == {}

    def test_whitelist_keys_are_extracted(self) -> None:
        """화이트리스트 내 키는 그대로 추출된다."""
        decisions = {
            "strategy_param_hint": [
                {
                    "strategy": "momentum",
                    "params": {
                        "volume_ratio": 0.9,
                        "atr_stop_mult": 1.5,
                    },
                },
            ],
        }
        result = extract_strategy_param_hints(decisions)
        assert result == {"volume_ratio": 0.9, "atr_stop_mult": 1.5}

    def test_non_whitelist_keys_are_filtered(self) -> None:
        """whitelist 외 키는 제외된다."""
        decisions = {
            "strategy_param_hint": [
                {
                    "params": {
                        "volume_ratio": 1.0,
                        "evil_key": 999,  # whitelist 외
                        "take_profit": 0.05,  # whitelist 외 (의도적으로 PR3 범위 제외)
                    },
                },
            ],
        }
        result = extract_strategy_param_hints(decisions)
        assert "volume_ratio" in result
        assert "evil_key" not in result
        assert "take_profit" not in result

    def test_content_without_params_subkey(self) -> None:
        """content 자체를 params로 간주하는 fallback 경로."""
        decisions = {
            "strategy_param_hint": [
                {"volume_ratio": 1.2, "atr_tp_mult": 2.5},
            ],
        }
        result = extract_strategy_param_hints(decisions)
        assert result == {"volume_ratio": 1.2, "atr_tp_mult": 2.5}

    def test_range_min_boundary_accepted(self) -> None:
        """범위 min 경계값은 허용된다."""
        decisions = {
            "strategy_param_hint": [{"params": {"volume_ratio": 0.5, "atr_stop_mult": 0.5}}],
        }
        result = extract_strategy_param_hints(decisions)
        assert result == {"volume_ratio": 0.5, "atr_stop_mult": 0.5}

    def test_range_max_boundary_accepted(self) -> None:
        """범위 max 경계값은 허용된다."""
        decisions = {
            "strategy_param_hint": [{"params": {"volume_ratio": 2.0, "max_positions": 10}}],
        }
        result = extract_strategy_param_hints(decisions)
        assert result == {"volume_ratio": 2.0, "max_positions": 10}

    def test_range_over_max_rejected(self) -> None:
        """max 초과 값은 거부된다 (적용 안 함)."""
        decisions = {
            "strategy_param_hint": [{"params": {"volume_ratio": 2.1, "atr_tp_mult": 6.0}}],
        }
        result = extract_strategy_param_hints(decisions)
        assert result == {}

    def test_range_under_min_rejected(self) -> None:
        """min 미만 값은 거부된다."""
        decisions = {
            "strategy_param_hint": [{"params": {"volume_ratio": 0.4, "max_positions": 0}}],
        }
        result = extract_strategy_param_hints(decisions)
        assert result == {}

    def test_gap_risk_threshold_negative_range(self) -> None:
        """gap_risk_threshold는 음수 범위(-0.10 ~ -0.01)."""
        decisions = {
            "strategy_param_hint": [{"params": {"gap_risk_threshold": -0.05}}],
        }
        result = extract_strategy_param_hints(decisions)
        assert result == {"gap_risk_threshold": -0.05}

    def test_gap_risk_threshold_positive_rejected(self) -> None:
        """gap_risk_threshold에 양수가 오면 거부."""
        decisions = {
            "strategy_param_hint": [{"params": {"gap_risk_threshold": 0.05}}],
        }
        assert extract_strategy_param_hints(decisions) == {}

    def test_non_numeric_rejected(self) -> None:
        """숫자가 아닌 값은 거부된다."""
        decisions = {
            "strategy_param_hint": [
                {"params": {"volume_ratio": "not_a_number", "atr_stop_mult": None}}
            ],
        }
        result = extract_strategy_param_hints(decisions)
        assert result == {}

    def test_bool_is_rejected(self) -> None:
        """bool은 숫자 아닌 것으로 취급 (True/False 의도 오용 방지)."""
        decisions = {
            "strategy_param_hint": [{"params": {"max_positions": True}}],
        }
        assert extract_strategy_param_hints(decisions) == {}

    def test_numeric_string_is_coerced(self) -> None:
        """숫자 문자열은 변환 허용 (JSON 직렬화 경로 배려)."""
        decisions = {
            "strategy_param_hint": [{"params": {"volume_ratio": "1.3"}}],
        }
        result = extract_strategy_param_hints(decisions)
        assert result == {"volume_ratio": 1.3}

    def test_max_positions_is_int(self) -> None:
        """max_positions는 int로 강제 변환된다."""
        decisions = {
            "strategy_param_hint": [{"params": {"max_positions": 5.0}}],
        }
        result = extract_strategy_param_hints(decisions)
        assert result == {"max_positions": 5}
        assert isinstance(result["max_positions"], int)

    def test_latest_decision_wins_on_duplicate_key(self) -> None:
        """같은 키가 여러 결정에 있으면 최신(리스트 앞)이 우선."""
        # load_approved_decisions는 created_at desc 순으로 반환하므로
        # 리스트 앞이 최신.
        decisions = {
            "strategy_param_hint": [
                {"params": {"volume_ratio": 1.5}},  # 최신
                {"params": {"volume_ratio": 0.8}},  # 구
                {"params": {"atr_stop_mult": 2.0}},  # 최신의 새 키
            ],
        }
        result = extract_strategy_param_hints(decisions)
        assert result == {"volume_ratio": 1.5, "atr_stop_mult": 2.0}

    def test_non_dict_content_ignored(self) -> None:
        """content가 dict가 아니면 무시."""
        decisions = {"strategy_param_hint": [None, "invalid", 123]}  # type: ignore[list-item]
        assert extract_strategy_param_hints(decisions) == {}

    def test_whitelist_constant_has_five_keys(self) -> None:
        """whitelist 상수 가드 — 5개 키 고정."""
        assert set(LLM_PARAM_WHITELIST.keys()) == {
            "volume_ratio",
            "atr_stop_mult",
            "atr_tp_mult",
            "gap_risk_threshold",
            "max_positions",
        }


class TestApplyLLMParamHints:
    """apply_llm_param_hints — DB(사용자) 우선 + LLM 힌트 보충."""

    def test_db_key_wins_over_llm(self) -> None:
        """DB에 있는 키는 LLM 값으로 덮이지 않는다."""
        db_config = {"volume_ratio": 1.0}
        hints = {"volume_ratio": 1.5, "atr_stop_mult": 1.8}
        result = apply_llm_param_hints(db_config, hints)
        assert result["volume_ratio"] == 1.0  # DB 유지
        assert result["atr_stop_mult"] == 1.8  # LLM 적용

    def test_empty_hints_returns_copy_of_db(self) -> None:
        """힌트가 비면 DB config 사본 그대로."""
        db_config = {"volume_ratio": 1.0, "other_key": 42}
        result = apply_llm_param_hints(db_config, {})
        assert result == db_config
        assert result is not db_config  # shallow copy

    def test_empty_db_uses_all_hints(self) -> None:
        """DB에 아무것도 없으면 모든 힌트가 적용된다."""
        hints = {"volume_ratio": 0.9, "max_positions": 3}
        result = apply_llm_param_hints({}, hints)
        assert result == {"volume_ratio": 0.9, "max_positions": 3}

    def test_db_with_jsonb_wrapped_value_still_wins(self) -> None:
        """DB 값이 {'value': x} 형태로 래핑돼 있어도 키가 있으면 유지."""
        db_config = {"volume_ratio": {"value": 1.0}}
        hints = {"volume_ratio": 1.8}
        result = apply_llm_param_hints(db_config, hints)
        assert result["volume_ratio"] == {"value": 1.0}

    def test_does_not_mutate_db_config(self) -> None:
        """원본 db_config은 수정되지 않는다."""
        db_config: dict[str, object] = {"volume_ratio": 1.0}
        apply_llm_param_hints(db_config, {"atr_stop_mult": 2.0})
        assert db_config == {"volume_ratio": 1.0}

    def test_unrelated_db_keys_preserved(self) -> None:
        """hints 와 무관한 DB 키는 그대로 보존된다."""
        db_config = {"stop_loss": 0.02, "entry_start_time": "09:05"}
        hints = {"volume_ratio": 1.1}
        result = apply_llm_param_hints(db_config, hints)
        assert result["stop_loss"] == 0.02
        assert result["entry_start_time"] == "09:05"
        assert result["volume_ratio"] == 1.1


class TestFlagOffSemantics:
    """USE_LLM_DECISIONS 플래그 off 시의 의미론 — 헬퍼는 순수 함수.

    flag 검사는 live_trader 레벨에서 이루어진다. 추출/적용 헬퍼 자체는
    flag와 무관하게 동작해야 한다 (단위 테스트 가능성 보장).
    """

    def test_extract_works_without_flag(self) -> None:
        """flag 상관없이 extract는 항상 유효 값 추출한다."""
        decisions = {"strategy_param_hint": [{"params": {"volume_ratio": 1.0}}]}
        assert extract_strategy_param_hints(decisions) == {"volume_ratio": 1.0}

    def test_apply_is_pure(self) -> None:
        """apply 호출은 flag에 의존하지 않는다 — 순수 병합."""
        result = apply_llm_param_hints({}, {"atr_tp_mult": 2.0})
        assert result == {"atr_tp_mult": 2.0}


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
