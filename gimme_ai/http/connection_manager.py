"""Connection manager with pooling and circuit breaker for async HTTP operations."""

import asyncio
import time
import logging
from typing import Dict, Optional, Any, List
from dataclasses import dataclass
from enum import Enum
import httpx
from ..utils.security import get_secure_logger

logger = get_secure_logger(__name__)


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"       # Normal operation
    OPEN = "open"          # Failing, reject requests
    HALF_OPEN = "half_open" # Testing if service recovered


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker."""
    failure_threshold: int = 5          # Failures before opening
    recovery_timeout: float = 60.0      # Seconds to wait before trying again
    success_threshold: int = 3          # Successes needed to close circuit
    timeout: float = 30.0               # Request timeout


class CircuitBreaker:
    """Circuit breaker implementation for HTTP requests."""
    
    def __init__(self, config: CircuitBreakerConfig):
        self.config = config
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = 0.0
        self.last_request_time = 0.0
    
    async def call(self, func, *args, **kwargs):
        """Execute function with circuit breaker protection."""
        current_time = time.time()
        
        # Check if circuit should transition from OPEN to HALF_OPEN
        if (self.state == CircuitState.OPEN and 
            current_time - self.last_failure_time >= self.config.recovery_timeout):
            self.state = CircuitState.HALF_OPEN
            self.success_count = 0
            logger.info("Circuit breaker transitioning to HALF_OPEN")
        
        # Reject requests if circuit is OPEN
        if self.state == CircuitState.OPEN:
            raise Exception(f"Circuit breaker OPEN - service unavailable")
        
        try:
            # Execute the function with timeout
            result = await asyncio.wait_for(
                func(*args, **kwargs), 
                timeout=self.config.timeout
            )
            
            # Success - handle state transitions
            if self.state == CircuitState.HALF_OPEN:
                self.success_count += 1
                if self.success_count >= self.config.success_threshold:
                    self.state = CircuitState.CLOSED
                    self.failure_count = 0
                    logger.info("Circuit breaker CLOSED - service recovered")
            else:
                self.failure_count = max(0, self.failure_count - 1)
            
            self.last_request_time = current_time
            return result
            
        except Exception as e:
            # Failure - increment counter and potentially open circuit
            self.failure_count += 1
            self.last_failure_time = current_time
            
            if self.failure_count >= self.config.failure_threshold:
                if self.state != CircuitState.OPEN:
                    self.state = CircuitState.OPEN
                    logger.warning(f"Circuit breaker OPEN after {self.failure_count} failures")
            
            raise e


class ConnectionPool:
    """HTTP connection pool manager."""
    
    def __init__(self, 
                 max_connections: int = 100,
                 max_keepalive_connections: int = 20,
                 keepalive_expiry: float = 5.0):
        """
        Initialize connection pool.
        
        Args:
            max_connections: Maximum total connections
            max_keepalive_connections: Maximum persistent connections
            keepalive_expiry: Seconds to keep connections alive
        """
        self.limits = httpx.Limits(
            max_connections=max_connections,
            max_keepalive_connections=max_keepalive_connections,
            keepalive_expiry=keepalive_expiry
        )
        self.clients: Dict[str, httpx.AsyncClient] = {}
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}
        self._lock = asyncio.Lock()
    
    async def get_client(self, base_url: str, timeout: float = 30.0) -> httpx.AsyncClient:
        """Get or create HTTP client for base URL."""
        async with self._lock:
            if base_url not in self.clients:
                # Create new client with connection pooling
                client = httpx.AsyncClient(
                    base_url=base_url,
                    limits=self.limits,
                    timeout=timeout,
                    headers={'User-Agent': 'gimme-ai-workflow/1.0'}
                )
                self.clients[base_url] = client
                logger.debug(f"Created new HTTP client for {base_url}")
            
            return self.clients[base_url]
    
    def get_circuit_breaker(self, service_name: str) -> CircuitBreaker:
        """Get or create circuit breaker for service."""
        if service_name not in self.circuit_breakers:
            config = CircuitBreakerConfig()
            self.circuit_breakers[service_name] = CircuitBreaker(config)
            logger.debug(f"Created circuit breaker for {service_name}")
        
        return self.circuit_breakers[service_name]
    
    async def request(self, 
                     method: str,
                     url: str, 
                     service_name: Optional[str] = None,
                     **kwargs) -> httpx.Response:
        """Make HTTP request with circuit breaker protection."""
        # Extract base URL for client pooling
        if url.startswith('http'):
            from urllib.parse import urlparse
            parsed = urlparse(url)
            base_url = f"{parsed.scheme}://{parsed.netloc}"
            path = url[len(base_url):]
        else:
            base_url = ""
            path = url
        
        # Get pooled client
        client = await self.get_client(base_url)
        
        # Use circuit breaker if service name provided
        if service_name:
            circuit_breaker = self.get_circuit_breaker(service_name)
            return await circuit_breaker.call(
                client.request, method, path, **kwargs
            )
        else:
            return await client.request(method, path, **kwargs)
    
    async def close_all(self):
        """Close all HTTP clients and clean up resources."""
        async with self._lock:
            for base_url, client in self.clients.items():
                try:
                    await client.aclose()
                    logger.debug(f"Closed HTTP client for {base_url}")
                except Exception as e:
                    logger.warning(f"Error closing client for {base_url}: {e}")
            
            self.clients.clear()
            self.circuit_breakers.clear()
    
    async def __aenter__(self):
        """Async context manager entry."""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close_all()


class AsyncResourceManager:
    """Manager for async resources with proper cleanup."""
    
    def __init__(self):
        self.resources: List[Any] = []
        self.connection_pool: Optional[ConnectionPool] = None
        self._cleanup_tasks: List[asyncio.Task] = []
    
    def get_connection_pool(self) -> ConnectionPool:
        """Get or create connection pool."""
        if self.connection_pool is None:
            self.connection_pool = ConnectionPool()
            self.resources.append(self.connection_pool)
        return self.connection_pool
    
    def add_resource(self, resource: Any):
        """Add resource for cleanup tracking."""
        self.resources.append(resource)
    
    def add_task(self, task: asyncio.Task):
        """Add task for cleanup tracking."""
        self._cleanup_tasks.append(task)
    
    async def cleanup(self):
        """Clean up all managed resources."""
        # Cancel pending tasks
        for task in self._cleanup_tasks:
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
                except Exception as e:
                    logger.warning(f"Error cancelling task: {e}")
        
        # Close resources
        for resource in self.resources:
            try:
                if hasattr(resource, 'close_all'):
                    await resource.close_all()
                elif hasattr(resource, 'aclose'):
                    await resource.aclose()
                elif hasattr(resource, 'close'):
                    resource.close()
            except Exception as e:
                logger.warning(f"Error closing resource {type(resource).__name__}: {e}")
        
        self.resources.clear()
        self._cleanup_tasks.clear()
        self.connection_pool = None
    
    async def __aenter__(self):
        """Async context manager entry."""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.cleanup()


# Global resource manager instance
_global_resource_manager: Optional[AsyncResourceManager] = None


def get_global_resource_manager() -> AsyncResourceManager:
    """Get or create global resource manager."""
    global _global_resource_manager
    if _global_resource_manager is None:
        _global_resource_manager = AsyncResourceManager()
    return _global_resource_manager


async def cleanup_global_resources():
    """Clean up global resources."""
    global _global_resource_manager
    if _global_resource_manager is not None:
        await _global_resource_manager.cleanup()
        _global_resource_manager = None