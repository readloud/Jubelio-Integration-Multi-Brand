# retry_handler.py
import time
import random
import asyncio
from functools import wraps
from typing import Callable, Any, Optional, List, Dict
from enum import Enum
from dataclasses import dataclass
from datetime import datetime
import threading
from logger import logger
from alerting import alert_manager

class RetryStrategy(Enum):
    """Retry strategy types"""
    EXPONENTIAL = "exponential"
    LINEAR = "linear"
    FIBONACCI = "fibonacci"
    RANDOM = "random"
    CUSTOM = "custom"

@dataclass
class RetryConfig:
    """Configuration for retry mechanism"""
    max_retries: int = 3
    base_delay: float = 1.0  # seconds
    max_delay: float = 60.0  # seconds
    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL
    backoff_multiplier: float = 2.0
    jitter: bool = True  # Add random jitter to avoid thundering herd
    retry_on_status_codes: List[int] = None  # HTTP status codes to retry
    retry_on_exceptions: List[Exception] = None
    max_total_time: Optional[float] = None  # Maximum total retry time
    
    def __post_init__(self):
        if self.retry_on_status_codes is None:
            self.retry_on_status_codes = [408, 429, 500, 502, 503, 504]
        if self.retry_on_exceptions is None:
            self.retry_on_exceptions = [
                ConnectionError,
                TimeoutError,
                ConnectionRefusedError,
                ConnectionResetError
            ]

class RetryContext:
    """Context manager for tracking retry attempts"""
    
    def __init__(self, operation_name: str, config: RetryConfig):
        self.operation_name = operation_name
        self.config = config
        self.attempts = 0
        self.start_time = None
        self.last_error = None
        self.retry_delays = []
    
    def __enter__(self):
        self.start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        duration = time.time() - self.start_time
        logger.info(f"RetryContext {self.operation_name}: {self.attempts} attempts, {duration:.2f}s")
    
    def should_retry(self, error: Exception = None, status_code: int = None) -> bool:
        """Determine if should retry based on error/status code"""
        
        # Check max attempts
        if self.attempts >= self.config.max_retries:
            return False
        
        # Check max total time
        if self.config.max_total_time:
            elapsed = time.time() - self.start_time
            if elapsed >= self.config.max_total_time:
                return False
        
        # Check error type
        if error:
            for retry_exception in self.config.retry_on_exceptions:
                if isinstance(error, retry_exception):
                    return True
        
        # Check status code
        if status_code and status_code in self.config.retry_on_status_codes:
            return True
        
        return False
    
    def calculate_next_delay(self) -> float:
        """Calculate next retry delay based on strategy"""
        
        if self.config.strategy == RetryStrategy.EXPONENTIAL:
            delay = self.config.base_delay * (self.config.backoff_multiplier ** self.attempts)
        
        elif self.config.strategy == RetryStrategy.LINEAR:
            delay = self.config.base_delay * (self.attempts + 1)
        
        elif self.config.strategy == RetryStrategy.FIBONACCI:
            fib = self._fibonacci(self.attempts + 2)
            delay = self.config.base_delay * fib
        
        elif self.config.strategy == RetryStrategy.RANDOM:
            delay = random.uniform(self.config.base_delay, self.config.max_delay)
        
        else:
            delay = self.config.base_delay
        
        # Apply jitter
        if self.config.jitter:
            jitter = random.uniform(0.8, 1.2)
            delay = delay * jitter
        
        # Cap at max delay
        delay = min(delay, self.config.max_delay)
        
        self.retry_delays.append(delay)
        return delay
    
    def _fibonacci(self, n: int) -> int:
        """Calculate fibonacci number"""
        if n <= 1:
            return n
        a, b = 0, 1
        for _ in range(n - 1):
            a, b = b, a + b
        return b

class AdvancedRetryHandler:
    """
    Advanced retry handler with multiple strategies and circuit breaker
    """
    
    def __init__(self):
        self.circuit_breakers = {}  # Track circuit breaker states
        self.failure_counts = {}
        self.last_failure_time = {}
    
    def retry(
        self, 
        config: RetryConfig = None,
        on_retry_callback: Callable = None,
        on_failure_callback: Callable = None
    ):
        """Decorator for retry logic"""
        
        if config is None:
            config = RetryConfig()
        
        def decorator(func: Callable) -> Callable:
            @wraps(func)
            def wrapper(*args, **kwargs):
                return self._execute_with_retry(
                    func, config, args, kwargs, 
                    on_retry_callback, on_failure_callback
                )
            
            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                return await self._execute_with_retry_async(
                    func, config, args, kwargs,
                    on_retry_callback, on_failure_callback
                )
            
            if asyncio.iscoroutinefunction(func):
                return async_wrapper
            return wrapper
        
        return decorator
    
    def _execute_with_retry(
        self,
        func: Callable,
        config: RetryConfig,
        args: tuple,
        kwargs: dict,
        on_retry_callback: Optional[Callable],
        on_failure_callback: Optional[Callable]
    ) -> Any:
        """Execute function with retry logic (sync)"""
        
        with RetryContext(func.__name__, config) as ctx:
            while True:
                try:
                    result = func(*args, **kwargs)
                    
                    # Reset failure count on success
                    self._record_success(func.__name__)
                    
                    return result
                
                except Exception as e:
                    ctx.last_error = e
                    ctx.attempts += 1
                    
                    status_code = getattr(e, 'status_code', None) if hasattr(e, 'status_code') else None
                    
                    if not ctx.should_retry(e, status_code):
                        logger.error(f"Final failure for {func.__name__} after {ctx.attempts} attempts: {e}")
                        
                        # Record failure
                        self._record_failure(func.__name__)
                        
                        # Call failure callback
                        if on_failure_callback:
                            on_failure_callback(func.__name__, ctx.attempts, e)
                        
                        # Send alert for persistent failures
                        if ctx.attempts >= config.max_retries:
                            self._send_failure_alert(func.__name__, ctx.attempts, e)
                        
                        raise e
                    
                    # Calculate next delay
                    delay = ctx.calculate_next_delay()
                    
                    logger.warning(
                        f"Retry {ctx.attempts}/{config.max_retries} for {func.__name__} "
                        f"after {delay:.2f}s (error: {str(e)[:100]})"
                    )
                    
                    # Call retry callback
                    if on_retry_callback:
                        on_retry_callback(func.__name__, ctx.attempts, delay, e)
                    
                    # Wait before retry
                    time.sleep(delay)
    
    async def _execute_with_retry_async(
        self,
        func: Callable,
        config: RetryConfig,
        args: tuple,
        kwargs: dict,
        on_retry_callback: Optional[Callable],
        on_failure_callback: Optional[Callable]
    ) -> Any:
        """Execute async function with retry logic"""
        
        with RetryContext(func.__name__, config) as ctx:
            while True:
                try:
                    result = await func(*args, **kwargs)
                    self._record_success(func.__name__)
                    return result
                
                except Exception as e:
                    ctx.last_error = e
                    ctx.attempts += 1
                    
                    status_code = getattr(e, 'status_code', None) if hasattr(e, 'status_code') else None
                    
                    if not ctx.should_retry(e, status_code):
                        logger.error(f"Final failure for {func.__name__} after {ctx.attempts} attempts: {e}")
                        self._record_failure(func.__name__)
                        
                        if on_failure_callback:
                            on_failure_callback(func.__name__, ctx.attempts, e)
                        
                        if ctx.attempts >= config.max_retries:
                            self._send_failure_alert(func.__name__, ctx.attempts, e)
                        
                        raise e
                    
                    delay = ctx.calculate_next_delay()
                    
                    logger.warning(
                        f"Retry {ctx.attempts}/{config.max_retries} for {func.__name__} "
                        f"after {delay:.2f}s"
                    )
                    
                    if on_retry_callback:
                        on_retry_callback(func.__name__, ctx.attempts, delay, e)
                    
                    await asyncio.sleep(delay)
    
    def _record_success(self, operation: str):
        """Record successful operation"""
        if operation in self.failure_counts:
            # Reset failure count after success
            self.failure_counts[operation] = 0
    
    def _record_failure(self, operation: str):
        """Record failed operation (for circuit breaker)"""
        current_time = time.time()
        
        if operation not in self.failure_counts:
            self.failure_counts[operation] = 0
            self.last_failure_time[operation] = current_time
        
        self.failure_counts[operation] += 1
        self.last_failure_time[operation] = current_time
        
        # Check if circuit breaker should open
        if self.failure_counts[operation] >= 5:  # 5 failures in a row
            self._open_circuit_breaker(operation)
    
    def _open_circuit_breaker(self, operation: str):
        """Open circuit breaker for operation"""
        self.circuit_breakers[operation] = {
            "state": "open",
            "opened_at": time.time(),
            "reset_at": time.time() + 60  # Reset after 60 seconds
        }
        
        alert_manager.send_slack(
            f"🔌 *Circuit Breaker Opened*\n"
            f"Operation: {operation}\n"
            f"Reason: {self.failure_counts[operation]} consecutive failures\n"
            f"Will reset at: {datetime.fromtimestamp(time.time() + 60).strftime('%H:%M:%S')}",
            color="warning"
        )
    
    def is_circuit_open(self, operation: str) -> bool:
        """Check if circuit breaker is open for operation"""
        if operation not in self.circuit_breakers:
            return False
        
        breaker = self.circuit_breakers[operation]
        
        if breaker["state"] == "open":
            # Check if it's time to reset
            if time.time() >= breaker["reset_at"]:
                # Try half-open state
                breaker["state"] = "half_open"
                logger.info(f"Circuit breaker for {operation} is now half-open")
                return False
            return True
        
        return False
    
    def _send_failure_alert(self, operation: str, attempts: int, error: Exception):
        """Send alert for persistent failures"""
        
        # Check if circuit breaker is about to open
        failure_count = self.failure_counts.get(operation, 0)
        
        alert_manager.send_slack(
            f"❌ *Persistent Failure Detected*\n"
            f"Operation: {operation}\n"
            f"Attempts: {attempts}\n"
            f"Consecutive failures: {failure_count}\n"
            f"Error: {str(error)[:200]}\n"
            f"Action: Manual intervention may be required",
            color="danger"
        )
        
        alert_manager.send_email(
            f"[URGENT] Persistent failure: {operation}",
            f"Operation {operation} failed after {attempts} attempts.\n\n"
            f"Error: {error}\n\n"
            f"Please check the system and retry manually if needed."
        )

class RetryableAPIClient:
    """
    API Client with built-in retry and SLA monitoring
    """
    
    def __init__(self, base_url: str, default_retry_config: RetryConfig = None):
        self.base_url = base_url
        self.retry_handler = AdvancedRetryHandler()
        self.default_config = default_retry_config or RetryConfig(
            max_retries=3,
            base_delay=1.0,
            max_delay=30.0,
            strategy=RetryStrategy.EXPONENTIAL,
            jitter=True
        )
        self.sla_monitor = get_sla_monitor()
    
    @monitor_sla("api.request")
    def request(self, method: str, endpoint: str, **kwargs) -> Any:
        """Make API request with retry and SLA monitoring"""
        
        @self.retry_handler.retry(config=self.default_config)
        def _make_request():
            import requests
            
            url = f"{self.base_url}{endpoint}"
            
            response = requests.request(method, url, timeout=30, **kwargs)
            
            # Check if status code requires retry
            if response.status_code >= 500 or response.status_code in [408, 429]:
                raise Exception(f"HTTP {response.status_code}: {response.text[:100]}")
            
            response.raise_for_status()
            return response.json()
        
        return _make_request()
    
    async def request_async(self, method: str, endpoint: str, **kwargs) -> Any:
        """Async API request with retry"""
        
        @self.retry_handler.retry(config=self.default_config)
        async def _make_request():
            import aiohttp
            
            url = f"{self.base_url}{endpoint}"
            
            async with aiohttp.ClientSession() as session:
                async with session.request(method, url, timeout=30, **kwargs) as response:
                    if response.status >= 500 or response.status in [408, 429]:
                        text = await response.text()
                        raise Exception(f"HTTP {response.status}: {text[:100]}")
                    
                    response.raise_for_status()
                    return await response.json()
        
        return await _make_request()

# Example usage with decorator
retry_handler = AdvancedRetryHandler()

@retry_handler.retry(
    config=RetryConfig(
        max_retries=5,
        base_delay=0.5,
        max_delay=30,
        strategy=RetryStrategy.EXPONENTIAL,
        jitter=True,
        max_total_time=120
    )
)
def fetch_jubelio_orders(brand_id: str, date: str):
    """Example: Fetch orders with retry"""
    import requests
    
    response = requests.get(
        f"https://api.jubelio.com/v1/orders",
        params={"brand_id": brand_id, "date": date},
        timeout=30
    )
    
    if response.status_code == 429:  # Rate limited
        raise Exception("Rate limited")
    
    response.raise_for_status()
    return response.json()