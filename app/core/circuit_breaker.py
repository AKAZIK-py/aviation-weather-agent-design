"""
Circuit Breaker 模式实现
用于 LLM 多层级降级策略中保护下游服务

状态流转: CLOSED → OPEN → HALF_OPEN → CLOSED
"""
import time
import asyncio
import logging
from enum import Enum
from typing import Optional, Callable, Any
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)


class CircuitState(str, Enum):
    """熔断器状态"""
    CLOSED = "CLOSED"        # 正常状态，请求通过
    OPEN = "OPEN"            # 熔断状态，请求被拒绝
    HALF_OPEN = "HALF_OPEN"  # 半开状态，允许探测请求


class CircuitBreakerOpenError(Exception):
    """熔断器开启时抛出的异常"""
    def __init__(self, name: str, failure_count: int):
        self.name = name
        self.failure_count = failure_count
        super().__init__(
            f"Circuit breaker '{name}' is OPEN "
            f"(failures: {failure_count}). "
            f"Requests are temporarily blocked."
        )


class CircuitBreaker:
    """
    异步 Circuit Breaker 实现
    
    Args:
        name: 熔断器名称（用于日志和监控）
        failure_threshold: 触发熔断的连续失败次数
        recovery_timeout: 熔断后等待恢复的秒数
        half_open_max_calls: 半开状态下允许的探测请求数
    """
    
    def __init__(
        self,
        name: str = "default",
        failure_threshold: int = 3,
        recovery_timeout: float = 30.0,
        half_open_max_calls: int = 1,
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls
        
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: float = 0
        self._half_open_calls = 0
        self._lock = asyncio.Lock()
    
    @property
    def state(self) -> CircuitState:
        """获取当前状态（惰性检查OPEN → HALF_OPEN转换）"""
        if self._state == CircuitState.OPEN:
            elapsed = time.time() - self._last_failure_time
            if elapsed >= self.recovery_timeout:
                self._state = CircuitState.HALF_OPEN
                self._half_open_calls = 0
                logger.info(
                    f"Circuit breaker '{self.name}': "
                    f"OPEN → HALF_OPEN (timeout {self.recovery_timeout}s elapsed)"
                )
        return self._state
    
    @property
    def failure_count(self) -> int:
        return self._failure_count
    
    @property
    def is_closed(self) -> bool:
        return self.state == CircuitState.CLOSED
    
    @property
    def is_open(self) -> bool:
        return self.state == CircuitState.OPEN
    
    async def record_success(self):
        """记录一次成功调用"""
        async with self._lock:
            self._success_count += 1
            if self._state == CircuitState.HALF_OPEN:
                self._half_open_calls += 1
                if self._half_open_calls >= self.half_open_max_calls:
                    self._state = CircuitState.CLOSED
                    self._failure_count = 0
                    logger.info(
                        f"Circuit breaker '{self.name}': "
                        f"HALF_OPEN → CLOSED (recovered)"
                    )
            elif self._state == CircuitState.CLOSED:
                # 连续成功时重置失败计数
                self._failure_count = max(0, self._failure_count - 1)
    
    async def record_failure(self):
        """记录一次失败调用"""
        async with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.time()
            
            if self._state == CircuitState.HALF_OPEN:
                # 半开状态下失败，重新熔断
                self._state = CircuitState.OPEN
                logger.warning(
                    f"Circuit breaker '{self.name}': "
                    f"HALF_OPEN → OPEN (probe failed)"
                )
            elif self._state == CircuitState.CLOSED:
                if self._failure_count >= self.failure_threshold:
                    self._state = CircuitState.OPEN
                    logger.warning(
                        f"Circuit breaker '{self.name}': "
                        f"CLOSED → OPEN (failures: {self._failure_count}/{self.failure_threshold})"
                    )
    
    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        通过熔断器执行函数
        
        Raises:
            CircuitBreakerOpenError: 熔断器开启时
        """
        current_state = self.state
        
        if current_state == CircuitState.OPEN:
            raise CircuitBreakerOpenError(self.name, self._failure_count)
        
        if current_state == CircuitState.HALF_OPEN:
            async with self._lock:
                if self._half_open_calls >= self.half_open_max_calls:
                    raise CircuitBreakerOpenError(self.name, self._failure_count)
                self._half_open_calls += 1
        
        try:
            result = await func(*args, **kwargs)
            await self.record_success()
            return result
        except CircuitBreakerOpenError:
            raise
        except Exception as e:
            await self.record_failure()
            raise
    
    @asynccontextmanager
    async def protect(self):
        """
        异步上下文管理器保护代码块
        
        使用方式:
            async with circuit_breaker.protect():
                result = await some_api_call()
        """
        current_state = self.state
        
        if current_state == CircuitState.OPEN:
            raise CircuitBreakerOpenError(self.name, self._failure_count)
        
        if current_state == CircuitState.HALF_OPEN:
            async with self._lock:
                if self._half_open_calls >= self.half_open_max_calls:
                    raise CircuitBreakerOpenError(self.name, self._failure_count)
                self._half_open_calls += 1
        
        try:
            yield
            await self.record_success()
        except CircuitBreakerOpenError:
            raise
        except Exception as e:
            await self.record_failure()
            raise
    
    def reset(self):
        """重置熔断器状态"""
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._half_open_calls = 0
        logger.info(f"Circuit breaker '{self.name}': reset to CLOSED")
    
    def get_stats(self) -> dict:
        """获取统计信息"""
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self._failure_count,
            "success_count": self._success_count,
            "failure_threshold": self.failure_threshold,
            "recovery_timeout": self.recovery_timeout,
            "last_failure_time": self._last_failure_time,
        }
    
    def __repr__(self) -> str:
        return (
            f"CircuitBreaker(name='{self.name}', "
            f"state={self.state.value}, "
            f"failures={self._failure_count}/{self.failure_threshold})"
        )
