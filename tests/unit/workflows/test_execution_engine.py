"""Test workflow execution engine with dependencies and parallel execution."""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from gimme_ai.workflows.execution_engine import (
    WorkflowExecutionEngine,
    StepExecutionResult,
    WorkflowExecutionResult,
    ExecutionError,
    DependencyError,
    CircularDependencyError
)
from gimme_ai.config.workflow import WorkflowConfig, StepConfig, AuthConfig
from gimme_ai.http.workflow_client import WorkflowHTTPClient


class TestStepExecutionResult:
    """Test step execution result data structure."""
    
    def test_step_result_success(self):
        """Test successful step result."""
        result = StepExecutionResult(
            step_name="test_step",
            success=True,
            response_data={"id": 123, "status": "complete"},
            execution_time=1.5
        )
        
        assert result.step_name == "test_step"
        assert result.success is True
        assert result.response_data["id"] == 123
        assert result.execution_time == 1.5
        assert result.error is None
    
    def test_step_result_failure(self):
        """Test failed step result."""
        result = StepExecutionResult(
            step_name="test_step",
            success=False,
            error="API request failed",
            execution_time=0.5
        )
        
        assert result.step_name == "test_step"
        assert result.success is False
        assert result.error == "API request failed"
        assert result.response_data is None


class TestWorkflowExecutionEngine:
    """Test workflow execution engine."""
    
    def setup_method(self):
        """Set up test engine and mock client."""
        self.mock_client = Mock(spec=WorkflowHTTPClient)
        self.engine = WorkflowExecutionEngine(http_client=self.mock_client)
    
    def test_engine_initialization(self):
        """Test engine initialization."""
        assert self.engine.http_client == self.mock_client
        assert self.engine.execution_context == {}
        assert self.engine.step_results == {}
    
    def test_add_step_result(self):
        """Test adding step results to context."""
        result = StepExecutionResult(
            step_name="test_step",
            success=True,
            response_data={"id": 123}
        )
        
        self.engine._add_step_result(result)
        
        assert "test_step" in self.engine.step_results
        assert self.engine.step_results["test_step"] == result
        assert self.engine.execution_context["test_step"] == {"id": 123}
    
    def test_resolve_dependencies_no_deps(self):
        """Test dependency resolution with no dependencies."""
        steps = [
            StepConfig(name="step1", endpoint="/api/1"),
            StepConfig(name="step2", endpoint="/api/2")
        ]
        
        execution_order = self.engine._resolve_dependencies(steps)
        
        # Should return steps in original order when no dependencies
        assert len(execution_order) == 1  # One phase
        assert len(execution_order[0]) == 2  # Two parallel steps
        step_names = [step.name for step in execution_order[0]]
        assert "step1" in step_names
        assert "step2" in step_names
    
    def test_resolve_dependencies_sequential(self):
        """Test dependency resolution for sequential steps."""
        steps = [
            StepConfig(name="step3", endpoint="/api/3", depends_on=["step2"]),
            StepConfig(name="step1", endpoint="/api/1"),
            StepConfig(name="step2", endpoint="/api/2", depends_on=["step1"])
        ]
        
        execution_order = self.engine._resolve_dependencies(steps)
        
        # Should have 3 phases for sequential execution
        assert len(execution_order) == 3
        assert execution_order[0][0].name == "step1"
        assert execution_order[1][0].name == "step2"
        assert execution_order[2][0].name == "step3"
    
    def test_resolve_dependencies_parallel_groups(self):
        """Test dependency resolution with parallel groups."""
        steps = [
            StepConfig(name="step1", endpoint="/api/1", parallel_group="group1"),
            StepConfig(name="step2", endpoint="/api/2", parallel_group="group1"),
            StepConfig(name="step3", endpoint="/api/3", depends_on=["group1"]),
            StepConfig(name="step4", endpoint="/api/4", depends_on=["group1"])
        ]
        
        execution_order = self.engine._resolve_dependencies(steps)
        
        # Should have 2 phases: parallel group, then dependent steps
        assert len(execution_order) == 2
        
        # Phase 1: parallel group
        phase1_names = [step.name for step in execution_order[0]]
        assert "step1" in phase1_names
        assert "step2" in phase1_names
        
        # Phase 2: dependent steps
        phase2_names = [step.name for step in execution_order[1]]
        assert "step3" in phase2_names
        assert "step4" in phase2_names
    
    def test_resolve_dependencies_circular(self):
        """Test circular dependency detection."""
        steps = [
            StepConfig(name="step1", endpoint="/api/1", depends_on=["step2"]),
            StepConfig(name="step2", endpoint="/api/2", depends_on=["step1"])
        ]
        
        with pytest.raises(CircularDependencyError):
            self.engine._resolve_dependencies(steps)
    
    def test_resolve_dependencies_missing(self):
        """Test missing dependency detection."""
        steps = [
            StepConfig(name="step1", endpoint="/api/1", depends_on=["nonexistent"])
        ]
        
        with pytest.raises(DependencyError, match="Missing dependency"):
            self.engine._resolve_dependencies(steps)
    
    @pytest.mark.asyncio
    async def test_execute_single_step_success(self):
        """Test successful execution of a single step."""
        self.mock_client.make_request.return_value = {"id": 123, "status": "complete"}
        
        step = StepConfig(name="test_step", endpoint="/api/test")
        
        result = await self.engine._execute_step(step)
        
        assert result.success is True
        assert result.step_name == "test_step"
        assert result.response_data["id"] == 123
        assert result.error is None
        
        self.mock_client.make_request.assert_called_once_with(
            endpoint="/api/test",
            method="POST",
            payload=None,
            headers=None,
            timeout=None,
            download_as_file=False,
            upload_files=None,
            poll_for_completion=False,
            poll_config=None
        )
    
    @pytest.mark.asyncio
    async def test_execute_single_step_failure(self):
        """Test failed execution of a single step."""
        self.mock_client.make_request.side_effect = Exception("API Error")
        
        step = StepConfig(name="test_step", endpoint="/api/test")
        
        result = await self.engine._execute_step(step)
        
        assert result.success is False
        assert result.step_name == "test_step"
        assert result.response_data is None
        assert "API Error" in str(result.error)
    
    @pytest.mark.asyncio
    async def test_execute_step_with_payload_template(self):
        """Test step execution with Jinja2 payload template."""
        self.mock_client.make_request.return_value = {"success": True}
        
        # Set up execution context
        self.engine.execution_context = {
            "topic": "algebra",
            "count": 5
        }
        
        step = StepConfig(
            name="test_step",
            endpoint="/api/test",
            payload_template='{"topic": "{{ topic }}", "question_count": {{ count }}}'
        )
        
        result = await self.engine._execute_step(step)
        
        expected_payload = {"topic": "algebra", "question_count": 5}
        self.mock_client.make_request.assert_called_once_with(
            endpoint="/api/test",
            method="POST",
            payload=expected_payload,
            headers=None,
            timeout=None,
            download_as_file=False,
            upload_files=None,
            poll_for_completion=False,
            poll_config=None
        )
    
    @pytest.mark.asyncio
    async def test_execute_step_with_static_payload(self):
        """Test step execution with static payload."""
        self.mock_client.make_request.return_value = {"success": True}
        
        step = StepConfig(
            name="test_step",
            endpoint="/api/test",
            payload={"static": "data"}
        )
        
        result = await self.engine._execute_step(step)
        
        self.mock_client.make_request.assert_called_once_with(
            endpoint="/api/test",
            method="POST",
            payload={"static": "data"},
            headers=None,
            timeout=None,
            download_as_file=False,
            upload_files=None,
            poll_for_completion=False,
            poll_config=None
        )
    
    @pytest.mark.asyncio
    async def test_execute_step_with_previous_step_data(self):
        """Test step execution using data from previous steps."""
        self.mock_client.make_request.return_value = {"success": True}
        
        # Add previous step result to context
        previous_result = StepExecutionResult(
            step_name="previous_step",
            success=True,
            response_data={"question_ids": [1, 2, 3]}
        )
        self.engine._add_step_result(previous_result)
        
        step = StepConfig(
            name="current_step",
            endpoint="/api/documents",
            payload_template='{"question_ids": {{ previous_step.question_ids }}}'
        )
        
        result = await self.engine._execute_step(step)
        
        expected_payload = {"question_ids": [1, 2, 3]}
        self.mock_client.make_request.assert_called_once_with(
            endpoint="/api/documents",
            method="POST",
            payload=expected_payload,
            headers=None,
            timeout=None,
            download_as_file=False,
            upload_files=None,
            poll_for_completion=False,
            poll_config=None
        )
    
    @pytest.mark.asyncio
    async def test_execute_parallel_steps(self):
        """Test parallel execution of multiple steps."""
        # Mock responses for each step
        def mock_request(endpoint, **kwargs):
            if endpoint == "/api/step1":
                return {"step": 1, "result": "data1"}
            elif endpoint == "/api/step2":
                return {"step": 2, "result": "data2"}
            elif endpoint == "/api/step3":
                return {"step": 3, "result": "data3"}
        
        self.mock_client.make_request.side_effect = mock_request
        
        steps = [
            StepConfig(name="step1", endpoint="/api/step1"),
            StepConfig(name="step2", endpoint="/api/step2"),
            StepConfig(name="step3", endpoint="/api/step3")
        ]
        
        results = await self.engine._execute_parallel_steps(steps)
        
        assert len(results) == 3
        assert all(result.success for result in results)
        assert {result.step_name for result in results} == {"step1", "step2", "step3"}
        
        # Verify all steps were called
        assert self.mock_client.make_request.call_count == 3
    
    @pytest.mark.asyncio
    async def test_execute_parallel_steps_with_failure(self):
        """Test parallel execution with one step failing."""
        def mock_request(endpoint, **kwargs):
            if endpoint == "/api/step1":
                return {"step": 1, "result": "data1"}
            elif endpoint == "/api/step2":
                raise Exception("Step 2 failed")
            elif endpoint == "/api/step3":
                return {"step": 3, "result": "data3"}
        
        self.mock_client.make_request.side_effect = mock_request
        
        steps = [
            StepConfig(name="step1", endpoint="/api/step1"),
            StepConfig(name="step2", endpoint="/api/step2"),
            StepConfig(name="step3", endpoint="/api/step3")
        ]
        
        results = await self.engine._execute_parallel_steps(steps)
        
        assert len(results) == 3
        
        # Check individual results
        success_count = sum(1 for result in results if result.success)
        failure_count = sum(1 for result in results if not result.success)
        
        assert success_count == 2  # step1 and step3 succeed
        assert failure_count == 1  # step2 fails
    
    @pytest.mark.asyncio
    async def test_execute_workflow_simple(self):
        """Test complete workflow execution."""
        self.mock_client.make_request.return_value = {"success": True}
        
        workflow = WorkflowConfig(
            name="test_workflow",
            api_base="https://api.test.com",
            steps=[
                StepConfig(name="step1", endpoint="/api/step1"),
                StepConfig(name="step2", endpoint="/api/step2")
            ]
        )
        
        result = await self.engine.execute_workflow(workflow)
        
        assert result.success is True
        assert result.workflow_name == "test_workflow"
        assert len(result.step_results) == 2
        assert all(r.success for r in result.step_results.values())
    
    @pytest.mark.asyncio
    async def test_execute_workflow_with_dependencies(self):
        """Test workflow execution with step dependencies."""
        responses = []
        
        def mock_request(endpoint, **kwargs):
            if endpoint == "/api/init":
                response = {"session_id": "sess_123"}
                responses.append(("init", response))
                return response
            elif endpoint == "/api/process":
                # Should have access to init step data
                response = {"processed": True, "session": "sess_123"}
                responses.append(("process", response))
                return response
        
        self.mock_client.make_request.side_effect = mock_request
        
        workflow = WorkflowConfig(
            name="test_workflow",
            api_base="https://api.test.com",
            steps=[
                StepConfig(name="init", endpoint="/api/init"),
                StepConfig(
                    name="process",
                    endpoint="/api/process",
                    depends_on=["init"]
                )
            ]
        )
        
        result = await self.engine.execute_workflow(workflow)
        
        assert result.success is True
        assert len(responses) == 2
        assert responses[0][0] == "init"  # Init called first
        assert responses[1][0] == "process"  # Process called second
    
    @pytest.mark.asyncio
    async def test_execute_workflow_parallel_then_sequential(self):
        """Test workflow with parallel phase followed by sequential phase."""
        call_order = []
        
        def mock_request(endpoint, **kwargs):
            call_order.append(endpoint)
            if endpoint in ["/api/generate1", "/api/generate2"]:
                return {"questions": [1, 2, 3]}
            elif endpoint == "/api/compile":
                return {"document_id": "doc_123"}
        
        self.mock_client.make_request.side_effect = mock_request
        
        workflow = WorkflowConfig(
            name="test_workflow",
            api_base="https://api.test.com",
            steps=[
                StepConfig(name="generate1", endpoint="/api/generate1", parallel_group="generation"),
                StepConfig(name="generate2", endpoint="/api/generate2", parallel_group="generation"),
                StepConfig(name="compile", endpoint="/api/compile", depends_on=["generation"])
            ]
        )
        
        result = await self.engine.execute_workflow(workflow)
        
        assert result.success is True
        assert len(call_order) == 3
        
        # First two calls should be parallel (order doesn't matter)
        parallel_calls = set(call_order[:2])
        assert parallel_calls == {"/api/generate1", "/api/generate2"}
        
        # Last call should be compile (after parallel phase)
        assert call_order[2] == "/api/compile"
    
    @pytest.mark.asyncio
    async def test_execute_workflow_with_auth(self):
        """Test workflow execution with authentication."""
        auth = AuthConfig(type="bearer", token="test-token")
        
        workflow = WorkflowConfig(
            name="test_workflow",
            api_base="https://api.test.com",
            auth=auth,
            steps=[
                StepConfig(name="step1", endpoint="/api/test")
            ]
        )
        
        self.mock_client.make_request.return_value = {"success": True}
        
        result = await self.engine.execute_workflow(workflow)
        
        # Verify auth was set on client
        self.mock_client.set_auth.assert_called_once_with(auth)
        assert result.success is True
    
    @pytest.mark.asyncio
    async def test_execute_workflow_failure_handling(self):
        """Test workflow execution with step failures."""
        def mock_request(endpoint, **kwargs):
            if endpoint == "/api/step1":
                return {"success": True}
            elif endpoint == "/api/step2":
                raise Exception("Step 2 failed")
        
        self.mock_client.make_request.side_effect = mock_request
        
        workflow = WorkflowConfig(
            name="test_workflow",
            api_base="https://api.test.com",
            steps=[
                StepConfig(name="step1", endpoint="/api/step1"),
                StepConfig(name="step2", endpoint="/api/step2")
            ]
        )
        
        result = await self.engine.execute_workflow(workflow)
        
        assert result.success is False
        assert len(result.step_results) == 2
        assert result.step_results["step1"].success is True
        assert result.step_results["step2"].success is False
        assert result.error is not None
    
    @pytest.mark.asyncio
    async def test_execute_workflow_continue_on_error(self):
        """Test workflow execution with continue_on_error."""
        def mock_request(endpoint, **kwargs):
            if endpoint == "/api/step1":
                raise Exception("Step 1 failed")
            elif endpoint == "/api/step2":
                return {"success": True}
        
        self.mock_client.make_request.side_effect = mock_request
        
        workflow = WorkflowConfig(
            name="test_workflow",
            api_base="https://api.test.com",
            steps=[
                StepConfig(name="step1", endpoint="/api/step1", continue_on_error=True),
                StepConfig(name="step2", endpoint="/api/step2")
            ]
        )
        
        result = await self.engine.execute_workflow(workflow)
        
        # Workflow should succeed overall despite step1 failure
        assert result.success is True
        assert result.step_results["step1"].success is False
        assert result.step_results["step2"].success is True


class TestWorkflowExecutionResult:
    """Test workflow execution result data structure."""
    
    def test_workflow_result_success(self):
        """Test successful workflow result."""
        step_results = {
            "step1": StepExecutionResult("step1", True, {"id": 1}),
            "step2": StepExecutionResult("step2", True, {"id": 2})
        }
        
        result = WorkflowExecutionResult(
            workflow_name="test_workflow",
            success=True,
            step_results=step_results,
            total_execution_time=5.0
        )
        
        assert result.workflow_name == "test_workflow"
        assert result.success is True
        assert len(result.step_results) == 2
        assert result.total_execution_time == 5.0
        assert result.error is None
    
    def test_workflow_result_failure(self):
        """Test failed workflow result."""
        step_results = {
            "step1": StepExecutionResult("step1", True, {"id": 1}),
            "step2": StepExecutionResult("step2", False, error="Failed")
        }
        
        result = WorkflowExecutionResult(
            workflow_name="test_workflow",
            success=False,
            step_results=step_results,
            error="Step 2 failed",
            total_execution_time=3.0
        )
        
        assert result.success is False
        assert result.error == "Step 2 failed"
        assert len(result.step_results) == 2