#!/usr/bin/env python3
"""
Comprehensive error handling and resilience tests.
Tests various failure scenarios and recovery mechanisms.
"""

import pytest
import asyncio
import time
import aiohttp
from unittest.mock import patch, Mock

from gimme_ai.workflows.execution_engine import WorkflowExecutionEngine
from gimme_ai.http.workflow_client import WorkflowHTTPClient
from gimme_ai.config.workflow import WorkflowConfig, StepConfig, AuthConfig, RetryConfig
from tests.fixtures.mock_api_server import MockAPIServer, MockEndpoint

class TestRetryMechanisms:
    """Test retry logic and backoff strategies."""
    
    @pytest.fixture
    def mock_server(self):
        """Mock server with failing endpoints."""
        server = MockAPIServer(port=8900)
        
        # Endpoint that fails 3 times then succeeds
        server.add_endpoint(MockEndpoint(
            path="/api/fail-3-times",
            method="POST",
            response_data={"status": "success", "attempt": 4},
            failure_count=3
        ))
        
        # Endpoint with 50% failure rate
        server.add_endpoint(MockEndpoint(
            path="/api/flaky",
            method="GET", 
            response_data={"data": "success"},
            failure_rate=0.5
        ))
        
        # Slow endpoint for timeout testing
        server.add_endpoint(MockEndpoint(
            path="/api/slow",
            method="GET",
            response_data={"message": "finally done"},
            delay_seconds=10.0
        ))
        
        # Always failing endpoint
        server.add_endpoint(MockEndpoint(
            path="/api/always-fails",
            method="POST",
            response_data={},
            failure_rate=1.0
        ))
        
        server.start(background=True)
        yield server
        server.stop()
    
    @pytest.fixture
    def workflow_engine(self, mock_server):
        """Create workflow engine with mock server."""
        client = WorkflowHTTPClient(base_url=mock_server.base_url)
        return WorkflowExecutionEngine(http_client=client)
    
    @pytest.mark.asyncio
    async def test_exponential_backoff_retry(self, workflow_engine):
        """Test exponential backoff retry strategy."""
        workflow = WorkflowConfig(
            name="exponential_backoff_test",
            api_base=workflow_engine.http_client.base_url,
            steps=[
                StepConfig(
                    name="retry_step",
                    endpoint="/api/fail-3-times",
                    method="POST",
                    payload={"test": "data"},
                    retry=RetryConfig(
                        limit=5,
                        delay="0.5s", 
                        backoff="exponential"
                    )
                )
            ]
        )
        
        start_time = time.time()
        result = await workflow_engine.execute_workflow(workflow)
        execution_time = time.time() - start_time
        
        assert result.success is True
        step_result = result.step_results["retry_step"]
        assert step_result.success is True
        assert step_result.retry_count == 3  # Failed 3 times, succeeded on 4th
        
        # Exponential backoff: 0.5s + 1s + 2s = 3.5s minimum delay
        # Plus API delays and processing time
        assert execution_time >= 3.0, f"Expected >= 3s delay, got {execution_time:.2f}s"
        
        print(f"✅ Exponential backoff completed in {execution_time:.2f}s with {step_result.retry_count} retries")
    
    @pytest.mark.asyncio
    async def test_linear_backoff_retry(self, workflow_engine):
        """Test linear backoff retry strategy."""
        workflow = WorkflowConfig(
            name="linear_backoff_test",
            api_base=workflow_engine.http_client.base_url,
            steps=[
                StepConfig(
                    name="retry_step",
                    endpoint="/api/fail-3-times",
                    method="POST",
                    retry=RetryConfig(
                        limit=5,
                        delay="0.5s",
                        backoff="linear"
                    )
                )
            ]
        )
        
        start_time = time.time()
        result = await workflow_engine.execute_workflow(workflow)
        execution_time = time.time() - start_time
        
        assert result.success is True
        step_result = result.step_results["retry_step"]
        assert step_result.retry_count == 3
        
        # Linear backoff: 0.5s + 1s + 1.5s = 3s minimum delay
        assert execution_time >= 2.5, f"Expected >= 2.5s delay, got {execution_time:.2f}s"
        
        print(f"✅ Linear backoff completed in {execution_time:.2f}s with {step_result.retry_count} retries")
    
    @pytest.mark.asyncio
    async def test_constant_backoff_retry(self, workflow_engine):
        """Test constant backoff retry strategy."""
        workflow = WorkflowConfig(
            name="constant_backoff_test",
            api_base=workflow_engine.http_client.base_url,
            steps=[
                StepConfig(
                    name="retry_step",
                    endpoint="/api/fail-3-times",
                    method="POST",
                    retry=RetryConfig(
                        limit=5,
                        delay="0.5s",
                        backoff="constant"
                    )
                )
            ]
        )
        
        start_time = time.time()
        result = await workflow_engine.execute_workflow(workflow)
        execution_time = time.time() - start_time
        
        assert result.success is True
        step_result = result.step_results["retry_step"]
        assert step_result.retry_count == 3
        
        # Constant backoff: 0.5s + 0.5s + 0.5s = 1.5s minimum delay
        assert execution_time >= 1.0, f"Expected >= 1s delay, got {execution_time:.2f}s"
        
        print(f"✅ Constant backoff completed in {execution_time:.2f}s with {step_result.retry_count} retries")
    
    @pytest.mark.asyncio
    async def test_retry_limit_exceeded(self, workflow_engine):
        """Test behavior when retry limit is exceeded."""
        workflow = WorkflowConfig(
            name="retry_limit_test",
            api_base=workflow_engine.http_client.base_url,
            steps=[
                StepConfig(
                    name="failing_step",
                    endpoint="/api/always-fails",
                    method="POST",
                    retry=RetryConfig(
                        limit=2,  # Only 2 retries
                        delay="1s",
                        backoff="constant"
                    )
                )
            ]
        )
        
        result = await workflow_engine.execute_workflow(workflow)
        
        # Workflow should fail when retry limit exceeded
        assert result.success is False
        step_result = result.step_results["failing_step"]
        assert step_result.success is False
        assert step_result.retry_count == 2  # Hit retry limit
        assert step_result.error is not None
        
        print(f"✅ Retry limit properly enforced after {step_result.retry_count} attempts")


class TestTimeoutHandling:
    """Test timeout scenarios and handling."""
    
    @pytest.fixture
    def mock_server(self):
        """Mock server with slow endpoints."""
        server = MockAPIServer(port=8901)
        
        # Very slow endpoint
        server.add_endpoint(MockEndpoint(
            path="/api/very-slow",
            method="GET",
            response_data={"message": "slow response"},
            delay_seconds=10.0
        ))
        
        # Moderately slow endpoint
        server.add_endpoint(MockEndpoint(
            path="/api/moderate-slow",
            method="GET",
            response_data={"message": "moderate response"},
            delay_seconds=2.0
        ))
        
        server.start(background=True)
        yield server
        server.stop()
    
    @pytest.fixture
    def workflow_engine(self, mock_server):
        """Create workflow engine with mock server."""
        client = WorkflowHTTPClient(base_url=mock_server.base_url)
        return WorkflowExecutionEngine(http_client=client)
    
    @pytest.mark.asyncio
    async def test_step_timeout(self, workflow_engine):
        """Test individual step timeout handling."""
        workflow = WorkflowConfig(
            name="timeout_test",
            api_base=workflow_engine.http_client.base_url,
            steps=[
                StepConfig(
                    name="slow_step",
                    endpoint="/api/very-slow",
                    method="GET",
                    timeout="2s"  # Timeout before response
                )
            ]
        )
        
        start_time = time.time()
        result = await workflow_engine.execute_workflow(workflow)
        execution_time = time.time() - start_time
        
        # Should timeout and fail
        assert result.success is False
        step_result = result.step_results["slow_step"]
        assert step_result.success is False
        assert "timeout" in step_result.error.lower()
        
        # Should complete quickly due to timeout
        assert execution_time < 5.0, f"Timeout should prevent long execution, got {execution_time:.2f}s"
        
        print(f"✅ Step timeout properly enforced after {execution_time:.2f}s")
    
    @pytest.mark.asyncio
    async def test_timeout_with_retry(self, workflow_engine):
        """Test timeout behavior with retry logic."""
        workflow = WorkflowConfig(
            name="timeout_retry_test",
            api_base=workflow_engine.http_client.base_url,
            steps=[
                StepConfig(
                    name="slow_step",
                    endpoint="/api/moderate-slow",  # 2s delay
                    method="GET",
                    timeout="1s",  # Timeout before response
                    retry=RetryConfig(
                        limit=3,
                        delay="1s",
                        backoff="constant"
                    )
                )
            ]
        )
        
        start_time = time.time()
        result = await workflow_engine.execute_workflow(workflow)
        execution_time = time.time() - start_time
        
        # Should fail after retries
        assert result.success is False
        step_result = result.step_results["slow_step"]
        assert step_result.success is False
        assert step_result.retry_count == 3  # All retries attempted
        
        print(f"✅ Timeout with retry completed in {execution_time:.2f}s after {step_result.retry_count} attempts")


class TestNetworkErrorHandling:
    """Test handling of various network errors."""
    
    @pytest.fixture
    def workflow_engine(self):
        """Create workflow engine with unreachable base URL."""
        client = WorkflowHTTPClient(base_url="http://localhost:19999")  # Unreachable port
        return WorkflowExecutionEngine(http_client=client)
    
    @pytest.mark.asyncio
    async def test_connection_refused(self, workflow_engine):
        """Test handling of connection refused errors."""
        workflow = WorkflowConfig(
            name="connection_error_test",
            api_base="http://localhost:19999",  # Unreachable
            steps=[
                StepConfig(
                    name="unreachable_step",
                    endpoint="/api/test",
                    method="GET",
                    retry=RetryConfig(
                        limit=2,
                        delay="1s",
                        backoff="constant"
                    )
                )
            ]
        )
        
        result = await workflow_engine.execute_workflow(workflow)
        
        assert result.success is False
        step_result = result.step_results["unreachable_step"]
        assert step_result.success is False
        assert step_result.retry_count == 2
        assert "connection" in step_result.error.lower() or "refused" in step_result.error.lower()
        
        print("✅ Connection refused error properly handled")
    
    @pytest.mark.asyncio
    async def test_dns_resolution_failure(self):
        """Test handling of DNS resolution failures."""
        client = WorkflowHTTPClient(base_url="http://nonexistent-domain-12345.com")
        engine = WorkflowExecutionEngine(http_client=client)
        
        workflow = WorkflowConfig(
            name="dns_error_test",
            api_base="http://nonexistent-domain-12345.com",
            steps=[
                StepConfig(
                    name="dns_fail_step",
                    endpoint="/api/test",
                    method="GET",
                    retry=RetryConfig(limit=1, delay="1s")
                )
            ]
        )
        
        result = await engine.execute_workflow(workflow)
        
        assert result.success is False
        step_result = result.step_results["dns_fail_step"]
        assert step_result.success is False
        assert step_result.error is not None
        
        print("✅ DNS resolution failure properly handled")


class TestWorkflowLevelErrorHandling:
    """Test error handling at the workflow level."""
    
    @pytest.fixture
    def mock_server(self):
        """Mock server with mixed success/failure endpoints."""
        server = MockAPIServer(port=8902)
        
        server.add_endpoint(MockEndpoint(
            path="/api/success",
            method="GET",
            response_data={"status": "ok"}
        ))
        
        server.add_endpoint(MockEndpoint(
            path="/api/failure",
            method="GET",
            response_data={},
            failure_rate=1.0
        ))
        
        server.start(background=True)
        yield server
        server.stop()
    
    @pytest.fixture
    def workflow_engine(self, mock_server):
        """Create workflow engine with mock server."""
        client = WorkflowHTTPClient(base_url=mock_server.base_url)
        return WorkflowExecutionEngine(http_client=client)
    
    @pytest.mark.asyncio
    async def test_continue_on_error_workflow(self, workflow_engine):
        """Test workflow continues when steps are marked continue_on_error."""
        workflow = WorkflowConfig(
            name="continue_on_error_test",
            api_base=workflow_engine.http_client.base_url,
            steps=[
                StepConfig(
                    name="success_step1",
                    endpoint="/api/success",
                    method="GET"
                ),
                StepConfig(
                    name="failing_step",
                    endpoint="/api/failure",
                    method="GET",
                    continue_on_error=True,  # Continue despite failure
                    depends_on=["success_step1"]
                ),
                StepConfig(
                    name="success_step2",
                    endpoint="/api/success",
                    method="GET",
                    depends_on=["failing_step"]
                )
            ]
        )
        
        result = await workflow_engine.execute_workflow(workflow)
        
        # Overall workflow should succeed due to continue_on_error
        assert result.success is True
        assert len(result.step_results) == 3
        
        success1_result = result.step_results["success_step1"]
        failing_result = result.step_results["failing_step"]
        success2_result = result.step_results["success_step2"]
        
        assert success1_result.success is True
        assert failing_result.success is False  # This step failed
        assert success2_result.success is True  # But workflow continued
        
        print("✅ Continue on error behavior works correctly")
    
    @pytest.mark.asyncio
    async def test_stop_on_error_workflow(self, workflow_engine):
        """Test workflow stops when step fails without continue_on_error."""
        workflow = WorkflowConfig(
            name="stop_on_error_test",
            api_base=workflow_engine.http_client.base_url,
            steps=[
                StepConfig(
                    name="success_step",
                    endpoint="/api/success",
                    method="GET"
                ),
                StepConfig(
                    name="failing_step",
                    endpoint="/api/failure",
                    method="GET",
                    continue_on_error=False,  # Stop on failure
                    depends_on=["success_step"]
                ),
                StepConfig(
                    name="never_executed",
                    endpoint="/api/success",
                    method="GET",
                    depends_on=["failing_step"]
                )
            ]
        )
        
        result = await workflow_engine.execute_workflow(workflow)
        
        # Workflow should fail and stop
        assert result.success is False
        
        # Only first two steps should have been attempted
        assert len(result.step_results) == 2
        assert "success_step" in result.step_results
        assert "failing_step" in result.step_results
        assert "never_executed" not in result.step_results
        
        success_result = result.step_results["success_step"]
        failing_result = result.step_results["failing_step"]
        
        assert success_result.success is True
        assert failing_result.success is False
        
        print("✅ Stop on error behavior works correctly")
    
    @pytest.mark.asyncio
    async def test_partial_failure_in_parallel_group(self, workflow_engine):
        """Test handling of partial failures in parallel execution groups."""
        workflow = WorkflowConfig(
            name="partial_parallel_failure_test",
            api_base=workflow_engine.http_client.base_url,
            steps=[
                StepConfig(
                    name="parallel_success1",
                    endpoint="/api/success",
                    method="GET",
                    parallel_group="parallel_group"
                ),
                StepConfig(
                    name="parallel_failure",
                    endpoint="/api/failure",
                    method="GET",
                    parallel_group="parallel_group",
                    continue_on_error=True  # Allow partial failure
                ),
                StepConfig(
                    name="parallel_success2",
                    endpoint="/api/success",
                    method="GET",
                    parallel_group="parallel_group"
                ),
                StepConfig(
                    name="after_parallel",
                    endpoint="/api/success",
                    method="GET",
                    depends_on=["parallel_group"]
                )
            ]
        )
        
        result = await workflow_engine.execute_workflow(workflow)
        
        # Should succeed overall due to continue_on_error on failing step
        assert result.success is True
        assert len(result.step_results) == 4
        
        success1_result = result.step_results["parallel_success1"]
        failure_result = result.step_results["parallel_failure"]
        success2_result = result.step_results["parallel_success2"]
        after_result = result.step_results["after_parallel"]
        
        assert success1_result.success is True
        assert failure_result.success is False
        assert success2_result.success is True
        assert after_result.success is True
        
        # All parallel steps should have same execution order
        assert success1_result.execution_order == failure_result.execution_order
        assert success1_result.execution_order == success2_result.execution_order
        assert after_result.execution_order > success1_result.execution_order
        
        print("✅ Partial failure in parallel group handled correctly")


class TestAuthenticationErrorHandling:
    """Test authentication error scenarios."""
    
    @pytest.fixture
    def mock_server(self):
        """Mock server that validates authentication."""
        server = MockAPIServer(port=8903)
        
        # Endpoint that returns 401 for invalid auth
        server.add_endpoint(MockEndpoint(
            path="/api/protected",
            method="GET",
            response_data={"error": "Unauthorized"},
            status_code=401
        ))
        
        server.start(background=True)
        yield server
        server.stop()
    
    @pytest.mark.asyncio 
    async def test_authentication_failure(self, mock_server):
        """Test handling of authentication failures."""
        client = WorkflowHTTPClient(base_url=mock_server.base_url)
        engine = WorkflowExecutionEngine(http_client=client)
        
        workflow = WorkflowConfig(
            name="auth_failure_test",
            api_base=mock_server.base_url,
            auth=AuthConfig(type="bearer", token="invalid-token"),
            steps=[
                StepConfig(
                    name="protected_step",
                    endpoint="/api/protected",
                    method="GET",
                    retry=RetryConfig(limit=2, delay="1s")
                )
            ]
        )
        
        result = await engine.execute_workflow(workflow)
        
        assert result.success is False
        step_result = result.step_results["protected_step"]
        assert step_result.success is False
        assert step_result.retry_count == 2  # Should retry auth failures
        assert "401" in str(step_result.error) or "unauthorized" in step_result.error.lower()
        
        print("✅ Authentication failure properly handled")


if __name__ == "__main__":
    # Run a quick test of the mock server
    import asyncio
    
    async def run_basic_test():
        from tests.fixtures.mock_api_server import test_mock_server
        await test_mock_server()
    
    asyncio.run(run_basic_test())