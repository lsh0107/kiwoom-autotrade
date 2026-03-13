"""백테스트/매매 결과 조회 API 테스트."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi import HTTPException
from httpx import AsyncClient

from src.api.v1.results import get_result
from src.models.user import User


class TestListResults:
    """결과 목록 조회 테스트."""

    async def test_list_results(
        self,
        auth_client: AsyncClient,
        test_user: User,
        tmp_path: Path,
    ) -> None:
        """인증 + 파일 존재 → 200 + 파일 목록."""
        sample = tmp_path / "backtest_2026.json"
        sample.write_text(json.dumps({"strategy": "test"}), encoding="utf-8")

        with patch("src.api.v1.results.RESULTS_DIR", tmp_path):
            resp = await auth_client.get("/api/v1/results/list")

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["filename"] == "backtest_2026.json"
        assert "modified_at" in data[0]

    async def test_list_results_empty_dir(
        self,
        auth_client: AsyncClient,
        test_user: User,
        tmp_path: Path,
    ) -> None:
        """인증 + 빈 디렉토리 → 200 + []."""
        with patch("src.api.v1.results.RESULTS_DIR", tmp_path):
            resp = await auth_client.get("/api/v1/results/list")

        assert resp.status_code == 200
        assert resp.json() == []

    async def test_list_results_no_dir(
        self,
        auth_client: AsyncClient,
        test_user: User,
        tmp_path: Path,
    ) -> None:
        """인증 + 디렉토리 없음 → 200 + []."""
        nonexistent = tmp_path / "nonexistent"
        with patch("src.api.v1.results.RESULTS_DIR", nonexistent):
            resp = await auth_client.get("/api/v1/results/list")

        assert resp.status_code == 200
        assert resp.json() == []

    async def test_list_results_unauthenticated(
        self,
        client: AsyncClient,
    ) -> None:
        """미인증 → 401."""
        resp = await client.get("/api/v1/results/list")
        assert resp.status_code == 401


class TestGetResult:
    """개별 결과 조회 테스트."""

    async def test_get_result(
        self,
        auth_client: AsyncClient,
        test_user: User,
        tmp_path: Path,
    ) -> None:
        """인증 + 유효 파일명 → 200 + JSON 내용."""
        payload = {"strategy": "momentum", "profit": 12.5}
        sample = tmp_path / "backtest.json"
        sample.write_text(json.dumps(payload), encoding="utf-8")

        with patch("src.api.v1.results.RESULTS_DIR", tmp_path):
            resp = await auth_client.get("/api/v1/results/backtest.json")

        assert resp.status_code == 200
        assert resp.json() == payload

    async def test_get_result_not_found(
        self,
        auth_client: AsyncClient,
        test_user: User,
        tmp_path: Path,
    ) -> None:
        """인증 + 없는 파일명 → 404."""
        with patch("src.api.v1.results.RESULTS_DIR", tmp_path):
            resp = await auth_client.get("/api/v1/results/nonexistent.json")

        assert resp.status_code == 404

    async def test_get_result_path_traversal_dotdot(
        self,
        auth_client: AsyncClient,
        test_user: User,
    ) -> None:
        """경로 조작 (..) → 400."""
        resp = await auth_client.get("/api/v1/results/..secret.json")
        assert resp.status_code == 400

    async def test_get_result_path_traversal_slash(self) -> None:
        """경로에 / 포함 → 400 (Starlette가 %2F를 디코딩하므로 함수 직접 호출)."""
        with pytest.raises(HTTPException) as exc_info:
            await get_result("foo/bar.json", _current_user=None)  # type: ignore[arg-type]
        assert exc_info.value.status_code == 400

    async def test_get_result_path_traversal_backslash(
        self,
        auth_client: AsyncClient,
        test_user: User,
    ) -> None:
        r"""경로 조작 (\\) → 400."""
        resp = await auth_client.get("/api/v1/results/foo%5Cbar.json")
        assert resp.status_code == 400

    async def test_get_result_non_json(
        self,
        auth_client: AsyncClient,
        test_user: User,
        tmp_path: Path,
    ) -> None:
        """비-JSON 확장자 → 404."""
        txt_file = tmp_path / "test.txt"
        txt_file.write_text("not json", encoding="utf-8")

        with patch("src.api.v1.results.RESULTS_DIR", tmp_path):
            resp = await auth_client.get("/api/v1/results/test.txt")

        assert resp.status_code == 404

    async def test_get_result_unauthenticated(
        self,
        client: AsyncClient,
    ) -> None:
        """미인증 → 401."""
        resp = await client.get("/api/v1/results/any.json")
        assert resp.status_code == 401
