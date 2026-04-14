"""
缓存服务测试
测试L1缓存命中/过期、缓存键生成一致性
"""
import pytest
import time
import tempfile
import shutil
from pathlib import Path

from app.services.cache import (
    SimpleTTLCache,
    generate_cache_key,
    CacheService,
)


# ==================== 缓存键生成 ====================

class TestCacheKeyGeneration:
    """缓存键生成一致性测试"""

    def test_same_input_same_key(self):
        """相同输入产生相同key"""
        key1 = generate_cache_key("METAR ZSPD 110800Z 25012KT 9999 SCT040 28/22 Q1008", "pilot")
        key2 = generate_cache_key("METAR ZSPD 110800Z 25012KT 9999 SCT040 28/22 Q1008", "pilot")
        assert key1 == key2

    def test_different_role_different_key(self):
        """不同角色产生不同key"""
        key1 = generate_cache_key("METAR ZSPD 110800Z 25012KT 9999 SCT040 28/22 Q1008", "pilot")
        key2 = generate_cache_key("METAR ZSPD 110800Z 25012KT 9999 SCT040 28/22 Q1008", "dispatcher")
        assert key1 != key2

    def test_different_metar_different_key(self):
        """不同METAR产生不同key"""
        key1 = generate_cache_key("METAR ZSPD 110800Z 25012KT 9999 SCT040 28/22 Q1008", "pilot")
        key2 = generate_cache_key("METAR ZBAA 110800Z 35008MPS 9999 FEW040 12/M05 Q1018", "pilot")
        assert key1 != key2

    def test_whitespace_normalization(self):
        """空白不影响key（strip处理）"""
        key1 = generate_cache_key("  METAR ZSPD 110800Z 25012KT 9999 SCT040 28/22 Q1008  ", "pilot")
        key2 = generate_cache_key("METAR ZSPD 110800Z 25012KT 9999 SCT040 28/22 Q1008", "pilot")
        assert key1 == key2

    def test_extra_param(self):
        """extra参数影响key"""
        key1 = generate_cache_key("METAR ZSPD 110800Z 25012KT 9999 SCT040 28/22 Q1008", "pilot", "analysis")
        key2 = generate_cache_key("METAR ZSPD 110800Z 25012KT 9999 SCT040 28/22 Q1008", "pilot", "report")
        assert key1 != key2

    def test_key_length(self):
        """key应为16字符"""
        key = generate_cache_key("test", "pilot")
        assert len(key) == 16


# ==================== SimpleTTLCache ====================

class TestSimpleTTLCache:
    """SimpleTTLCache单元测试"""

    def test_set_and_get(self):
        cache = SimpleTTLCache(maxsize=10, ttl=60)
        cache.set("key1", "value1")
        assert cache.get("key1") == "value1"

    def test_get_nonexistent(self):
        cache = SimpleTTLCache(maxsize=10, ttl=60)
        assert cache.get("missing") is None

    def test_contains(self):
        cache = SimpleTTLCache(maxsize=10, ttl=60)
        cache.set("key1", "value1")
        assert "key1" in cache
        assert "key2" not in cache

    def test_delete(self):
        cache = SimpleTTLCache(maxsize=10, ttl=60)
        cache.set("key1", "value1")
        cache.delete("key1")
        assert cache.get("key1") is None

    def test_clear(self):
        cache = SimpleTTLCache(maxsize=10, ttl=60)
        cache.set("k1", "v1")
        cache.set("k2", "v2")
        cache.clear()
        assert cache.get("k1") is None
        assert cache.get("k2") is None

    def test_maxsize_eviction(self):
        """超出maxsize应驱逐最旧条目"""
        cache = SimpleTTLCache(maxsize=2, ttl=60)
        cache.set("k1", "v1")
        cache.set("k2", "v2")
        cache.set("k3", "v3")  # 触发驱逐
        assert cache.get("k1") is None  # k1被驱逐
        assert cache.get("k2") == "v2"
        assert cache.get("k3") == "v3"

    def test_ttl_expiry(self):
        """TTL过期后应返回None"""
        cache = SimpleTTLCache(maxsize=10, ttl=1)  # 1秒TTL
        cache.set("key1", "value1")
        assert cache.get("key1") == "value1"
        time.sleep(2)  # 等足够长确保过期
        assert cache.get("key1") is None

    def test_dict_interface(self):
        """字典式接口"""
        cache = SimpleTTLCache(maxsize=10, ttl=60)
        cache["key1"] = "value1"
        assert cache["key1"] == "value1"

    def test_dict_getitem_missing_raises(self):
        """__getitem__缺失key应抛KeyError"""
        cache = SimpleTTLCache(maxsize=10, ttl=60)
        with pytest.raises(KeyError):
            _ = cache["missing"]


# ==================== CacheService L1 ====================

class TestCacheServiceL1:
    """CacheService L1缓存测试"""

    @pytest.fixture
    def cache_service(self):
        """创建测试用CacheService（仅L1，无L2/L3）"""
        tmpdir = tempfile.mkdtemp()
        cs = CacheService(
            l1_maxsize=100,
            l1_ttl=5,  # 5秒TTL方便测试
            l3_cache_dir=tmpdir,
        )
        yield cs
        shutil.rmtree(tmpdir, ignore_errors=True)

    @pytest.mark.asyncio
    async def test_l1_set_and_get(self, cache_service):
        """L1缓存写入和读取"""
        await cache_service.set("test_key", {"data": "hello"})
        result = await cache_service.get("test_key")
        assert result == {"data": "hello"}

    @pytest.mark.asyncio
    async def test_l1_miss(self, cache_service):
        """L1缓存未命中"""
        result = await cache_service.get("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_l1_invalidate(self, cache_service):
        """L1缓存失效"""
        await cache_service.set("test_key", "value")
        await cache_service.invalidate("test_key")
        result = await cache_service.get("test_key")
        assert result is None

    @pytest.mark.asyncio
    async def test_l1_ttl_expiry(self, cache_service):
        """L1 TTL过期后应从L3回填"""
        await cache_service.set("test_key", "value")
        assert await cache_service.get("test_key") == "value"

        # L1过期，但L3仍有效，get会从L3回填
        time.sleep(6)
        result = await cache_service.get("test_key")
        # L3回填所以值仍然存在
        assert result == "value"

    @pytest.mark.asyncio
    async def test_l1_invalidate_all_levels(self, cache_service):
        """invalidate应清除所有层级"""
        await cache_service.set("test_key", "value")
        await cache_service.invalidate("test_key")
        result = await cache_service.get("test_key")
        assert result is None

    @pytest.mark.asyncio
    async def test_metar_cache(self, cache_service):
        """METAR缓存读写"""
        metar = "METAR ZSPD 110800Z 25012KT 9999 SCT040 28/22 Q1008"
        data = {"risk_level": "LOW", "parsed": True}
        await cache_service.set_metar_cache(metar, "pilot", data)

        result = await cache_service.get_metar_cache(metar, "pilot")
        assert result is not None
        assert result["risk_level"] == "LOW"

    def test_cache_stats(self, cache_service):
        """缓存统计"""
        stats = cache_service.get_stats()
        assert "l1_type" in stats
        assert "l1_size" in stats
        assert "l2_enabled" in stats
        assert "l3_dir" in stats
