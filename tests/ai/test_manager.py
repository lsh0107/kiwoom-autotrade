"""LLM 매니저 테스트."""

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
        content="테스트 응답",
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

    async def test_quick_mode_routes_to_primary(self) -> None:
        """quick 모드는 primary(openai)로 라우팅."""
        manager, mock_openai, mock_anthropic, _mock_gemini = self._make_manager()
        response = _make_llm_response("openai")
        mock_openai.complete.return_value = response

        request = LLMRequest(user_prompt="테스트")
        result = await manager.complete(request, mode="quick")

        assert result.provider == "openai"
        mock_openai.complete.assert_called_once()
        mock_anthropic.complete.assert_not_called()

    async def test_deep_mode_routes_to_fallback(self) -> None:
        """deep 모드는 fallback(anthropic)으로 라우팅."""
        manager, mock_openai, mock_anthropic, _mock_gemini = self._make_manager()
        response = _make_llm_response("anthropic", "claude-sonnet-4-20250514")
        mock_anthropic.complete.return_value = response

        request = LLMRequest(user_prompt="심층 분석")
        result = await manager.complete(request, mode="deep")

        assert result.provider == "anthropic"
        mock_anthropic.complete.assert_called_once()
        mock_openai.complete.assert_not_called()

    async def test_daily_cost_limit_raises(self) -> None:
        """일일 비용 한도 초과 시 LLMRateLimitError."""
        manager, _mock_openai, _mock_anthropic, _mock_gemini = self._make_manager()

        # 비용 한도에 도달하도록 설정
        manager._daily_cost = 5.0  # max_daily_llm_cost_usd와 동일

        request = LLMRequest(user_prompt="테스트")
        with pytest.raises(LLMRateLimitError):
            await manager.complete(request)

    async def test_fallback_on_primary_failure(self) -> None:
        """primary 실패 시 fallback으로 전환."""
        manager, mock_openai, mock_anthropic, _mock_gemini = self._make_manager()

        # primary(openai) 실패
        mock_openai.complete.side_effect = RuntimeError("API 오류")
        # fallback(anthropic) 성공
        fallback_response = _make_llm_response("anthropic", "claude-sonnet-4-20250514")
        mock_anthropic.complete.return_value = fallback_response

        request = LLMRequest(user_prompt="테스트")
        result = await manager.complete(request, mode="quick")

        assert result.provider == "anthropic"
        mock_openai.complete.assert_called_once()
        mock_anthropic.complete.assert_called_once()

    async def test_both_providers_fail_raises(self) -> None:
        """primary + fallback 모두 실패하면 AIError."""
        manager, mock_openai, mock_anthropic, _mock_gemini = self._make_manager()

        mock_openai.complete.side_effect = RuntimeError("openai 오류")
        mock_anthropic.complete.side_effect = RuntimeError("anthropic 오류")

        request = LLMRequest(user_prompt="테스트")
        with pytest.raises(AIError, match="LLM 호출 실패"):
            await manager.complete(request, mode="quick")

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
        mock_openai.complete_json.assert_called_once()

    async def test_complete_json_fallback(self) -> None:
        """complete_json primary 실패 시 fallback 전환."""
        from src.ai.analysis.models import TradingSignal

        manager, mock_openai, mock_anthropic, _mock_gemini = self._make_manager()

        mock_openai.complete_json.side_effect = RuntimeError("API 오류")

        signal = TradingSignal(symbol="005930", action="HOLD", confidence=0.5)
        response = _make_llm_response("anthropic")
        mock_anthropic.complete_json.return_value = (signal, response)

        request = LLMRequest(user_prompt="분석")
        _parsed, resp = await manager.complete_json(request, TradingSignal, mode="quick")

        assert resp.provider == "anthropic"
        mock_openai.complete_json.assert_called_once()
        mock_anthropic.complete_json.assert_called_once()

    async def test_primary_missing_auto_falls_through_to_fallback(self) -> None:
        """primary(openai) 클라이언트 미등록 시 fallback(anthropic)으로 자동 진행."""
        manager, _mock_openai, mock_anthropic, _mock_gemini = self._make_manager()

        # openai 클라이언트 제거 (키가 없었다고 가정)
        manager._clients.pop("openai", None)

        response = _make_llm_response("anthropic")
        mock_anthropic.complete.return_value = response

        request = LLMRequest(user_prompt="테스트")
        result = await manager.complete(request, mode="quick")

        assert result.provider == "anthropic"
        mock_anthropic.complete.assert_called_once()

    async def test_no_providers_registered_raises(self) -> None:
        """등록된 프로바이더가 하나도 없으면 AIError."""
        manager, _mock_openai, _mock_anthropic, _mock_gemini = self._make_manager()
        manager._clients.clear()

        request = LLMRequest(user_prompt="테스트")
        with pytest.raises(AIError, match="사용 가능한 LLM 프로바이더"):
            await manager.complete(request, mode="quick")

    # ── Gemini 3번째 fallback 시나리오 ──────────────────────────────

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

    async def test_fallback_chain_quick_with_gemini(self) -> None:
        """quick 모드 체인: openai → anthropic → gemini."""
        manager, _o, _a, _g = self._make_manager(gemini_api_key=_FAKE)
        assert manager._fallback_chain("quick") == ["openai", "anthropic", "gemini"]

    async def test_fallback_chain_deep_with_gemini(self) -> None:
        """deep 모드 체인: anthropic → openai → gemini."""
        manager, _o, _a, _g = self._make_manager(gemini_api_key=_FAKE)
        assert manager._fallback_chain("deep") == ["anthropic", "openai", "gemini"]

    async def test_gemini_third_fallback_on_both_primary_and_fallback_fail(self) -> None:
        """primary + fallback 모두 실패 시 gemini(3번째)로 전환."""
        manager, mock_openai, mock_anthropic, mock_gemini = self._make_manager(gemini_api_key=_FAKE)

        mock_openai.complete.side_effect = RuntimeError("openai 장애")
        mock_anthropic.complete.side_effect = RuntimeError("anthropic 장애")

        gemini_response = _make_llm_response("gemini", "gemini-1.5-flash", cost=0.0001)
        mock_gemini.complete.return_value = gemini_response

        request = LLMRequest(user_prompt="테스트")
        result = await manager.complete(request, mode="quick")

        assert result.provider == "gemini"
        mock_openai.complete.assert_called_once()
        mock_anthropic.complete.assert_called_once()
        mock_gemini.complete.assert_called_once()

    async def test_all_three_providers_fail_raises(self) -> None:
        """3-provider 모두 실패 시 AIError + 마지막 에러 chaining."""
        manager, mock_openai, mock_anthropic, mock_gemini = self._make_manager(gemini_api_key=_FAKE)

        mock_openai.complete.side_effect = RuntimeError("openai 장애")
        mock_anthropic.complete.side_effect = RuntimeError("anthropic 장애")
        mock_gemini.complete.side_effect = RuntimeError("gemini 장애")

        request = LLMRequest(user_prompt="테스트")
        with pytest.raises(AIError, match="LLM 호출 실패"):
            await manager.complete(request, mode="quick")

        mock_gemini.complete.assert_called_once()

    async def test_gemini_third_fallback_json(self) -> None:
        """complete_json에서도 3-provider fallback 동작."""
        from src.ai.analysis.models import TradingSignal

        manager, mock_openai, mock_anthropic, mock_gemini = self._make_manager(gemini_api_key=_FAKE)

        mock_openai.complete_json.side_effect = RuntimeError("openai")
        mock_anthropic.complete_json.side_effect = RuntimeError("anthropic")

        signal = TradingSignal(symbol="005930", action="HOLD", confidence=0.5)
        response = _make_llm_response("gemini", "gemini-1.5-flash")
        mock_gemini.complete_json.return_value = (signal, response)

        request = LLMRequest(user_prompt="분석")
        _parsed, resp = await manager.complete_json(request, TradingSignal, mode="quick")

        assert resp.provider == "gemini"
        mock_gemini.complete_json.assert_called_once()

    async def test_gemini_not_used_when_primary_succeeds(self) -> None:
        """primary 성공 시 gemini 미호출 (불필요 비용 방지)."""
        manager, mock_openai, mock_anthropic, mock_gemini = self._make_manager(gemini_api_key=_FAKE)

        response = _make_llm_response("openai")
        mock_openai.complete.return_value = response

        request = LLMRequest(user_prompt="테스트")
        result = await manager.complete(request, mode="quick")

        assert result.provider == "openai"
        mock_anthropic.complete.assert_not_called()
        mock_gemini.complete.assert_not_called()
