"""TTLCache 테스트."""

import time
from unittest.mock import patch

from src.ai.data.cache import TTLCache


class TestTTLCache:
    """TTLCache 클래스 테스트."""

    def test_get_set_basic(self) -> None:
        """기본 get/set 동작 확인."""
        cache = TTLCache(default_ttl=60)
        cache.set("key1", "value1")

        assert cache.get("key1") == "value1"

    def test_get_missing_key_returns_none(self) -> None:
        """존재하지 않는 키 조회 시 None 반환."""
        cache = TTLCache(default_ttl=60)

        assert cache.get("nonexistent") is None

    def test_ttl_expiration(self) -> None:
        """TTL 만료 후 None 반환."""
        cache = TTLCache(default_ttl=1)

        # 현재 시각 기준으로 set
        base_time = time.monotonic()
        with patch("src.ai.data.cache.time.monotonic", return_value=base_time):
            cache.set("key1", "value1")

        # 2초 후 → 만료
        with patch("src.ai.data.cache.time.monotonic", return_value=base_time + 2):
            assert cache.get("key1") is None

    def test_custom_ttl(self) -> None:
        """개별 TTL 설정 테스트."""
        cache = TTLCache(default_ttl=60)

        base_time = time.monotonic()
        with patch("src.ai.data.cache.time.monotonic", return_value=base_time):
            cache.set("short", "val", ttl=5)
            cache.set("long", "val", ttl=100)

        # 10초 후: short는 만료, long은 유효
        with patch("src.ai.data.cache.time.monotonic", return_value=base_time + 10):
            assert cache.get("short") is None
            assert cache.get("long") == "val"

    def test_delete(self) -> None:
        """캐시 항목 삭제."""
        cache = TTLCache(default_ttl=60)
        cache.set("key1", "value1")

        cache.delete("key1")
        assert cache.get("key1") is None

    def test_delete_nonexistent_key(self) -> None:
        """존재하지 않는 키 삭제 시 에러 없음."""
        cache = TTLCache(default_ttl=60)
        cache.delete("nonexistent")  # 에러 없이 통과해야 함

    def test_clear(self) -> None:
        """전체 캐시 초기화."""
        cache = TTLCache(default_ttl=60)
        cache.set("key1", "val1")
        cache.set("key2", "val2")

        cache.clear()

        assert cache.get("key1") is None
        assert cache.get("key2") is None

    def test_cleanup_expired_entries(self) -> None:
        """만료된 항목 정리 (cleanup)."""
        cache = TTLCache(default_ttl=1)

        base_time = time.monotonic()
        with patch("src.ai.data.cache.time.monotonic", return_value=base_time):
            cache.set("expired1", "v1", ttl=1)
            cache.set("expired2", "v2", ttl=2)
            cache.set("valid", "v3", ttl=100)

        # 5초 후: expired1, expired2 만료, valid 유효
        with patch("src.ai.data.cache.time.monotonic", return_value=base_time + 5):
            removed = cache.cleanup()
            assert removed == 2
            assert cache.get("valid") == "v3"

    def test_cleanup_no_expired(self) -> None:
        """만료 항목 없으면 0 반환."""
        cache = TTLCache(default_ttl=300)
        cache.set("k1", "v1")
        cache.set("k2", "v2")

        removed = cache.cleanup()
        assert removed == 0

    def test_overwrite_value(self) -> None:
        """같은 키에 값 덮어쓰기."""
        cache = TTLCache(default_ttl=60)
        cache.set("key1", "old")
        cache.set("key1", "new")

        assert cache.get("key1") == "new"
