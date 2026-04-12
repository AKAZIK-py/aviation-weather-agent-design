"""
航空天气AI系统 - API保护机制
实现熔断器、超时控制、重试机制
"""

import time
import threading
from typing import Callable, Any, Optional, Dict
from functools import wraps
from datetime import datetime, timedelta
from enum import Enum


class CircuitState(Enum):
    """熔断器状态"""
    CLOSED = "closed"      # 正常状态
    OPEN = "open"          # 熔断状态
    HALF_OPEN = "half_open"  # 半开状态（试探性恢复）


class CircuitBreaker:
    """
    熔断器实现
    防止系统持续调用失败的服务，保护系统稳定性
    """
    
    def __init__(self, 
                 failure_threshold: int = 5,
                 timeout: int = 60,
                 success_threshold: int = 2):
        """
        初始化熔断器
        
        Args:
            failure_threshold: 失败次数阈值，达到后熔断
            timeout: 熔断持续时间（秒）
            success_threshold: 半开状态下成功次数阈值，达到后恢复
        """
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.success_threshold = success_threshold
        
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[datetime] = None
        
        self._lock = threading.Lock()
        
        # 统计信息
        self.stats = {
            "total_calls": 0,
            "successful_calls": 0,
            "failed_calls": 0,
            "circuit_open_calls": 0,
            "state_changes": 0
        }
    
    def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        通过熔断器调用函数
        
        Args:
            func: 要调用的函数
            *args, **kwargs: 函数参数
        
        Returns:
            函数返回值
        
        Raises:
            Exception: 熔断器处于OPEN状态或函数执行失败
        """
        with self._lock:
            self.stats["total_calls"] += 1
            
            # 检查是否应该尝试恢复
            if self.state == CircuitState.OPEN:
                if self._should_attempt_reset():
                    self._transition_to(CircuitState.HALF_OPEN)
                else:
                    self.stats["circuit_open_calls"] += 1
                    raise Exception("熔断器处于开启状态，拒绝请求")
        
        try:
            result = func(*args, **kwargs)
            self._record_success()
            return result
            
        except Exception as e:
            self._record_failure()
            raise e
    
    def _should_attempt_reset(self) -> bool:
        """检查是否应该尝试重置熔断器"""
        if self.last_failure_time is None:
            return False
        
        elapsed = datetime.now() - self.last_failure_time
        return elapsed >= timedelta(seconds=self.timeout)
    
    def _transition_to(self, new_state: CircuitState):
        """状态转换"""
        if self.state != new_state:
            self.state = new_state
            self.stats["state_changes"] += 1
            
            if new_state == CircuitState.HALF_OPEN:
                self.success_count = 0
    
    def _record_success(self):
        """记录成功调用"""
        with self._lock:
            self.stats["successful_calls"] += 1
            
            if self.state == CircuitState.HALF_OPEN:
                self.success_count += 1
                if self.success_count >= self.success_threshold:
                    self._transition_to(CircuitState.CLOSED)
                    self.failure_count = 0
    
    def _record_failure(self):
        """记录失败调用"""
        with self._lock:
            self.stats["failed_calls"] += 1
            self.failure_count += 1
            self.last_failure_time = datetime.now()
            
            if self.state == CircuitState.HALF_OPEN:
                # 半开状态下失败，立即熔断
                self._transition_to(CircuitState.OPEN)
            elif self.failure_count >= self.failure_threshold:
                # 达到失败阈值，熔断
                self._transition_to(CircuitState.OPEN)
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        with self._lock:
            return {
                **self.stats,
                "current_state": self.state.value,
                "failure_count": self.failure_count,
                "success_count": self.success_count
            }
    
    def reset(self):
        """重置熔断器"""
        with self._lock:
            self.state = CircuitState.CLOSED
            self.failure_count = 0
            self.success_count = 0
            self.last_failure_time = None


class TimeoutHandler:
    """超时控制处理器"""
    
    def __init__(self, timeout_seconds: int = 30):
        """
        初始化超时处理器
        
        Args:
            timeout_seconds: 超时时间（秒）
        """
        self.timeout = timeout_seconds
        self.stats = {
            "total_calls": 0,
            "timeout_calls": 0,
            "successful_calls": 0
        }
        self._lock = threading.Lock()
    
    def call_with_timeout(self, func: Callable, *args, **kwargs) -> Any:
        """
        带超时控制的函数调用
        
        Args:
            func: 要调用的函数
            *args, **kwargs: 函数参数
        
        Returns:
            函数返回值
        
        Raises:
            TimeoutError: 调用超时
        """
        with self._lock:
            self.stats["total_calls"] += 1
        
        result = [None]
        exception = [None]
        
        def worker():
            try:
                result[0] = func(*args, **kwargs)
            except Exception as e:
                exception[0] = e
        
        thread = threading.Thread(target=worker)
        thread.daemon = True
        thread.start()
        thread.join(timeout=self.timeout)
        
        if thread.is_alive():
            # 超时
            with self._lock:
                self.stats["timeout_calls"] += 1
            raise TimeoutError(f"调用超时（{self.timeout}秒）")
        
        if exception[0] is not None:
            raise exception[0]
        
        with self._lock:
            self.stats["successful_calls"] += 1
        
        return result[0]
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        with self._lock:
            return self.stats.copy()


class RetryMechanism:
    """重试机制"""
    
    def __init__(self, 
                 max_retries: int = 3,
                 backoff_factor: float = 1.0,
                 retryable_exceptions: Optional[list] = None):
        """
        初始化重试机制
        
        Args:
            max_retries: 最大重试次数
            backoff_factor: 退避因子（指数退避）
            retryable_exceptions: 可重试的异常类型列表
        """
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor
        self.retryable_exceptions = retryable_exceptions or [Exception]
        
        self.stats = {
            "total_calls": 0,
            "successful_calls": 0,
            "retry_calls": 0,
            "final_failures": 0
        }
        self._lock = threading.Lock()
    
    def call_with_retry(self, func: Callable, *args, **kwargs) -> Any:
        """
        带重试机制的函数调用
        
        Args:
            func: 要调用的函数
            *args, **kwargs: 函数参数
        
        Returns:
            函数返回值
        
        Raises:
            Exception: 重试耗尽后仍然失败
        """
        with self._lock:
            self.stats["total_calls"] += 1
        
        last_exception = None
        
        for attempt in range(self.max_retries + 1):
            try:
                result = func(*args, **kwargs)
                
                with self._lock:
                    if attempt > 0:
                        self.stats["retry_calls"] += 1
                    self.stats["successful_calls"] += 1
                
                return result
                
            except tuple(self.retryable_exceptions) as e:
                last_exception = e
                
                if attempt < self.max_retries:
                    # 计算退避时间
                    wait_time = self.backoff_factor * (2 ** attempt)
                    time.sleep(wait_time)
                else:
                    # 重试耗尽
                    with self._lock:
                        self.stats["final_failures"] += 1
                    raise last_exception
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        with self._lock:
            return self.stats.copy()


class APIProtection:
    """
    API保护组合器
    集成熔断器、超时控制、重试机制
    """
    
    def __init__(self,
                 failure_threshold: int = 5,
                 circuit_timeout: int = 60,
                 call_timeout: int = 30,
                 max_retries: int = 3,
                 backoff_factor: float = 1.0):
        """
        初始化API保护器
        
        Args:
            failure_threshold: 熔断失败阈值
            circuit_timeout: 熔断持续时间（秒）
            call_timeout: 单次调用超时（秒）
            max_retries: 最大重试次数
            backoff_factor: 重试退避因子
        """
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=failure_threshold,
            timeout=circuit_timeout
        )
        
        self.timeout_handler = TimeoutHandler(timeout_seconds=call_timeout)
        
        self.retry_mechanism = RetryMechanism(
            max_retries=max_retries,
            backoff_factor=backoff_factor
        )
    
    def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        通过保护机制调用函数
        执行顺序：熔断器 -> 重试 -> 超时控制
        
        Args:
            func: 要调用的函数
            *args, **kwargs: 函数参数
        
        Returns:
            函数返回值
        """
        # 包装超时控制
        def timeout_wrapped():
            return self.timeout_handler.call_with_timeout(func, *args, **kwargs)
        
        # 包装重试机制
        def retry_wrapped():
            return self.retry_mechanism.call_with_retry(timeout_wrapped)
        
        # 通过熔断器调用
        return self.circuit_breaker.call(retry_wrapped)
    
    def get_all_stats(self) -> Dict[str, Any]:
        """获取所有统计信息"""
        return {
            "circuit_breaker": self.circuit_breaker.get_stats(),
            "timeout_handler": self.timeout_handler.get_stats(),
            "retry_mechanism": self.retry_mechanism.get_stats()
        }
    
    def reset_all(self):
        """重置所有保护机制"""
        self.circuit_breaker.reset()
        # TimeoutHandler和RetryMechanism无状态，无需重置


# 装饰器版本
def with_api_protection(failure_threshold: int = 5,
                        circuit_timeout: int = 60,
                        call_timeout: int = 30,
                        max_retries: int = 3):
    """
    API保护装饰器
    
    使用示例：
    @with_api_protection(failure_threshold=3, call_timeout=10)
    def call_external_api():
        # API调用逻辑
        pass
    """
    protection = APIProtection(
        failure_threshold=failure_threshold,
        circuit_timeout=circuit_timeout,
        call_timeout=call_timeout,
        max_retries=max_retries
    )
    
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            return protection.call(func, *args, **kwargs)
        
        # 添加统计访问
        wrapper.get_stats = protection.get_all_stats
        wrapper.reset = protection.reset_all
        
        return wrapper
    
    return decorator


if __name__ == "__main__":
    # 测试代码
    print("=== API保护机制测试 ===")
    
    # 测试熔断器
    print("\n1. 熔断器测试")
    cb = CircuitBreaker(failure_threshold=3, timeout=5)
    
    def failing_func():
        raise ValueError("模拟失败")
    
    for i in range(5):
        try:
            cb.call(failing_func)
        except Exception as e:
            print(f"调用{i+1}: {type(e).__name__} - {e}")
            print(f"熔断器状态: {cb.state.value}")
    
    # 测试超时控制
    print("\n2. 超时控制测试")
    th = TimeoutHandler(timeout_seconds=2)
    
    def slow_func():
        time.sleep(5)
        return "完成"
    
    try:
        result = th.call_with_timeout(slow_func)
    except TimeoutError as e:
        print(f"超时捕获: {e}")
        print(f"统计: {th.get_stats()}")
    
    # 测试重试机制
    print("\n3. 重试机制测试")
    rm = RetryMechanism(max_retries=3, backoff_factor=0.5)
    
    attempt_count = [0]
    
    def eventually_succeed():
        attempt_count[0] += 1
        if attempt_count[0] < 3:
            raise ValueError(f"失败{attempt_count[0]}")
        return f"成功（第{attempt_count[0]}次尝试）"
    
    result = rm.call_with_retry(eventually_succeed)
    print(f"结果: {result}")
    print(f"统计: {rm.get_stats()}")
    
    print("\n=== 测试完成 ===")
