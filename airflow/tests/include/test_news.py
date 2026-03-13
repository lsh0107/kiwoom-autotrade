"""뉴스 수집기 단위 테스트."""

from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

import pytest


class TestNewsCollector:
    """네이버 뉴스 수집기 테스트."""

    def _make_mock_requests(self, items: list[dict]) -> MagicMock:
        """requests mock 생성 헬퍼."""
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = {"items": items}
        mock_requests = MagicMock()
        mock_requests.get.return_value = mock_resp
        return mock_requests

    def test_collect_news_returns_list(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """정상 응답 시 기사 목록을 반환해야 한다."""
        monkeypatch.setenv("NAVER_CLIENT_ID", "test-id")
        monkeypatch.setenv("NAVER_CLIENT_SECRET", "test-secret")

        fake_items = [
            {"title": "삼성전자 급등", "description": "주가 상승"},
            {"title": "삼성전자 호재", "description": "실적 발표"},
        ]
        mock_requests = self._make_mock_requests(fake_items)

        sys.modules.pop("include.collectors.news", None)
        with (
            patch.dict(sys.modules, {"requests": mock_requests}),
            patch("include.collectors.news.time.sleep"),
        ):
            from include.collectors.news import collect_news

            result = collect_news(["삼성전자"])

        assert isinstance(result, list)
        assert len(result) == 2
        assert result[0]["keyword"] == "삼성전자"

    def test_collect_news_keyword_tagged(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """각 기사에 keyword 필드가 추가되어야 한다."""
        monkeypatch.setenv("NAVER_CLIENT_ID", "test-id")
        monkeypatch.setenv("NAVER_CLIENT_SECRET", "test-secret")

        mock_requests = self._make_mock_requests([{"title": "뉴스 제목", "description": "설명"}])

        sys.modules.pop("include.collectors.news", None)
        with (
            patch.dict(sys.modules, {"requests": mock_requests}),
            patch("include.collectors.news.time.sleep"),
        ):
            from include.collectors.news import collect_news

            result = collect_news(["SK하이닉스"])

        assert result[0]["keyword"] == "SK하이닉스"

    def test_collect_news_multiple_keywords(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """여러 키워드 검색 시 모든 결과가 합산되어야 한다."""
        monkeypatch.setenv("NAVER_CLIENT_ID", "test-id")
        monkeypatch.setenv("NAVER_CLIENT_SECRET", "test-secret")

        mock_requests = self._make_mock_requests([{"title": "뉴스", "description": "설명"}])

        sys.modules.pop("include.collectors.news", None)
        with (
            patch.dict(sys.modules, {"requests": mock_requests}),
            patch("include.collectors.news.time.sleep"),
        ):
            from include.collectors.news import collect_news

            result = collect_news(["삼성전자", "SK하이닉스", "현대차"])

        # 키워드 3개 x 기사 1개 = 3개
        assert len(result) == 3

    def test_collect_news_api_failure_continues(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """한 키워드 실패 시 나머지 키워드 수집을 계속해야 한다."""
        monkeypatch.setenv("NAVER_CLIENT_ID", "test-id")
        monkeypatch.setenv("NAVER_CLIENT_SECRET", "test-secret")

        mock_resp_ok = MagicMock()
        mock_resp_ok.raise_for_status.return_value = None
        mock_resp_ok.json.return_value = {"items": [{"title": "정상 기사", "description": ""}]}

        mock_resp_fail = MagicMock()
        mock_resp_fail.raise_for_status.side_effect = Exception("API 오류")

        mock_requests = MagicMock()
        mock_requests.get.side_effect = [mock_resp_fail, mock_resp_ok]

        sys.modules.pop("include.collectors.news", None)
        with (
            patch.dict(sys.modules, {"requests": mock_requests}),
            patch("include.collectors.news.time.sleep"),
        ):
            from include.collectors.news import collect_news

            result = collect_news(["실패키워드", "성공키워드"])

        # 실패한 키워드는 건너뛰고 성공한 기사만 반환
        assert len(result) == 1
        assert result[0]["keyword"] == "성공키워드"

    def test_collect_news_no_credentials_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """API 인증 정보 미설정 시 ValueError를 발생시켜야 한다."""
        monkeypatch.delenv("NAVER_CLIENT_ID", raising=False)
        monkeypatch.delenv("NAVER_CLIENT_SECRET", raising=False)

        sys.modules.pop("include.collectors.news", None)
        from include.collectors.news import collect_news

        with pytest.raises(ValueError, match="NAVER_CLIENT_ID"):
            collect_news(["삼성전자"])

    def test_collect_news_empty_response(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """빈 응답 시 빈 리스트를 반환해야 한다."""
        monkeypatch.setenv("NAVER_CLIENT_ID", "test-id")
        monkeypatch.setenv("NAVER_CLIENT_SECRET", "test-secret")

        mock_requests = self._make_mock_requests([])

        sys.modules.pop("include.collectors.news", None)
        with (
            patch.dict(sys.modules, {"requests": mock_requests}),
            patch("include.collectors.news.time.sleep"),
        ):
            from include.collectors.news import collect_news

            result = collect_news(["삼성전자"])

        assert result == []
