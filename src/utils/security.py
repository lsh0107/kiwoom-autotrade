"""비밀번호 해싱 (bcrypt)."""

import bcrypt


def hash_password(password: str) -> str:
    """비밀번호를 bcrypt로 해시한다."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """평문 비밀번호와 해시를 비교 검증한다."""
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
