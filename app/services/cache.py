"""
三级缓存架构服务
L1: 进程内 TTLCache (cachetools, TTL=300s)
L2: Redis (可选)
L3: 文件持久化 (JSON)
"""
import hashlib
import json
import os
import time
import logging
from typing import Optional, Any, Dict
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)

# L1 缓存: 使用 cachetools TTLCache
try:
    from cachetools import TTLCache
    HAS_CACHETOOLS = True
except ImportError:
    HAS_CACHETOOLS = False
    logger.warning("cachetools not installed, L1 cache will use simple dict fallback")

# L2 缓存: Redis 可选
try:
    import redis.asyncio as redis
    HAS_REDIS = True
except ImportError:
    HAS_REDIS = False
    logger.debug("redis not installed, L2 cache disabled")


class SimpleTTLCache:
    """简单TTL缓存（当cachetools不可用时的回退）"""
    
    def __init__(self, maxsize: int = 1000, ttl: int = 300):
        self.maxsize = maxsize
        self.ttl = ttl
        self._cache: Dict[str, tuple] = {}  # key -> (value, expire_time)
    
    def __len__(self) -> int:
        return len(self._cache)
    
    def __setitem__(self, key: str, value: Any):
        self.set(key, value)
    
    def __getitem__(self, key: str) -> Optional[Any]:
        result = self.get(key)
        if result is None:
            raise KeyError(key)
        return result
    
    def __contains__(self, key: str) -> bool:
        return self.get(key) is not None
    
    def get(self, key: str) -> Optional[Any]:
        if key in self._cache:
            value, expire_time = self._cache[key]
            if time.time() < expire_time:
                return value
            else:
                del self._cache[key]
        return None
    
    def set(self, key: str, value: Any):
        if len(self._cache) >= self.maxsize:
            # 移除最旧的条目
            oldest_key = next(iter(self._cache))
            del self._cache[oldest_key]
        self._cache[key] = (value, time.time() + self.ttl)
    
    def pop(self, key: str, default=None):
        return self._cache.pop(key, default)
    
    def delete(self, key: str):
        self._cache.pop(key, None)
    
    def clear(self):
        self._cache.clear()


def generate_cache_key(metar: str, role: str = "", extra: str = "") -> str:
    """
    生成缓存键
    
    Args:
        metar: 原始METAR报文
        role: 用户角色
        extra: 额外标识
    
    Returns:
        16字符的SHA256哈希前缀
    """
    raw_key = f"{metar.strip()}:{role}:{extra}"
    return hashlib.sha256(raw_key.encode()).hexdigest()[:16]


class CacheService:
    """
    三级缓存服务
    
    L1: 进程内缓存 (TTL=300s, maxsize=1000)
    L2: Redis (可选, TTL=600s)
    L3: 文件持久化 (JSON, TTL=1800s)
    
    读取策略: L1 → L2 → L3 → miss
    写入策略: 同时写入所有已启用的层级
    """
    
    def __init__(
        self,
        l1_maxsize: int = 1000,
        l1_ttl: int = 300,
        l2_redis_url: Optional[str] = None,
        l2_ttl: int = 600,
        l3_cache_dir: Optional[str] = None,
        l3_ttl: int = 1800,
    ):
        # L1 缓存初始化
        self.l1_ttl = l1_ttl
        if HAS_CACHETOOLS:
            self._l1 = TTLCache(maxsize=l1_maxsize, ttl=l1_ttl)
            self._l1_type = "cachetools"
        else:
            self._l1 = SimpleTTLCache(maxsize=l1_maxsize, ttl=l1_ttl)
            self._l1_type = "simple"
        
        # L2 Redis 缓存
        self._l2_redis: Optional[redis.Redis] = None
        self._l2_ttl = l2_ttl
        if HAS_REDIS and l2_redis_url:
            try:
                self._l2_redis = redis.from_url(l2_redis_url, decode_responses=True)
                logger.info(f"L2 Redis cache configured: {l2_redis_url[:20]}...")
            except Exception as e:
                logger.warning(f"Failed to connect Redis: {e}, L2 cache disabled")
        
        # L3 文件缓存
        self._l3_dir = Path(l3_cache_dir or os.path.join(os.getcwd(), ".cache", "metar"))
        self._l3_ttl = l3_ttl
        self._l3_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(
            f"CacheService initialized: "
            f"L1={self._l1_type}(ttl={l1_ttl}s), "
            f"L2={'redis' if self._l2_redis else 'disabled'}, "
            f"L3=file(ttl={l3_ttl}s, dir={self._l3_dir})"
        )
    
    async def get(self, key: str) -> Optional[Any]:
        """
        三级缓存读取
        
        Returns:
            缓存值或 None (miss)
        """
        # L1 查询
        value = self._l1_get(key)
        if value is not None:
            logger.debug(f"Cache L1 HIT: {key}")
            return value
        
        # L2 查询 (Redis)
        if self._l2_redis:
            value = await self._l2_get(key)
            if value is not None:
                logger.debug(f"Cache L2 HIT: {key}")
                # 回填 L1
                self._l1_set(key, value)
                return value
        
        # L3 查询 (文件)
        value = self._l3_get(key)
        if value is not None:
            logger.debug(f"Cache L3 HIT: {key}")
            # 回填 L1 和 L2
            self._l1_set(key, value)
            if self._l2_redis:
                await self._l2_set(key, value)
            return value
        
        logger.debug(f"Cache MISS: {key}")
        return None
    
    async def set(self, key: str, value: Any, ttl: Optional[int] = None):
        """
        三级缓存写入
        同时写入所有已启用的层级
        """
        self._l1_set(key, value)
        
        if self._l2_redis:
            await self._l2_set(key, value, ttl)
        
        self._l3_set(key, value, ttl)
    
    async def invalidate(self, key: str):
        """清除指定键的缓存"""
        self._l1_delete(key)
        
        if self._l2_redis:
            await self._l2_delete(key)
        
        self._l3_delete(key)
        
        logger.info(f"Cache invalidated: {key}")
    
    async def get_metar_cache(self, metar: str, role: str = "") -> Optional[Dict]:
        """获取METAR分析缓存"""
        key = generate_cache_key(metar, role, "analysis")
        cached = await self.get(key)
        if cached and isinstance(cached, dict):
            # 检查缓存是否过期 (METAR 有效期 30 分钟)
            cached_time = cached.get("_cached_at", 0)
            if time.time() - cached_time > 1800:
                await self.invalidate(key)
                return None
        return cached
    
    async def set_metar_cache(self, metar: str, role: str, data: Dict):
        """设置METAR分析缓存"""
        key = generate_cache_key(metar, role, "analysis")
        data["_cached_at"] = time.time()
        await self.set(key, data, ttl=1800)
    
    async def get_llm_cache(self, prompt_hash: str) -> Optional[str]:
        """获取LLM响应缓存"""
        key = f"llm:{prompt_hash}"
        return await self.get(key)
    
    async def set_llm_cache(self, prompt_hash: str, response: str):
        """设置LLM响应缓存"""
        key = f"llm:{prompt_hash}"
        await self.set(key, response, ttl=600)
    
    # ========== L1 内存缓存操作 ==========
    
    def _l1_get(self, key: str) -> Optional[Any]:
        if HAS_CACHETOOLS:
            return self._l1.get(key)
        else:
            return self._l1.get(key)
    
    def _l1_set(self, key: str, value: Any):
        try:
            self._l1[key] = value
        except Exception as e:
            logger.warning(f"L1 cache set error: {e}")
    
    def _l1_delete(self, key: str):
        if HAS_CACHETOOLS:
            self._l1.pop(key, None)
        else:
            self._l1.delete(key)
    
    # ========== L2 Redis 缓存操作 ==========
    
    async def _l2_get(self, key: str) -> Optional[Any]:
        if not self._l2_redis:
            return None
        try:
            raw = await self._l2_redis.get(f"aviation:{key}")
            if raw:
                return json.loads(raw)
        except Exception as e:
            logger.warning(f"L2 cache get error: {e}")
        return None
    
    async def _l2_set(self, key: str, value: Any, ttl: Optional[int] = None):
        if not self._l2_redis:
            return
        try:
            raw = json.dumps(value, ensure_ascii=False, default=str)
            await self._l2_redis.setex(
                f"aviation:{key}",
                ttl or self._l2_ttl,
                raw
            )
        except Exception as e:
            logger.warning(f"L2 cache set error: {e}")
    
    async def _l2_delete(self, key: str):
        if not self._l2_redis:
            return
        try:
            await self._l2_redis.delete(f"aviation:{key}")
        except Exception as e:
            logger.warning(f"L2 cache delete error: {e}")
    
    # ========== L3 文件缓存操作 ==========
    
    def _l3_path(self, key: str) -> Path:
        return self._l3_dir / f"{key}.json"
    
    def _l3_get(self, key: str) -> Optional[Any]:
        path = self._l3_path(key)
        if not path.exists():
            return None
        try:
            stat = path.stat()
            if time.time() - stat.st_mtime > self._l3_ttl:
                path.unlink(missing_ok=True)
                return None
            with open(path, 'r', encoding='utf-8') as f:
                wrapper = json.load(f)
                return wrapper.get("data")
        except Exception as e:
            logger.warning(f"L3 cache get error: {e}")
            return None
    
    def _l3_set(self, key: str, value: Any, ttl: Optional[int] = None):
        path = self._l3_path(key)
        try:
            wrapper = {
                "data": value,
                "cached_at": datetime.now().isoformat(),
                "ttl": ttl or self._l3_ttl,
            }
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(wrapper, f, ensure_ascii=False, default=str)
        except Exception as e:
            logger.warning(f"L3 cache set error: {e}")
    
    def _l3_delete(self, key: str):
        path = self._l3_path(key)
        path.unlink(missing_ok=True)
    
    def get_stats(self) -> Dict:
        """获取缓存统计"""
        stats = {
            "l1_type": self._l1_type,
            "l1_size": len(self._l1),
            "l2_enabled": self._l2_redis is not None,
            "l3_dir": str(self._l3_dir),
            "l3_files": len(list(self._l3_dir.glob("*.json"))) if self._l3_dir.exists() else 0,
        }
        return stats


# ========== 全局单例 ==========

_cache_service: Optional[CacheService] = None


def get_cache_service(
    l1_maxsize: int = 1000,
    l1_ttl: int = 300,
    l2_redis_url: Optional[str] = None,
    l3_cache_dir: Optional[str] = None,
) -> CacheService:
    """获取缓存服务单例"""
    global _cache_service
    if _cache_service is None:
        # 尝试从环境变量获取Redis URL
        if l2_redis_url is None:
            l2_redis_url = os.getenv("REDIS_URL")
        _cache_service = CacheService(
            l1_maxsize=l1_maxsize,
            l1_ttl=l1_ttl,
            l2_redis_url=l2_redis_url,
            l3_cache_dir=l3_cache_dir,
        )
    return _cache_service
