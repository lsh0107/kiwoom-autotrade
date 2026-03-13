"""JWT 토큰 생성/검증 테스트."""

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import pytest
from jose import jwt as jose_jwt

from src.utils.exceptions import InvalidTokenError, TokenExpiredError
from src.utils.jwt import (
    clear_auth_cookies,
    create_access_token,
    create_refresh_token,
    decode_token,
    set_auth_cookies,
)


@pytest.fixture
def _mock_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    """JWT 관련 설정을 테스트용으로 패치한다."""
    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret-key-for-jwt")
    monkeypatch.setenv("JWT_ALGORITHM", "HS256")
    monkeypatch.setenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30")
    monkeypatch.setenv("REFRESH_TOKEN_EXPIRE_DAYS", "7")
    monkeypatch.setenv("DEBUG", "true")


@pytest.fixture
def user_id() -> uuid.UUID:
    """테스트 사용자 UUID."""
    return uuid.UUID("12345678-1234-5678-1234-567812345678")


@pytest.mark.usefixtures("_mock_settings")
class TestCreateAccessToken:
    """create_access_token 함수 테스트."""

    def test_create_access_token(self, user_id: uuid.UUID) -> None:
        """액세스 토큰 생성 및 디코딩."""
        token = create_access_token(user_id)

        assert isinstance(token, str)
        assert len(token) > 0

        # 토큰 디코딩하여 내용 확인
        payload = jose_jwt.decode(token, "test-secret-key-for-jwt", algorithms=["HS256"])
        assert payload["sub"] == str(user_id)
        assert payload["type"] == "access"
        assert "exp" in payload


@pytest.mark.usefixtures("_mock_settings")
class TestCreateRefreshToken:
    """create_refresh_token 함수 테스트."""

    def test_create_refresh_token(self, user_id: uuid.UUID) -> None:
        """리프레시 토큰 생성."""
        token = create_refresh_token(user_id)

        assert isinstance(token, str)
        assert len(token) > 0

        payload = jose_jwt.decode(token, "test-secret-key-for-jwt", algorithms=["HS256"])
        assert payload["sub"] == str(user_id)
        assert payload["type"] == "refresh"
        assert "exp" in payload


@pytest.mark.usefixtures("_mock_settings")
class TestDecodeToken:
    """decode_token 함수 테스트."""

    def test_decode_valid_token(self, user_id: uuid.UUID) -> None:
        """유효한 토큰 디코딩."""
        token = create_access_token(user_id)
        payload = decode_token(token)

        assert payload["sub"] == str(user_id)
        assert payload["type"] == "access"

    def test_decode_expired_token(self) -> None:
        """만료 토큰 디코딩 시 TokenExpiredError."""
        # 이미 만료된 토큰을 직접 생성
        payload = {
            "sub": str(uuid.uuid4()),
            "exp": datetime.now(UTC) - timedelta(hours=1),
            "type": "access",
        }
        token = jose_jwt.encode(payload, "test-secret-key-for-jwt", algorithm="HS256")

        with pytest.raises(TokenExpiredError):
            decode_token(token)

    def test_decode_invalid_token(self) -> None:
        """잘못된 토큰 디코딩 시 InvalidTokenError."""
        with pytest.raises(InvalidTokenError):
            decode_token("invalid.token.value")

    def test_decode_token_missing_sub(self) -> None:
        """sub 필드가 없는 토큰 디코딩 시 InvalidTokenError."""
        payload = {
            "exp": datetime.now(UTC) + timedelta(hours=1),
            "type": "access",
        }
        token = jose_jwt.encode(payload, "test-secret-key-for-jwt", algorithm="HS256")

        with pytest.raises(InvalidTokenError):
            decode_token(token)

    def test_decode_token_missing_type(self) -> None:
        """type 필드가 없는 토큰 디코딩 시 InvalidTokenError."""
        payload = {
            "sub": str(uuid.uuid4()),
            "exp": datetime.now(UTC) + timedelta(hours=1),
        }
        token = jose_jwt.encode(payload, "test-secret-key-for-jwt", algorithm="HS256")

        with pytest.raises(InvalidTokenError):
            decode_token(token)


@pytest.mark.usefixtures("_mock_settings")
class TestSetAuthCookies:
    """set_auth_cookies 함수 테스트."""

    def test_set_auth_cookies(self) -> None:
        """쿠키 설정 검증."""
        response = MagicMock()
        set_auth_cookies(response, "access_token_value", "refresh_token_value")

        # set_cookie가 2번 호출됨 (access + refresh)
        assert response.set_cookie.call_count == 2

        # access token cookie 확인
        access_call = response.set_cookie.call_args_list[0]
        assert access_call.kwargs["key"] == "access_token"
        assert access_call.kwargs["value"] == "access_token_value"
        assert access_call.kwargs["httponly"] is True
        assert access_call.kwargs["samesite"] == "lax"
        assert access_call.kwargs["path"] == "/"

        # refresh token cookie 확인
        refresh_call = response.set_cookie.call_args_list[1]
        assert refresh_call.kwargs["key"] == "refresh_token"
        assert refresh_call.kwargs["value"] == "refresh_token_value"
        assert refresh_call.kwargs["httponly"] is True
        assert refresh_call.kwargs["path"] == "/api/v1/auth/refresh"

    def test_set_auth_cookies_secure_in_production(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """프로덕션(debug=False)에서 secure=True."""
        monkeypatch.setenv("DEBUG", "false")
        response = MagicMock()
        set_auth_cookies(response, "at", "rt")

        access_call = response.set_cookie.call_args_list[0]
        assert access_call.kwargs["secure"] is True


class TestClearAuthCookies:
    """clear_auth_cookies 함수 테스트."""

    def test_clear_auth_cookies(self) -> None:
        """쿠키 삭제 검증."""
        response = MagicMock()
        clear_auth_cookies(response)

        # delete_cookie가 2번 호출됨
        assert response.delete_cookie.call_count == 2

        # access token 삭제 확인
        access_call = response.delete_cookie.call_args_list[0]
        assert access_call.kwargs["key"] == "access_token"
        assert access_call.kwargs["path"] == "/"

        # refresh token 삭제 확인
        refresh_call = response.delete_cookie.call_args_list[1]
        assert refresh_call.kwargs["key"] == "refresh_token"
        assert refresh_call.kwargs["path"] == "/api/v1/auth/refresh"
