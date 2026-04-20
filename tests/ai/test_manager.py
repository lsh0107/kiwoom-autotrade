"""LLM 매니저 테스트 — 반환값/상태 기반 검증.

원칙:
- assert_called_* 최소화. 대신 반환값의 provider/cost로 fallback 경로를 검증한다.
- "호출되지 않았다"는 비용이 추가되지 않았음/ call_count 등 상태로 증명한다.
- fallback chain 은 결과(최종 provider)로 검증한다.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.ai.llm.provider import LLMRequest, LLMResponse
from src.utils.exceptions import AIError, LLMRateLimitError

_FAKE = "x"  # 시크릿 아님. Gemini 키 존재 여부 시뮬레이션용.


def _make_settings(**overrides: object) -> MagicMock:
    """테스트용 Settings 모킹."""
    defaults = {
        "llm_primary_provider": "openai",
        "llm_fallback_provider": "anthropic",
        "max_daily_llm_cost_usd": 5.0,
        "openai_api_key": "test-openai-key",
        "anthropic_api_key": "test-anthropic-key",
        "gemini_api_key": None,
        "openai_model": "gpt-4o-mini",
        "anthropic_model": "claude-sonnet-4-20250514",
        "gemini_model": "gemini-1.5-flash",
    }
    defaults.update(overrides)
    mock = MagicMock()
    for k, v in defaults.items():
        setattr(mock, k, v)
    return mock


def _make_llm_response(
    provider: str = "openai",
    model: str = "gpt-4o-mini",
    cost: float = 0.001,
) -> LLMResponse:
    """테스트용 LLMResponse 생성."""
    return LLMResponse(
        content=f"response-from-{provider}",
        provider=provider,
        model=model,
        input_tokens=100,
        output_tokens=50,
        cost_usd=cost,
        latency_ms=100,
    )


class TestLLMManager:
    """LLM 매니저 테스트."""

    @patch("src.ai.llm.manager.get_settings")
    @patch("src.ai.llm.manager.GeminiClient")
    @patch("src.ai.llm.manager.AnthropicClient")
    @patch("src.ai.llm.manager.OpenAIClient")
    def _make_manager(
        self,
        mock_openai_cls: MagicMock,
        mock_anthropic_cls: MagicMock,
        mock_gemini_cls: MagicMock,
        mock_get_settings: MagicMock,
        **settings_overrides: object,
    ) -> tuple:
        """테스트용 LLMManager + mock 클라이언트 생성."""
        mock_get_settings.return_value = _make_settings(**settings_overrides)

        mock_openai = AsyncMock()
        mock_openai.provider_name = "openai"
        mock_openai_cls.return_value = mock_openai

        mock_anthropic = AsyncMock()
        mock_anthropic.provider_name = "anthropic"
        mock_anthropic_cls.return_value = mock_anthropic

        mock_gemini = AsyncMock()
        mock_gemini.provider_name = "gemini"
        mock_gemini_cls.return_value = mock_gemini

        from src.ai.llm.manager import LLMManager

        manager = LLMManager()
        return manager, mock_openai, mock_anthropic, mock_gemini

    # ── 라우팅 (mode별) ──────────────────────────────────────────────

    @pytest.mark.parametrize(
        ("mode", "expected_provider"),
        [
            ("quick", "openai"),
            ("deep", "anthropic"),
        ],
    )
    async def test_mode_routes_to_expected_primary(self, mode: str, expected_provider: str) -> None:
        """mode 별로 최초 성공 응답의 provider 가 올바르게 결정된다.

        quick=openai, deep=anthropic. 내부 호출 회수가 아니라 결과의 provider 로 검증.
        """
        manager, mock_openai, mock_anthropic, _mock_gemini = self._make_manager()
        mock_openai.complete.return_value = _make_llm_response("openai")
        mock_anthropic.complete.return_value = _make_llm_response("anthropic")

        request = LLMRequest(user_prompt="테스트")
        result = await manager.complete(request, mode=mode)

        assert result.provider == expected_provider
        # 성공 경로는 1번째 provider 에서 종료되어야 하므로 비용도 1회분만 추적됨.
        assert manager.daily_cost == pytest.approx(0.001)

    # ── 비용 한도 ─────────────────────────────────────────────────

    async def test_daily_cost_limit_raises(self) -> None:
        """일일 비용 한도 초과 시 LLMRateLimitError."""
        manager, _mock_openai, _mock_anthropic, _mock_gemini = self._make_manager()

        # 비용 한도에 도달하도록 설정
        manager._daily_cost = 5.0  # max_daily_llm_cost_usd와 동일

        request = LLMRequest(user_prompt="테스트")
        with pytest.raises(LLMRateLimitError):
            await manager.complete(request)

    async def test_cost_tracking(self) -> None:
        """비용 추적 동작."""
        manager, mock_openai, _mock_anthropic, _mock_gemini = self._make_manager()
        response = _make_llm_response("openai", cost=0.002)
        mock_openai.complete.return_value = response

        assert manager.daily_cost == 0.0

        request = LLMRequest(user_prompt="테스트")
        await manager.complete(request, mode="quick")

        assert manager.daily_cost == pytest.approx(0.002)

    async def test_daily_cost_remaining(self) -> None:
        """남은 일일 비용 계산."""
        manager, mock_openai, _mock_anthropic, _mock_gemini = self._make_manager()
        response = _make_llm_response("openai", cost=1.5)
        mock_openai.complete.return_value = response

        request = LLMRequest(user_prompt="테스트")
        await manager.complete(request, mode="quick")

        assert manager.daily_cost_remaining == pytest.approx(3.5)  # 5.0 - 1.5

    async def test_cost_resets_on_new_day(self) -> None:
        """날짜 변경 시 비용 리셋."""
        from datetime import date

        manager, _mock_openai, _mock_anthropic, _mock_gemini = self._make_manager()
        manager._daily_cost = 3.0

        # 다음 날로 변경
        with patch("src.ai.llm.manager._today", return_value=date(2099, 1, 2)):
            assert manager.daily_cost == 0.0

    # ── fallback 체인 ────────────────────────────────────────────

    async def test_fallback_on_primary_failure_returns_fallback_provider(self) -> None:
        """primary 실패 시 fallback 의 응답이 최종 결과가 된다.

        내부 호출 횟수가 아니라 최종 결과의 provider/cost 로 fallback 을 증명한다.
        """
        manager, mock_openai, mock_anthropic, _mock_gemini = self._make_manager()

        mock_openai.complete.side_effect = RuntimeError("API 오류")
        mock_anthropic.complete.return_value = _make_llm_response(
            "anthropic", "claude-sonnet-4-20250514", cost=0.003
        )

        request = LLMRequest(user_prompt="테스트")
        result = await manager.complete(request, mode="quick")

        # fallback 의 응답이 최종 결과로 반환되었다.
        assert result.provider == "anthropic"
        assert result.content == "response-from-anthropic"
        # fallback 성공 시 비용은 fallback 것만 가산 (primary 는 실패해서 추적 X).
        assert manager.daily_cost == pytest.approx(0.003)

    async def test_both_providers_fail_raises_with_last_error_chained(self) -> None:
        """primary + fallback 모두 실패하면 AIError, 원인 예외가 체인된다."""
        manager, mock_openai, mock_anthropic, _mock_gemini = self._make_manager()

        mock_openai.complete.side_effect = RuntimeError("openai 오류")
        anthropic_exc = RuntimeError("anthropic 오류")
        mock_anthropic.complete.side_effect = anthropic_exc

        request = LLMRequest(user_prompt="테스트")
        with pytest.raises(AIError, match="LLM 호출 실패") as exc_info:
            await manager.complete(request, mode="quick")

        # 마지막 실패 예외가 __cause__ 로 체인되어 있어야 한다 (디버깅성 검증).
        assert exc_info.value.__cause__ is anthropic_exc
        # 전부 실패했으므로 비용은 가산되지 않아야 한다.
        assert manager.daily_cost == 0.0

    async def test_complete_json_routes_correctly(self) -> None:
        """complete_json도 모드별 라우팅."""
        from src.ai.analysis.models import TradingSignal

        manager, mock_openai, _mock_anthropic, _mock_gemini = self._make_manager()

        signal = TradingSignal(symbol="005930", action="BUY", confidence=0.8)
        response = _make_llm_response("openai")
        mock_openai.complete_json.return_value = (signal, response)

        request = LLMRequest(user_prompt="분석")
        parsed, resp = await manager.complete_json(request, TradingSignal, mode="quick")

        assert isinstance(parsed, TradingSignal)
        assert resp.provider == "openai"
        # quick 의 1차 성공이므로 비용 1회분.
        assert manager.daily_cost == pytest.approx(0.001)

    async def test_complete_json_fallback_returns_fallback_result(self) -> None:
        """complete_json primary 실패 시 fallback 결과가 최종 반환된다."""
        from src.ai.analysis.models import TradingSignal

        manager, mock_openai, mock_anthropic, _mock_gemini = self._make_manager()

        mock_openai.complete_json.side_effect = RuntimeError("API 오류")

        signal = TradingSignal(symbol="005930", action="HOLD", confidence=0.5)
        response = _make_llm_response("anthropic", cost=0.004)
        mock_anthropic.complete_json.return_value = (signal, response)

        request = LLMRequest(user_prompt="분석")
        parsed, resp = await manager.complete_json(request, TradingSignal, mode="quick")

        assert resp.provider == "anthropic"
        assert parsed.action == "HOLD"
        assert manager.daily_cost == pytest.approx(0.004)

    async def test_primary_missing_auto_falls_through_to_fallback(self) -> None:
        """primary(openai) 클라이언트 미등록 시 fallback(anthropic)으로 자동 진행."""
        manager, _mock_openai, mock_anthropic, _mock_gemini = self._make_manager()

        # openai 클라이언트 제거 (키가 없었다고 가정)
        manager._clients.pop("openai", None)

        mock_anthropic.complete.return_value = _make_llm_response("anthropic", cost=0.007)

        request = LLMRequest(user_prompt="테스트")
        result = await manager.complete(request, mode="quick")

        assert result.provider == "anthropic"
        # primary 등록이 없었으므로 시도 자체가 없었고, fallback 비용만 추적됨.
        assert manager.daily_cost == pytest.approx(0.007)

    async def test_no_providers_registered_raises(self) -> None:
        """등록된 프로바이더가 하나도 없으면 AIError."""
        manager, _mock_openai, _mock_anthropic, _mock_gemini = self._make_manager()
        manager._clients.clear()

        request = LLMRequest(user_prompt="테스트")
        with pytest.raises(AIError, match="사용 가능한 LLM 프로바이더"):
            await manager.complete(request, mode="quick")

    # ── Gemini 3번째 fallback ────────────────────────────────────

    async def test_gemini_registered_when_key_present(self) -> None:
        """gemini_api_key 설정 시 클라이언트 등록."""
        manager, _o, _a, _g = self._make_manager(gemini_api_key=_FAKE)
        assert "gemini" in manager._clients

    async def test_gemini_disabled_when_key_missing(self) -> None:
        """gemini_api_key 미설정 시 클라이언트 미등록 (기존 2-provider 동작 보존)."""
        manager, _o, _a, _g = self._make_manager(gemini_api_key=None)
        assert "gemini" not in manager._clients
        chain = manager._fallback_chain("quick")
        assert "gemini" not in chain
        assert chain == ["openai", "anthropic"]

    @pytest.mark.parametrize(
        ("mode", "expected_chain"),
        [
            ("quick", ["openai", "anthropic", "gemini"]),
            ("deep", ["anthropic", "openai", "gemini"]),
        ],
    )
    async def test_fallback_chain_order(self, mode: str, expected_chain: list[str]) -> None:
        """모드 별 fallback 체인 순서 (gemini 3번째)."""
        manager, _o, _a, _g = self._make_manager(gemini_api_key=_FAKE)
        assert manager._fallback_chain(mode) == expected_chain

    async def test_gemini_third_fallback_returns_gemini_result(self) -> None:
        """primary + fallback 모두 실패 시 gemini(3번째)의 응답이 최종 결과."""
        manager, mock_openai, mock_anthropic, mock_gemini = self._make_manager(gemini_api_key=_FAKE)

        mock_openai.complete.side_effect = RuntimeError("openai 장애")
        mock_anthropic.complete.side_effect = RuntimeError("anthropic 장애")
        mock_gemini.complete.return_value = _make_llm_response(
            "gemini", "gemini-1.5-flash", cost=0.0001
        )

        request = LLMRequest(user_prompt="테스트")
        result = await manager.complete(request, mode="quick")

        assert result.provider == "gemini"
        assert result.content == "response-from-gemini"
        # 3번째 fallback 성공 — 성공한 것만 비용 추적.
        assert manager.daily_cost == pytest.approx(0.0001)

    async def test_all_three_providers_fail_raises(self) -> None:
        """3-provider 모두 실패 시 AIError + 마지막 gemini 에러가 체인된다."""
        manager, mock_openai, mock_anthropic, mock_gemini = self._make_manager(gemini_api_key=_FAKE)

        mock_openai.complete.side_effect = RuntimeError("openai 장애")
        mock_anthropic.complete.side_effect = RuntimeError("anthropic 장애")
        gemini_exc = RuntimeError("gemini 장애")
        mock_gemini.complete.side_effect = gemini_exc

        request = LLMRequest(user_prompt="테스트")
        with pytest.raises(AIError, match="LLM 호출 실패") as exc_info:
            await manager.complete(request, mode="quick")

        # 마지막 provider 의 에러가 체인되어야 한다.
        assert exc_info.value.__cause__ is gemini_exc
        assert manager.daily_cost == 0.0

    async def test_gemini_third_fallback_json(self) -> None:
        """complete_json에서도 3-provider fallback 동작."""
        from src.ai.analysis.models import TradingSignal

        manager, mock_openai, mock_anthropic, mock_gemini = self._make_manager(gemini_api_key=_FAKE)

        mock_openai.complete_json.side_effect = RuntimeError("openai")
        mock_anthropic.complete_json.side_effect = RuntimeError("anthropic")

        signal = TradingSignal(symbol="005930", action="HOLD", confidence=0.5)
        response = _make_llm_response("gemini", "gemini-1.5-flash", cost=0.0002)
        mock_gemini.complete_json.return_value = (signal, response)

        request = LLMRequest(user_prompt="분석")
        parsed, resp = await manager.complete_json(request, TradingSignal, mode="quick")

        assert resp.provider == "gemini"
        assert parsed.action == "HOLD"
        assert manager.daily_cost == pytest.approx(0.0002)

    async def test_primary_success_skips_fallback_and_gemini(self) -> None:
        """primary 성공 시 fallback/gemini 는 건드리지 않는다 (비용 최적화 불변식)."""
        manager, mock_openai, mock_anthropic, mock_gemini = self._make_manager(gemini_api_key=_FAKE)

        mock_openai.complete.return_value = _make_llm_response("openai", cost=0.002)

        request = LLMRequest(user_prompt="테스트")
        result = await manager.complete(request, mode="quick")

        # 1) 결과는 primary 의 응답이다.
        assert result.provider == "openai"
        # 2) 비용은 정확히 primary 1회분만 기록 — fallback/gemini 가 실행됐다면
        #    그쪽의 response 가 side_effect 로 설정되지 않아 AttributeError 가 났을 것이다.
        assert manager.daily_cost == pytest.approx(0.002)
        # 3) call_count 로 "실제 실행되지 않음" 을 한번만 검증 (낮은 커플링).
        assert mock_anthropic.complete.call_count == 0
        assert mock_gemini.complete.call_count == 0
