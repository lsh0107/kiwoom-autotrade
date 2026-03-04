"""암복호화 유틸 테스트."""

import pytest
from src.utils.crypto import decrypt, encrypt, mask_value
from src.utils.exceptions import AppError


class TestEncryptDecrypt:
    """Fernet 암복호화 테스트."""

    def test_encrypt_decrypt_roundtrip(self) -> None:
        """encrypt → decrypt 왕복 성공."""
        plaintext = "my_secret_api_key_12345"
        ciphertext = encrypt(plaintext)

        assert ciphertext != plaintext
        assert decrypt(ciphertext) == plaintext

    def test_decrypt_with_wrong_key_fails(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """다른 키로 decrypt 시 실패."""
        ciphertext = encrypt("some_secret")

        # crypto 모듈이 직접 참조하는 get_settings를 패치
        from src.utils import crypto as crypto_module

        class FakeSettings:
            encryption_key = "completely_different_key_for_test"

        monkeypatch.setattr(crypto_module, "get_settings", lambda: FakeSettings())

        with pytest.raises(AppError, match="복호화 실패"):
            decrypt(ciphertext)


class TestMaskValue:
    """mask_value 테스트."""

    def test_mask_normal(self) -> None:
        """일반 문자열 마스킹."""
        assert mask_value("abcdefgh") == "abcd****"

    def test_mask_short_string(self) -> None:
        """visible 이하 길이 문자열 전체 마스킹."""
        assert mask_value("abc", visible=4) == "***"

    def test_mask_exact_visible(self) -> None:
        """visible과 길이가 같으면 전체 마스킹."""
        assert mask_value("abcd", visible=4) == "****"

    def test_mask_custom_visible(self) -> None:
        """visible 파라미터 커스텀."""
        assert mask_value("1234567890", visible=6) == "123456****"
