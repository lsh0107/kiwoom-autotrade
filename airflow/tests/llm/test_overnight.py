"""야간 분석 LLM 단위 테스트 (design-010 decision 스키마 정합성).

핵심 검증:
- decisions 배열의 decision_type 이 live_trader 소비 스펙과 일치한다
  (universe_adjust / symbol_bias / strategy_param_hint).
- 레거시 타입 (weight_adjust / risk_mode / param_tune) 은 제거된다.
- 각 타입별 content 스키마 검증 / 정규화.
- live_trader loader 의 apply_universe_decisions 와 end-to-end 통합.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest


def _make_llm_response(content: str) -> MagicMock:
    """LLMResponse mock 생성."""
    resp = MagicMock()
    resp.content = content
    resp.provider = "gpt"
    resp.model = "gpt-4o"
    return resp


VALID_OVERNIGHT_JSON = """{
  "summary": "미국 증시 하락으로 반도체 섹터 약세 예상.",
  "theme_scores": {"반도체": 0.3, "바이오": 0.6},
  "risk_flags": ["VIX 28 경계"],
  "weight_adjustments": {"반도체": -0.1},
  "decisions": [
    {
      "decision_type": "universe_adjust",
      "content": {"exclude": ["005930", "000660"], "reason": "반도체 약세"},
      "confidence": 0.8
    },
    {
      "decision_type": "symbol_bias",
      "content": {"symbol": "035720", "bias": "boost_buy", "reason": "실적 호전"},
      "confidence": 0.7
    },
    {
      "decision_type": "strategy_param_hint",
      "content": {
        "strategy": "momentum",
        "params": {"max_positions": 3, "volume_ratio": 1.2},
        "reason": "변동성 축소"
      },
      "confidence": 0.6
    }
  ]
}"""


# ── 프롬프트 포맷 검증 ────────────────────────────────────────────────────────


class TestPromptContainsDesign010Schema:
    """프롬프트에 Design 010 스펙의 decision_type 3종이 포함되어야 한다."""

    def test_prompt_mentions_all_supported_types(self) -> None:
        from llm.overnight import _USER_PROMPT_TEMPLATE

        assert "universe_adjust" in _USER_PROMPT_TEMPLATE
        assert "symbol_bias" in _USER_PROMPT_TEMPLATE
        assert "strategy_param_hint" in _USER_PROMPT_TEMPLATE

    def test_prompt_does_not_mention_legacy_types(self) -> None:
        """weight_adjust / risk_mode / param_tune 은 제거되어야 한다."""
        from llm.overnight import _USER_PROMPT_TEMPLATE

        assert "weight_adjust" not in _USER_PROMPT_TEMPLATE.replace("weight_adjustments", "")
        assert "param_tune" not in _USER_PROMPT_TEMPLATE
        # risk_mode(decision 타입)는 제거되지만, 본문에 "위험 모드" 한글은 시스템 프롬프트
        # 에만 있고 decision JSON 샘플에는 없어야 한다.
        assert '"risk_mode"' not in _USER_PROMPT_TEMPLATE

    def test_prompt_whitelists_param_keys(self) -> None:
        """strategy_param_hint 화이트리스트 키가 프롬프트에 명시되어야 한다."""
        from llm.overnight import _USER_PROMPT_TEMPLATE

        for key in ("volume_ratio", "atr_stop_mult", "atr_tp_mult", "max_positions"):
            assert key in _USER_PROMPT_TEMPLATE


# ── JSON 파싱 ────────────────────────────────────────────────────────────────


class TestParseResponse:
    """최상위 JSON 파싱 테스트."""

    def test_valid_json_parses(self) -> None:
        from llm.overnight import _parse_response

        data = _parse_response(VALID_OVERNIGHT_JSON)

        assert data is not None
        assert data["summary"].startswith("미국")

    def test_markdown_block_parses(self) -> None:
        from llm.overnight import _parse_response

        wrapped = f"```json\n{VALID_OVERNIGHT_JSON}\n```"
        data = _parse_response(wrapped)

        assert data is not None
        assert "decisions" in data

    def test_invalid_returns_none(self) -> None:
        from llm.overnight import _parse_response

        assert _parse_response("잡음") is None

    def test_weight_adjustments_clamped(self) -> None:
        from llm.overnight import _parse_response

        data = _parse_response('{"weight_adjustments": {"반도체": 0.9, "바이오": -0.5}}')

        assert data is not None
        assert data["weight_adjustments"]["반도체"] == pytest.approx(0.20)
        assert data["weight_adjustments"]["바이오"] == pytest.approx(-0.20)


# ── decisions 정규화 ──────────────────────────────────────────────────────────


class TestNormalizeDecisions:
    """_normalize_decisions — decision_type / content 검증."""

    def test_legacy_types_dropped(self) -> None:
        """weight_adjust / risk_mode / param_tune 은 제거되어야 한다."""
        from llm.overnight import _normalize_decisions

        raw = [
            {"decision_type": "weight_adjust", "content": {"반도체": 0.1}},
            {"decision_type": "risk_mode", "content": {"mode": "defensive"}},
            {"decision_type": "param_tune", "content": {"foo": 1}},
        ]
        assert _normalize_decisions(raw) == []

    def test_universe_adjust_valid(self) -> None:
        from llm.overnight import _normalize_decisions

        raw = [
            {
                "decision_type": "universe_adjust",
                "content": {"exclude": ["005930"], "reason": "악재"},
                "confidence": 0.9,
            }
        ]
        out = _normalize_decisions(raw)

        assert len(out) == 1
        assert out[0]["decision_type"] == "universe_adjust"
        assert out[0]["content"]["exclude"] == ["005930"]
        assert out[0]["content"]["reason"] == "악재"
        assert out[0]["confidence"] == pytest.approx(0.9)

    def test_universe_adjust_empty_exclude_dropped(self) -> None:
        from llm.overnight import _normalize_decisions

        raw = [
            {"decision_type": "universe_adjust", "content": {"exclude": []}},
            {"decision_type": "universe_adjust", "content": {"reason": "없음"}},
        ]
        assert _normalize_decisions(raw) == []

    def test_symbol_bias_valid(self) -> None:
        from llm.overnight import _normalize_decisions

        raw = [
            {
                "decision_type": "symbol_bias",
                "content": {"symbol": "005930", "bias": "block_buy", "reason": "리스크"},
                "confidence": 0.7,
            }
        ]
        out = _normalize_decisions(raw)

        assert len(out) == 1
        assert out[0]["content"]["symbol"] == "005930"
        assert out[0]["content"]["bias"] == "block_buy"

    def test_symbol_bias_unknown_bias_dropped(self) -> None:
        from llm.overnight import _normalize_decisions

        raw = [
            {
                "decision_type": "symbol_bias",
                "content": {"symbol": "005930", "bias": "sell_immediately"},
            }
        ]
        assert _normalize_decisions(raw) == []

    def test_symbol_bias_missing_symbol_dropped(self) -> None:
        from llm.overnight import _normalize_decisions

        raw = [
            {
                "decision_type": "symbol_bias",
                "content": {"bias": "block_buy"},
            }
        ]
        assert _normalize_decisions(raw) == []

    def test_strategy_param_hint_valid(self) -> None:
        from llm.overnight import _normalize_decisions

        raw = [
            {
                "decision_type": "strategy_param_hint",
                "content": {
                    "strategy": "momentum",
                    "params": {"max_positions": 3, "volume_ratio": 1.5},
                },
                "confidence": 0.5,
            }
        ]
        out = _normalize_decisions(raw)

        assert len(out) == 1
        assert out[0]["content"]["strategy"] == "momentum"
        assert out[0]["content"]["params"] == {"max_positions": 3, "volume_ratio": 1.5}

    def test_strategy_param_hint_whitelist_filters_unknown_keys(self) -> None:
        """화이트리스트 외 키는 params 에서 제거되어야 한다."""
        from llm.overnight import _normalize_decisions

        raw = [
            {
                "decision_type": "strategy_param_hint",
                "content": {
                    "strategy": "momentum",
                    "params": {
                        "max_positions": 3,
                        "mystery_flag": True,
                        "secret_key": "hack",
                    },
                },
            }
        ]
        out = _normalize_decisions(raw)

        assert len(out) == 1
        params = out[0]["content"]["params"]
        assert params == {"max_positions": 3}

    def test_strategy_param_hint_unknown_strategy_dropped(self) -> None:
        from llm.overnight import _normalize_decisions

        raw = [
            {
                "decision_type": "strategy_param_hint",
                "content": {"strategy": "quantum_ai", "params": {"max_positions": 3}},
            }
        ]
        assert _normalize_decisions(raw) == []

    def test_strategy_param_hint_empty_params_dropped(self) -> None:
        from llm.overnight import _normalize_decisions

        raw = [
            {
                "decision_type": "strategy_param_hint",
                "content": {"strategy": "momentum", "params": {"unknown_key": 1}},
            }
        ]
        assert _normalize_decisions(raw) == []

    def test_non_list_input_returns_empty(self) -> None:
        from llm.overnight import _normalize_decisions

        assert _normalize_decisions(None) == []
        assert _normalize_decisions("not a list") == []
        assert _normalize_decisions({"a": 1}) == []

    def test_non_dict_items_dropped(self) -> None:
        from llm.overnight import _normalize_decisions

        assert _normalize_decisions(["string", 42, None]) == []

    def test_confidence_clamped_to_0_1(self) -> None:
        from llm.overnight import _normalize_decisions

        raw = [
            {
                "decision_type": "universe_adjust",
                "content": {"exclude": ["A"]},
                "confidence": 1.5,
            },
            {
                "decision_type": "universe_adjust",
                "content": {"exclude": ["B"]},
                "confidence": -0.3,
            },
        ]
        out = _normalize_decisions(raw)

        assert out[0]["confidence"] == pytest.approx(1.0)
        assert out[1]["confidence"] == pytest.approx(0.0)

    def test_missing_confidence_gets_default(self) -> None:
        from llm.overnight import _normalize_decisions

        raw = [{"decision_type": "universe_adjust", "content": {"exclude": ["A"]}}]
        out = _normalize_decisions(raw)

        assert out[0]["confidence"] == pytest.approx(0.5)


# ── generate_overnight_analysis 통합 ─────────────────────────────────────────


class TestGenerateOvernightAnalysis:
    """generate_overnight_analysis — LLM mock 기반 전체 파이프라인."""

    def test_success_returns_supported_decisions_only(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")

        with patch("llm.client.generate") as mock_generate:
            mock_generate.return_value = _make_llm_response(VALID_OVERNIGHT_JSON)

            from llm.overnight import generate_overnight_analysis

            result = generate_overnight_analysis({"formatted": "context"})

        types = {d["decision_type"] for d in result["decisions"]}
        assert types == {"universe_adjust", "symbol_bias", "strategy_param_hint"}
        assert result["provider"] == "gpt"
        assert result["model"] == "gpt-4o"

    def test_legacy_types_are_filtered_from_llm_output(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """LLM 이 레거시 타입을 섞어 반환해도 최종 decisions 에 없어야 한다."""
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")

        mixed = {
            "summary": "s",
            "theme_scores": {},
            "risk_flags": [],
            "weight_adjustments": {},
            "decisions": [
                {"decision_type": "weight_adjust", "content": {"반도체": 0.1}},
                {
                    "decision_type": "universe_adjust",
                    "content": {"exclude": ["005930"]},
                    "confidence": 0.8,
                },
                {"decision_type": "risk_mode", "content": {"mode": "defensive"}},
            ],
        }

        with patch("llm.client.generate") as mock_generate:
            mock_generate.return_value = _make_llm_response(json.dumps(mixed))

            from llm.overnight import generate_overnight_analysis

            result = generate_overnight_analysis({"formatted": "ctx"})

        assert len(result["decisions"]) == 1
        assert result["decisions"][0]["decision_type"] == "universe_adjust"

    def test_llm_error_returns_empty_decisions(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")

        with patch("llm.client.generate") as mock_generate:
            from llm.client import LLMError

            mock_generate.side_effect = LLMError("fail")

            from llm.overnight import generate_overnight_analysis

            result = generate_overnight_analysis({"formatted": "ctx"})

        assert result["decisions"] == []
        assert result["provider"] == ""
        assert result["model"] == ""

    def test_invalid_json_returns_defaults(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")

        with patch("llm.client.generate") as mock_generate:
            mock_generate.return_value = _make_llm_response("notjson{")

            from llm.overnight import generate_overnight_analysis

            result = generate_overnight_analysis({"formatted": "ctx"})

        assert result["decisions"] == []
        # 원문은 보존
        assert result["raw_response"] == "notjson{"


# ── live_trader loader 와의 end-to-end 호환성 ─────────────────────────────────


class TestLoaderCompatibility:
    """생성된 decisions 가 live_trader loader 를 통해 올바르게 소비되는지 검증.

    즉, Airflow 생산자 → (DB 생략, dict 전달) → loader 소비자 파이프라인이
    스키마 일치로 실제 매매에 반영되는지 확인한다.
    """

    def test_universe_adjust_flows_to_apply_universe_decisions(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")

        with patch("llm.client.generate") as mock_generate:
            mock_generate.return_value = _make_llm_response(VALID_OVERNIGHT_JSON)

            from llm.overnight import generate_overnight_analysis

            result = generate_overnight_analysis({"formatted": "ctx"})

        # 생산자가 만든 decisions 를 loader 가 기대하는 {type: [content, ...]} 으로 재구성
        grouped: dict[str, list[dict]] = {}
        for d in result["decisions"]:
            grouped.setdefault(d["decision_type"], []).append(d["content"])

        from src.trading.llm_decision_loader import apply_universe_decisions

        filtered = apply_universe_decisions(["005930", "000660", "035720"], grouped)

        # VALID_OVERNIGHT_JSON 의 exclude 리스트는 005930, 000660 두 종목.
        assert "005930" not in filtered
        assert "000660" not in filtered
        assert "035720" in filtered

    def test_strategy_param_hint_flows_to_extract(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")

        with patch("llm.client.generate") as mock_generate:
            mock_generate.return_value = _make_llm_response(VALID_OVERNIGHT_JSON)

            from llm.overnight import generate_overnight_analysis

            result = generate_overnight_analysis({"formatted": "ctx"})

        grouped: dict[str, list[dict]] = {}
        for d in result["decisions"]:
            grouped.setdefault(d["decision_type"], []).append(d["content"])

        from src.trading.llm_decision_loader import extract_strategy_param_hints

        hints = extract_strategy_param_hints(grouped)

        # VALID_OVERNIGHT_JSON 에서 strategy_param_hint.params 는 max_positions=3,
        # volume_ratio=1.2 두 개가 화이트리스트에 포함된다.
        assert hints == {"max_positions": 3, "volume_ratio": pytest.approx(1.2)}
