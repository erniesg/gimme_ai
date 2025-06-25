"""Tests for connection manager and circuit breaker functionality."""

import pytest
import asyncio
import time
from unittest.mock import AsyncMock, patch
import httpx

from gimme_ai.http.connection_manager import (
    CircuitBreaker, CircuitBreakerConfig, CircuitState,
    ConnectionPool, AsyncResourceManager, 
    get_global_resource_manager, cleanup_global_resources
)


class TestCircuitBreaker:
    """Test cases for CircuitBreaker class."""
    
    def test_circuit_breaker_config_defaults(self):
        """Test circuit breaker configuration defaults."""
        config = CircuitBreakerConfig()
        
        assert config.failure_threshold == 5
        assert config.recovery_timeout == 60.0
        assert config.success_threshold == 3
        assert config.timeout == 30.0
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_normal_operation(self):
        """Test circuit breaker in normal (CLOSED) state."""
        config = CircuitBreakerConfig(failure_threshold=2)
        breaker = CircuitBreaker(config)
        
        # Mock successful function
        async def success_func():
            return "success"
        
        # Should work normally
        result = await breaker.call(success_func)
        assert result == "success"
        assert breaker.state == CircuitState.CLOSED
        assert breaker.failure_count == 0
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_opens_on_failures(self):
        """Test circuit breaker opens after failure threshold."""
        config = CircuitBreakerConfig(failure_threshold=2, recovery_timeout=0.1)
        breaker = CircuitBreaker(config)
        
        # Mock failing function
        async def fail_func():
            raise Exception("Test failure")
        
        # First failure
        with pytest.raises(Exception, match="Test failure"):
            await breaker.call(fail_func)
        
        assert breaker.state == CircuitState.CLOSED
        assert breaker.failure_count == 1
        
        # Second failure - should open circuit
        with pytest.raises(Exception, match="Test failure"):
            await breaker.call(fail_func)
        
        assert breaker.state == CircuitState.OPEN
        assert breaker.failure_count == 2
        
        # Third call should be rejected immediately
        with pytest.raises(Exception, match="Circuit breaker OPEN"):
            await breaker.call(fail_func)
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_half_open_recovery(self):
        """Test circuit breaker recovery through HALF_OPEN state."""
        config = CircuitBreakerConfig(
            failure_threshold=1, 
            recovery_timeout=0.01,  # Very short for testing
            success_threshold=2
        )
        breaker = CircuitBreaker(config)
        
        # Fail to open circuit
        async def fail_func():
            raise Exception("Test failure")
        
        with pytest.raises(Exception):
            await breaker.call(fail_func)
        
        assert breaker.state == CircuitState.OPEN
        
        # Wait for recovery timeout
        await asyncio.sleep(0.02)
        
        # Mock successful function
        async def success_func():
            return "success"
        
        # First success should put in HALF_OPEN
        result = await breaker.call(success_func)
        assert result == "success"
        assert breaker.state == CircuitState.HALF_OPEN
        assert breaker.success_count == 1
        
        # Second success should close circuit
        result = await breaker.call(success_func)
        assert result == "success"
        assert breaker.state == CircuitState.CLOSED
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_timeout(self):
        """Test circuit breaker request timeout."""
        config = CircuitBreakerConfig(timeout=0.01)  # Very short timeout
        breaker = CircuitBreaker(config)
        
        # Mock slow function
        async def slow_func():
            await asyncio.sleep(0.1)  # Longer than timeout
            return "should not reach here"
        
        with pytest.raises(asyncio.TimeoutError):
            await breaker.call(slow_func)
        
        assert breaker.failure_count == 1


class TestConnectionPool:
    """Test cases for ConnectionPool class."""
    
    @pytest.mark.asyncio
    async def test_connection_pool_creates_clients(self):
        """Test connection pool creates and reuses HTTP clients."""
        async with ConnectionPool() as pool:
            # Get client for first URL
            client1 = await pool.get_client("https://api.example.com")
            assert isinstance(client1, httpx.AsyncClient)
            
            # Get client for same URL - should reuse
            client2 = await pool.get_client("https://api.example.com")
            assert client1 is client2
            
            # Get client for different URL - should create new
            client3 = await pool.get_client("https://api.different.com")
            assert client3 is not client1
    
    @pytest.mark.asyncio
    async def test_connection_pool_circuit_breakers(self):
        """Test connection pool creates circuit breakers per service."""
        async with ConnectionPool() as pool:
            # Get circuit breaker for service
            breaker1 = pool.get_circuit_breaker("service1")
            assert isinstance(breaker1, CircuitBreaker)
            
            # Get same service - should reuse
            breaker2 = pool.get_circuit_breaker("service1")
            assert breaker1 is breaker2
            
            # Get different service - should create new
            breaker3 = pool.get_circuit_breaker("service2")
            assert breaker3 is not breaker1
    
    @pytest.mark.asyncio
    async def test_connection_pool_request_with_mock(self):
        """Test connection pool request method with mocked HTTP."""
        async with ConnectionPool() as pool:
            with patch('httpx.AsyncClient.request') as mock_request:
                mock_response = AsyncMock()
                mock_response.status_code = 200
                mock_response.json.return_value = {"result": "success"}
                mock_request.return_value = mock_response
                
                response = await pool.request(
                    "GET", 
                    "https://api.example.com/test",
                    service_name="test_service"
                )
                
                assert response == mock_response
                mock_request.assert_called_once()


class TestAsyncResourceManager:
    """Test cases for AsyncResourceManager class."""
    
    @pytest.mark.asyncio
    async def test_resource_manager_basic_usage(self):
        """Test basic resource manager functionality."""
        async with AsyncResourceManager() as manager:
            # Get connection pool
            pool = manager.get_connection_pool()
            assert isinstance(pool, ConnectionPool)
            
            # Getting again should return same instance
            pool2 = manager.get_connection_pool()
            assert pool is pool2
    
    @pytest.mark.asyncio
    async def test_resource_manager_task_tracking(self):
        """Test resource manager tracks and cleans up tasks."""
        manager = AsyncResourceManager()
        
        # Create a task
        async def dummy_task():
            await asyncio.sleep(1)  # Long enough to be cancelled
        
        task = asyncio.create_task(dummy_task())
        manager.add_task(task)
        
        # Cleanup should cancel the task
        await manager.cleanup()
        
        assert task.cancelled()
    
    @pytest.mark.asyncio 
    async def test_resource_manager_cleanup_on_exit(self):
        """Test resource manager cleanup on context exit."""
        manager = AsyncResourceManager()
        
        # Add some resources
        pool = manager.get_connection_pool()
        
        # Create a task
        async def dummy_task():
            await asyncio.sleep(1)
        
        task = asyncio.create_task(dummy_task())
        manager.add_task(task)
        
        # Use context manager
        async with manager:
            pass  # Context exit should trigger cleanup
        
        # Task should be cancelled and resources cleared
        assert task.cancelled()
        assert len(manager.resources) == 0
        assert len(manager._cleanup_tasks) == 0


class TestGlobalResourceManager:
    """Test cases for global resource manager."""
    
    @pytest.mark.asyncio
    async def test_global_resource_manager_singleton(self):
        """Test global resource manager is singleton."""
        manager1 = get_global_resource_manager()
        manager2 = get_global_resource_manager()
        
        assert manager1 is manager2
    
    @pytest.mark.asyncio
    async def test_global_cleanup(self):
        """Test global resource cleanup."""
        # Get global manager and use it
        manager = get_global_resource_manager()
        pool = manager.get_connection_pool()
        
        # Create a task
        async def dummy_task():
            await asyncio.sleep(1)
        
        task = asyncio.create_task(dummy_task())
        manager.add_task(task)
        
        # Cleanup should work
        await cleanup_global_resources()
        
        assert task.cancelled()
        
        # Getting manager again should create new instance
        new_manager = get_global_resource_manager()
        assert new_manager is not manager


class TestIntegration:
    """Integration tests for connection manager components."""
    
    @pytest.mark.asyncio
    async def test_connection_pool_with_circuit_breaker_failure(self):
        """Test connection pool with circuit breaker under failure conditions."""
        async with ConnectionPool() as pool:
            with patch('httpx.AsyncClient.request') as mock_request:
                # Mock request to always fail
                mock_request.side_effect = Exception("Network error")
                
                # First few requests should fail but circuit stays closed
                for i in range(4):
                    with pytest.raises(Exception, match="Network error"):
                        await pool.request(
                            "GET",
                            "https://api.example.com/test", 
                            service_name="failing_service"
                        )
                
                # Fifth request should open circuit
                with pytest.raises(Exception, match="Network error"):
                    await pool.request(
                        "GET",
                        "https://api.example.com/test",
                        service_name="failing_service" 
                    )
                
                # Sixth request should be rejected by circuit breaker
                with pytest.raises(Exception, match="Circuit breaker OPEN"):
                    await pool.request(
                        "GET", 
                        "https://api.example.com/test",
                        service_name="failing_service"
                    )