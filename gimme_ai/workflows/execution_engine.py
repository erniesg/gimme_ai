"""Workflow execution engine with dependency management and parallel execution."""

import asyncio
import time
import logging
from typing import Dict, Any, List, Optional, NamedTuple
from dataclasses import dataclass
from ..config.workflow import WorkflowConfig, StepConfig, resolve_workflow_dependencies
from ..http.workflow_client import WorkflowHTTPClient
from ..http.connection_manager import AsyncResourceManager, get_global_resource_manager
from ..utils.security import get_secure_logger

logger = get_secure_logger(__name__)


class ExecutionError(Exception):
    """General workflow execution error."""
    pass


class DependencyError(Exception):
    """Dependency resolution error."""
    pass


class CircularDependencyError(DependencyError):
    """Circular dependency detected."""
    pass


@dataclass
class StepExecutionResult:
    """Result of executing a single workflow step."""
    step_name: str
    success: bool
    response_data: Optional[Any] = None
    error: Optional[str] = None
    execution_time: Optional[float] = None
    retry_count: int = 0
    execution_order: int = 0


@dataclass 
class WorkflowExecutionResult:
    """Result of executing a complete workflow."""
    workflow_name: str
    success: bool
    step_results: Dict[str, StepExecutionResult]
    total_execution_time: float
    error: Optional[str] = None


class WorkflowExecutionEngine:
    """Engine for executing workflows with dependency management."""
    
    def __init__(self, 
                 http_client: WorkflowHTTPClient,
                 resource_manager: Optional[AsyncResourceManager] = None):
        """
        Initialize execution engine.
        
        Args:
            http_client: HTTP client for making API calls
            resource_manager: Async resource manager (optional, uses global if None)
        """
        self.http_client = http_client
        self.execution_context: Dict[str, Any] = {}
        self.step_results: Dict[str, StepExecutionResult] = {}
        self.resource_manager = resource_manager or get_global_resource_manager()
        self.current_execution_order = 0
    
    async def execute_workflow(self, workflow: WorkflowConfig) -> WorkflowExecutionResult:
        """
        Execute a complete workflow.
        
        Args:
            workflow: Workflow configuration
            
        Returns:
            Workflow execution result
        """
        start_time = time.time()
        
        try:
            logger.info(f"Starting workflow execution: {workflow.name}")
            
            # Set up authentication
            if workflow.auth:
                self.http_client.set_auth(workflow.auth)
            
            # Set up base URL
            self.http_client.base_url = workflow.api_base
            
            # Initialize execution context with variables
            if workflow.variables:
                self.execution_context.update(workflow.variables)
            
            # Reset step results
            self.step_results = {}
            
            # Resolve dependencies and get execution phases
            execution_phases = self._resolve_dependencies(workflow.steps)
            
            # Execute phases sequentially
            for phase_index, phase_steps in enumerate(execution_phases):
                logger.info(f"Executing phase {phase_index + 1} with {len(phase_steps)} steps")
                
                if len(phase_steps) == 1:
                    # Single step - execute directly
                    result = await self._execute_step(phase_steps[0])
                    result.execution_order = phase_index
                    self._add_step_result(result)
                    
                    if not result.success and not phase_steps[0].continue_on_error:
                        raise ExecutionError(f"Step '{result.step_name}' failed: {result.error}")
                        
                else:
                    # Multiple steps - execute in parallel
                    results = await self._execute_parallel_steps(phase_steps)
                    
                    for result in results:
                        result.execution_order = phase_index
                        self._add_step_result(result)
                        
                        if not result.success and not self._get_step_config(result.step_name, phase_steps).continue_on_error:
                            raise ExecutionError(f"Step '{result.step_name}' failed: {result.error}")
            
            total_time = time.time() - start_time
            logger.info(f"Workflow '{workflow.name}' completed successfully in {total_time:.2f}s")
            
            return WorkflowExecutionResult(
                workflow_name=workflow.name,
                success=True,
                step_results=self.step_results,
                total_execution_time=total_time
            )
            
        except Exception as e:
            total_time = time.time() - start_time
            error_msg = f"Workflow '{workflow.name}' failed: {str(e)}"
            logger.error(error_msg)
            
            return WorkflowExecutionResult(
                workflow_name=workflow.name,
                success=False,
                step_results=self.step_results,
                total_execution_time=total_time,
                error=error_msg
            )
    
    def _resolve_dependencies(self, steps: List[StepConfig]) -> List[List[StepConfig]]:
        """Resolve step dependencies and return execution phases."""
        try:
            return resolve_workflow_dependencies(steps)
        except ValueError as e:
            if "circular dependency" in str(e).lower():
                raise CircularDependencyError(str(e))
            else:
                raise DependencyError(str(e))
    
    async def _execute_step(self, step: StepConfig) -> StepExecutionResult:
        """
        Execute a single workflow step.
        
        Args:
            step: Step configuration
            
        Returns:
            Step execution result
        """
        start_time = time.time()
        
        try:
            logger.debug(f"Executing step: {step.name}")
            
            # Set retry configuration if specified
            if step.retry:
                self.http_client.set_retry_config(step.retry)
            
            # Render payload
            payload = step.render_payload(self.execution_context)
            
            # Parse timeout
            timeout = self._parse_timeout(step.timeout) if step.timeout else None
            
            # Prepare poll configuration if needed
            poll_config = None
            if step.poll_for_completion:
                poll_config = {
                    'poll_interval': step.poll_interval,
                    'poll_timeout': step.poll_timeout,
                    'completion_field': step.completion_field,
                    'completion_values': step.completion_values,
                    'result_field': step.result_field
                }
            
            # Make HTTP request with advanced features
            response = self.http_client.make_request(
                endpoint=step.endpoint,
                method=step.method,
                payload=payload,
                headers=step.headers,
                timeout=timeout,
                download_as_file=step.download_response,
                upload_files=step.upload_files,
                poll_for_completion=step.poll_for_completion,
                poll_config=poll_config
            )
            
            # Extract specific fields if configured
            if step.extract_fields:
                extracted = self.http_client.extract_fields(response, step.extract_fields)
                response = extracted
            
            # Store in R2 if configured
            if step.store_in_r2 and step.r2_bucket:
                if isinstance(response, str) and os.path.exists(response):
                    # Response is a file path
                    r2_key = step.r2_key_template or f"workflow/{step.name}/{time.time()}"
                    r2_url = self.http_client.upload_to_r2(response, step.r2_bucket, r2_key)
                    response = {"file_path": response, "r2_url": r2_url}
            
            # Apply response transformation if specified
            if step.response_transform:
                response = self._transform_response(response, step.response_transform)
            
            execution_time = time.time() - start_time
            
            logger.debug(f"Step '{step.name}' completed successfully in {execution_time:.2f}s")
            
            return StepExecutionResult(
                step_name=step.name,
                success=True,
                response_data=response,
                execution_time=execution_time
            )
            
        except Exception as e:
            execution_time = time.time() - start_time
            error_msg = str(e)
            
            logger.error(f"Step '{step.name}' failed after {execution_time:.2f}s: {error_msg}")
            
            return StepExecutionResult(
                step_name=step.name,
                success=False,
                error=error_msg,
                execution_time=execution_time
            )
    
    async def _execute_parallel_steps(self, steps: List[StepConfig]) -> List[StepExecutionResult]:
        """
        Execute multiple steps in parallel with proper resource management.
        
        Args:
            steps: List of steps to execute in parallel
            
        Returns:
            List of step execution results
        """
        logger.debug(f"Executing {len(steps)} steps in parallel")
        
        # Create tasks for each step
        tasks = []
        for step in steps:
            task = asyncio.create_task(self._execute_step(step))
            tasks.append(task)
            # Track task for cleanup
            self.resource_manager.add_task(task)
        
        try:
            # Wait for all tasks to complete with timeout protection
            results = await asyncio.wait_for(
                asyncio.gather(*tasks, return_exceptions=True),
                timeout=300.0  # 5 minute overall timeout for parallel execution
            )
        except asyncio.TimeoutError:
            # Cancel remaining tasks
            for task in tasks:
                if not task.done():
                    task.cancel()
            
            # Wait for cancellation to complete
            await asyncio.gather(*tasks, return_exceptions=True)
            
            raise ExecutionError("Parallel execution timed out after 5 minutes")
        
        # Process results
        step_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                # Task raised an exception
                step_name = steps[i].name
                step_results.append(StepExecutionResult(
                    step_name=step_name,
                    success=False,
                    error=str(result)
                ))
            else:
                step_results.append(result)
        
        return step_results
    
    def _add_step_result(self, result: StepExecutionResult) -> None:
        """Add step result to context and storage."""
        self.step_results[result.step_name] = result
        
        if result.success and result.response_data is not None:
            self.execution_context[result.step_name] = result.response_data
    
    def _get_step_config(self, step_name: str, steps: List[StepConfig]) -> StepConfig:
        """Get step configuration by name."""
        for step in steps:
            if step.name == step_name:
                return step
        raise ValueError(f"Step '{step_name}' not found")
    
    def _parse_timeout(self, timeout_str: str) -> float:
        """Parse timeout string to seconds."""
        if timeout_str.endswith('s'):
            return float(timeout_str[:-1])
        elif timeout_str.endswith('m'):
            return float(timeout_str[:-1]) * 60
        elif timeout_str.endswith('h'):
            return float(timeout_str[:-1]) * 3600
        else:
            raise ValueError(f"Invalid timeout format: {timeout_str}")
    
    def reset_context(self) -> None:
        """Reset execution context and step results."""
        self.execution_context = {}
        self.step_results = {}
    
    def _transform_response(self, response: Any, transform_template: str) -> Any:
        """Transform response using Jinja2 template."""
        try:
            from jinja2 import Environment, Template
            env = Environment()
            template = env.from_string(transform_template)
            
            # Create context with response and current execution context
            template_context = {
                'response': response,
                **self.execution_context
            }
            
            transformed = template.render(**template_context)
            
            # Try to parse as JSON if it looks like JSON
            if transformed.strip().startswith(('{', '[')):
                import json
                return json.loads(transformed)
            
            return transformed
            
        except Exception as e:
            logger.error(f"Failed to transform response: {e}")
            return response