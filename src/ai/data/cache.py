"""TTL 기반 인메모리 캐시."""

import time
from dataclasses import dataclass
from typing import Any


@dataclass
class CacheEntry:
    """캐시 항목."""

    value: Any
    expires_at: float


class TTLCache:
    """TTL 기반 인메모리 캐시."""

    def __init__(self, default_ttl: int = 300) -> None:
        self._cache: dict[str, CacheEntry] = {}
        self._default_ttl = default_ttl

    def get(self, key: str) -> Any | None:
        """캐시 조회. 만료 시 None."""
        entry = self._cache.get(key)
        if entry is None:
            return None
        if time.monotonic() > entry.expires_at:
            del self._cache[key]
            return None
        return entry.value

    def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        """캐시 저장."""
        expires_at = time.monotonic() + (ttl or self._default_ttl)
        self._cache[key] = CacheEntry(value=value, expires_at=expires_at)

    def delete(self, key: str) -> None:
        """캐시 삭제."""
        self._cache.pop(key, None)

    def clear(self) -> None:
        """전체 캐시 초기화."""
        self._cache.clear()

    def cleanup(self) -> int:
        """만료된 항목 정리. 삭제된 수 반환."""
        now = time.monotonic()
        expired = [k for k, v in self._cache.items() if now > v.expires_at]
        for k in expired:
            del self._cache[k]
        return len(expired)
