"""AES-256 대칭 암복호화 (Fernet 기반)."""

import base64

from cryptography.fernet import Fernet, InvalidToken

from src.config.settings import get_settings
from src.utils.exceptions import AppError


def _get_fernet() -> Fernet:
    """설정에서 encryption_key를 읽어 Fernet 인스턴스를 반환한다.

    Fernet은 URL-safe base64 인코딩된 32바이트 키를 요구한다.
    settings.encryption_key가 일반 문자열이면 SHA-256 해시 후 base64로 변환한다.
    """
    import hashlib

    settings = get_settings()
    raw_key = settings.encryption_key

    # 이미 유효한 Fernet 키인지 시도
    try:
        return Fernet(raw_key.encode())
    except (ValueError, Exception):  # noqa: S110
        pass

    # 일반 문자열이면 SHA-256 → base64로 변환
    digest = hashlib.sha256(raw_key.encode()).digest()
    fernet_key = base64.urlsafe_b64encode(digest)
    return Fernet(fernet_key)


def encrypt(plaintext: str) -> str:
    """평문을 암호화하여 base64 문자열로 반환한다."""
    fernet = _get_fernet()
    encrypted = fernet.encrypt(plaintext.encode())
    return encrypted.decode()


def decrypt(ciphertext: str) -> str:
    """암호화된 base64 문자열을 복호화하여 평문으로 반환한다."""
    fernet = _get_fernet()
    try:
        decrypted = fernet.decrypt(ciphertext.encode())
    except InvalidToken as e:
        raise AppError("복호화 실패: 유효하지 않은 암호문입니다", "DECRYPT_ERROR") from e
    return decrypted.decode()


def mask_value(value: str, visible: int = 4) -> str:
    """문자열 앞 N자리만 보이고 나머지는 마스킹한다.

    예: "abcdefgh" -> "abcd****"
    """
    if len(value) <= visible:
        return "*" * len(value)
    return value[:visible] + "*" * (len(value) - visible)
