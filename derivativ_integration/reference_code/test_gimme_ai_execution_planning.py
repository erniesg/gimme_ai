"""Unit tests for gimme_ai parallel vs sequential step execution logic.

This module tests the execution planning, dependency resolution, and parallel/sequential
step orchestration components of the GenericAPIWorkflow engine.
"""

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any, Optional

import pytest


@dataclass
class StepConfig:
    """Step configuration for workflow execution."""
    name: str
    endpoint: str
    method: str = "POST"
    depends_on: list[str] = field(default_factory=list)
    parallel_group: Optional[str] = None
    max_parallel: Optional[int] = None
    payload: Optional[dict[str, Any]] = None
    retry: Optional[dict[str, Any]] = None
    timeout: str = "30s"
    continue_on_error: bool = False


@dataclass
class ExecutionPhase:
    """Execution phase containing sequential steps and parallel groups."""
    sequential_steps: list[StepConfig] = field(default_factory=list)
    parallel_groups: list['StepGroup'] = field(default_factory=list)


@dataclass
class StepGroup:
    """Group of steps to execute in parallel."""
    group_name: str
    steps: list[StepConfig]
    max_parallel: Optional[int] = None


@dataclass
class ExecutionPlan:
    """Complete execution plan with phases."""
    phases: list[ExecutionPhase]
    total_steps: int


@dataclass
class StepResult:
    """Result of executing a workflow step."""
    step_name: str
    status: str  # 'success', 'failure', 'skipped'
    result: Optional[Any] = None
    error: Optional[str] = None
    duration_ms: float = 0
    attempts: int = 1
    start_time: Optional[float] = None
    end_time: Optional[float] = None


class ExecutionPlanner:
    """Execution planner for building dependency-aware execution plans."""

    def __init__(self):
        self.dependency_graph: dict[str, list[str]] = {}
        self.parallel_groups: dict[str, list[StepConfig]] = {}
        self.step_map: dict[str, StepConfig] = {}

    def build_execution_plan(self, steps: list[StepConfig]) -> ExecutionPlan:
        """Build execution plan with proper dependency resolution and parallel grouping."""

        # Reset internal state
        self.dependency_graph.clear()
        self.parallel_groups.clear()
        self.step_map.clear()

        # Build maps and graphs
        self._build_step_maps(steps)
        self._validate_dependencies()

        # Perform topological sort with parallel group awareness
        phases = self._build_execution_phases()

        return ExecutionPlan(
            phases=phases,
            total_steps=len(steps)
        )

    def _build_step_maps(self, steps: list[StepConfig]) -> None:
        """Build internal maps for steps, dependencies, and parallel groups."""

        for step in steps:
            # Validate step name uniqueness
            if step.name in self.step_map:
                raise ValueError(f"Duplicate step name: {step.name}")

            self.step_map[step.name] = step
            self.dependency_graph[step.name] = step.depends_on.copy()

            # Group parallel steps
            if step.parallel_group:
                if step.parallel_group not in self.parallel_groups:
                    self.parallel_groups[step.parallel_group] = []
                self.parallel_groups[step.parallel_group].append(step)

    def _validate_dependencies(self) -> None:
        """Validate that all dependencies exist and no circular dependencies."""

        # Check all dependencies exist
        for step_name, deps in self.dependency_graph.items():
            for dep in deps:
                if dep not in self.step_map:
                    raise ValueError(f"Step '{step_name}' depends on non-existent step: '{dep}'")

        # Check for circular dependencies using DFS
        visited = set()
        rec_stack = set()

        def has_cycle(node: str) -> bool:
            visited.add(node)
            rec_stack.add(node)

            for neighbor in self.dependency_graph.get(node, []):
                if neighbor not in visited:
                    if has_cycle(neighbor):
                        return True
                elif neighbor in rec_stack:
                    return True

            rec_stack.remove(node)
            return False

        for step_name in self.step_map:
            if step_name not in visited:
                if has_cycle(step_name):
                    raise ValueError("Circular dependency detected in workflow steps")

    def _build_execution_phases(self) -> list[ExecutionPhase]:
        """Build execution phases using topological sort with parallel group awareness."""

        phases = []
        completed = set()
        remaining = set(self.step_map.keys())

        while remaining:
            phase = ExecutionPhase()

            # Find steps that can execute (all dependencies completed)
            ready_steps = []
            for step_name in remaining:
                deps = self.dependency_graph[step_name]
                if all(dep in completed for dep in deps):
                    ready_steps.append(self.step_map[step_name])

            if not ready_steps:
                raise ValueError("No steps can execute - possible dependency cycle")

            # Group ready steps by parallel groups vs sequential
            sequential_steps = []
            grouped_steps = {}

            for step in ready_steps:
                if step.parallel_group:
                    if step.parallel_group not in grouped_steps:
                        grouped_steps[step.parallel_group] = []
                    grouped_steps[step.parallel_group].append(step)
                else:
                    sequential_steps.append(step)

            # Add sequential steps to phase
            phase.sequential_steps = sequential_steps

            # Add complete parallel groups to phase
            for group_name, group_steps in grouped_steps.items():
                all_group_steps = self.parallel_groups[group_name]
                ready_group_steps = [s for s in group_steps if s.name in [rs.name for rs in ready_steps]]

                # Only add complete parallel groups (all members ready)
                if len(ready_group_steps) == len(all_group_steps):
                    max_parallel = ready_group_steps[0].max_parallel if ready_group_steps else None
                    phase.parallel_groups.append(StepGroup(
                        group_name=group_name,
                        steps=ready_group_steps,
                        max_parallel=max_parallel
                    ))

                    # Mark group steps as handled
                    for step in ready_group_steps:
                        completed.add(step.name)
                        remaining.discard(step.name)

            # Mark sequential steps as completed
            for step in sequential_steps:
                completed.add(step.name)
                remaining.discard(step.name)

            phases.append(phase)

        return phases


class WorkflowExecutor:
    """Workflow executor for running execution plans with parallel/sequential logic."""

    def __init__(self):
        self.step_results: dict[str, StepResult] = {}
        self.execution_history: list[dict[str, Any]] = []
        self.mock_api = MockAPIExecutor()

    async def execute_plan(self, plan: ExecutionPlan) -> dict[str, StepResult]:
        """Execute complete workflow plan."""

        self.step_results.clear()
        self.execution_history.clear()

        print(f"Executing workflow plan with {len(plan.phases)} phases, {plan.total_steps} total steps")

        for phase_index, phase in enumerate(plan.phases):
            await self._execute_phase(phase, phase_index)

        return self.step_results.copy()

    async def _execute_phase(self, phase: ExecutionPhase, phase_index: int) -> None:
        """Execute a single phase (sequential steps + parallel groups)."""

        phase_start = time.time()
        print(f"Phase {phase_index}: {len(phase.sequential_steps)} sequential steps, {len(phase.parallel_groups)} parallel groups")

        # Execute sequential steps first
        for step in phase.sequential_steps:
            result = await self._execute_step(step)
            self.step_results[step.name] = result

        # Execute parallel groups
        for group in phase.parallel_groups:
            group_results = await self._execute_parallel_group(group)
            for result in group_results:
                self.step_results[result.step_name] = result

        phase_duration = (time.time() - phase_start) * 1000
        self.execution_history.append({
            "phase": phase_index,
            "duration_ms": phase_duration,
            "sequential_steps": len(phase.sequential_steps),
            "parallel_groups": len(phase.parallel_groups)
        })

    async def _execute_parallel_group(self, group: StepGroup) -> list[StepResult]:
        """Execute a parallel group of steps with optional concurrency control."""

        print(f"Executing parallel group '{group.group_name}' with {len(group.steps)} steps")

        # Use semaphore for concurrency control if max_parallel specified
        if group.max_parallel and group.max_parallel < len(group.steps):
            semaphore = asyncio.Semaphore(group.max_parallel)

            async def execute_with_semaphore(step: StepConfig) -> StepResult:
                async with semaphore:
                    return await self._execute_step(step)

            tasks = [execute_with_semaphore(step) for step in group.steps]
        else:
            # Execute all in parallel without limit
            tasks = [self._execute_step(step) for step in group.steps]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Handle exceptions in results
        step_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                step_results.append(StepResult(
                    step_name=group.steps[i].name,
                    status='failure',
                    error=str(result),
                    duration_ms=0
                ))
            else:
                step_results.append(result)

        return step_results

    async def _execute_step(self, step: StepConfig) -> StepResult:
        """Execute a single workflow step."""

        start_time = time.time()
        print(f"Executing step: {step.name}")

        try:
            # Simulate API call
            response = await self.mock_api.call_api(
                endpoint=step.endpoint,
                method=step.method,
                payload=step.payload,
                step_name=step.name
            )

            end_time = time.time()
            duration_ms = (end_time - start_time) * 1000

            return StepResult(
                step_name=step.name,
                status='success',
                result=response,
                duration_ms=duration_ms,
                start_time=start_time,
                end_time=end_time
            )

        except Exception as e:
            end_time = time.time()
            duration_ms = (end_time - start_time) * 1000

            if step.continue_on_error:
                return StepResult(
                    step_name=step.name,
                    status='skipped',
                    error=str(e),
                    duration_ms=duration_ms,
                    start_time=start_time,
                    end_time=end_time
                )
            else:
                return StepResult(
                    step_name=step.name,
                    status='failure',
                    error=str(e),
                    duration_ms=duration_ms,
                    start_time=start_time,
                    end_time=end_time
                )


class MockAPIExecutor:
    """Mock API executor for testing workflow execution."""

    def __init__(self):
        self.call_count = 0
        self.call_history: list[dict[str, Any]] = []

    async def call_api(
        self,
        endpoint: str,
        method: str = "POST",
        payload: Optional[dict[str, Any]] = None,
        step_name: str = ""
    ) -> dict[str, Any]:
        """Mock API call with configurable responses."""

        self.call_count += 1
        call_record = {
            "call_id": self.call_count,
            "endpoint": endpoint,
            "method": method,
            "payload": payload,
            "step_name": step_name,
            "timestamp": time.time()
        }
        self.call_history.append(call_record)

        # Simulate processing time
        await asyncio.sleep(0.01)  # 10ms simulation

        # Return endpoint-specific responses
        if "questions/generate" in endpoint:
            return {
                "question_ids": [f"{step_name}_q1", f"{step_name}_q2"],
                "count": 2,
                "status": "success"
            }
        elif "documents/generate" in endpoint:
            return {
                "document_id": f"doc_{step_name}_{self.call_count}",
                "status": "generated"
            }
        elif "documents/store" in endpoint:
            return {
                "storage_id": f"storage_{self.call_count}",
                "status": "stored"
            }
        elif "test/error" in endpoint:
            raise Exception(f"Simulated error for {step_name}")
        else:
            return {
                "result": f"success_{step_name}",
                "call_id": self.call_count
            }


class TestExecutionPlanning:
    """Test cases for execution planning and dependency resolution."""

    def test_simple_sequential_steps(self):
        """Test simple sequential steps without dependencies."""
        steps = [
            StepConfig(name="step1", endpoint="/api/step1"),
            StepConfig(name="step2", endpoint="/api/step2"),
            StepConfig(name="step3", endpoint="/api/step3")
        ]

        planner = ExecutionPlanner()
        plan = planner.build_execution_plan(steps)

        assert len(plan.phases) == 1
        assert len(plan.phases[0].sequential_steps) == 3
        assert len(plan.phases[0].parallel_groups) == 0
        assert plan.total_steps == 3

    def test_simple_parallel_group(self):
        """Test simple parallel group without dependencies."""
        steps = [
            StepConfig(name="parallel1", endpoint="/api/p1", parallel_group="group1"),
            StepConfig(name="parallel2", endpoint="/api/p2", parallel_group="group1"),
            StepConfig(name="parallel3", endpoint="/api/p3", parallel_group="group1")
        ]

        planner = ExecutionPlanner()
        plan = planner.build_execution_plan(steps)

        assert len(plan.phases) == 1
        assert len(plan.phases[0].sequential_steps) == 0
        assert len(plan.phases[0].parallel_groups) == 1

        group = plan.phases[0].parallel_groups[0]
        assert group.group_name == "group1"
        assert len(group.steps) == 3

    def test_mixed_sequential_and_parallel(self):
        """Test mix of sequential steps and parallel groups."""
        steps = [
            StepConfig(name="init", endpoint="/api/init"),
            StepConfig(name="parallel1", endpoint="/api/p1", parallel_group="group1"),
            StepConfig(name="parallel2", endpoint="/api/p2", parallel_group="group1"),
            StepConfig(name="cleanup", endpoint="/api/cleanup")
        ]

        planner = ExecutionPlanner()
        plan = planner.build_execution_plan(steps)

        assert len(plan.phases) == 1  # All can run in parallel since no dependencies
        assert len(plan.phases[0].sequential_steps) == 2  # init and cleanup
        assert len(plan.phases[0].parallel_groups) == 1   # group1

    def test_dependency_based_phases(self):
        """Test dependency-based phase separation."""
        steps = [
            StepConfig(name="init", endpoint="/api/init"),
            StepConfig(name="process1", endpoint="/api/p1", depends_on=["init"]),
            StepConfig(name="process2", endpoint="/api/p2", depends_on=["init"]),
            StepConfig(name="cleanup", endpoint="/api/cleanup", depends_on=["process1", "process2"])
        ]

        planner = ExecutionPlanner()
        plan = planner.build_execution_plan(steps)

        assert len(plan.phases) == 3

        # Phase 0: init only
        assert len(plan.phases[0].sequential_steps) == 1
        assert plan.phases[0].sequential_steps[0].name == "init"

        # Phase 1: process1 and process2 (can run in parallel)
        assert len(plan.phases[1].sequential_steps) == 2
        step_names = [s.name for s in plan.phases[1].sequential_steps]
        assert "process1" in step_names
        assert "process2" in step_names

        # Phase 2: cleanup only
        assert len(plan.phases[2].sequential_steps) == 1
        assert plan.phases[2].sequential_steps[0].name == "cleanup"

    def test_parallel_group_with_dependencies(self):
        """Test parallel group that depends on previous steps."""
        steps = [
            StepConfig(name="init", endpoint="/api/init"),
            StepConfig(name="parallel1", endpoint="/api/p1",
                      parallel_group="group1", depends_on=["init"]),
            StepConfig(name="parallel2", endpoint="/api/p2",
                      parallel_group="group1", depends_on=["init"]),
            StepConfig(name="parallel3", endpoint="/api/p3",
                      parallel_group="group1", depends_on=["init"])
        ]

        planner = ExecutionPlanner()
        plan = planner.build_execution_plan(steps)

        assert len(plan.phases) == 2

        # Phase 0: init
        assert len(plan.phases[0].sequential_steps) == 1
        assert plan.phases[0].sequential_steps[0].name == "init"

        # Phase 1: parallel group
        assert len(plan.phases[1].parallel_groups) == 1
        group = plan.phases[1].parallel_groups[0]
        assert len(group.steps) == 3

    def test_complex_derivativ_workflow(self):
        """Test complex Derivativ-style workflow with multiple phases."""
        steps = [
            # Phase 1: Parallel question generation
            StepConfig(name="generate_algebra", endpoint="/api/questions/generate",
                      parallel_group="question_generation"),
            StepConfig(name="generate_geometry", endpoint="/api/questions/generate",
                      parallel_group="question_generation"),
            StepConfig(name="generate_statistics", endpoint="/api/questions/generate",
                      parallel_group="question_generation"),

            # Phase 2: Document generation (depends on questions)
            StepConfig(name="create_worksheet", endpoint="/api/documents/generate",
                      depends_on=["generate_algebra", "generate_geometry", "generate_statistics"]),
            StepConfig(name="create_answer_key", endpoint="/api/documents/generate",
                      depends_on=["generate_algebra", "generate_geometry", "generate_statistics"]),
            StepConfig(name="create_teaching_notes", endpoint="/api/documents/generate",
                      depends_on=["generate_algebra", "generate_geometry", "generate_statistics"]),

            # Phase 3: Storage (depends on documents)
            StepConfig(name="store_documents", endpoint="/api/documents/store",
                      depends_on=["create_worksheet", "create_answer_key", "create_teaching_notes"])
        ]

        planner = ExecutionPlanner()
        plan = planner.build_execution_plan(steps)

        assert len(plan.phases) == 3
        assert plan.total_steps == 7

        # Phase 0: Parallel question generation
        assert len(plan.phases[0].parallel_groups) == 1
        assert plan.phases[0].parallel_groups[0].group_name == "question_generation"
        assert len(plan.phases[0].parallel_groups[0].steps) == 3

        # Phase 1: Document generation (sequential)
        assert len(plan.phases[1].sequential_steps) == 3
        doc_step_names = [s.name for s in plan.phases[1].sequential_steps]
        assert "create_worksheet" in doc_step_names
        assert "create_answer_key" in doc_step_names
        assert "create_teaching_notes" in doc_step_names

        # Phase 2: Storage
        assert len(plan.phases[2].sequential_steps) == 1
        assert plan.phases[2].sequential_steps[0].name == "store_documents"

    def test_duplicate_step_names(self):
        """Test validation of duplicate step names."""
        steps = [
            StepConfig(name="duplicate", endpoint="/api/step1"),
            StepConfig(name="duplicate", endpoint="/api/step2")
        ]

        planner = ExecutionPlanner()

        with pytest.raises(ValueError, match="Duplicate step name"):
            planner.build_execution_plan(steps)

    def test_missing_dependency(self):
        """Test validation of missing dependencies."""
        steps = [
            StepConfig(name="step1", endpoint="/api/step1", depends_on=["nonexistent"])
        ]

        planner = ExecutionPlanner()

        with pytest.raises(ValueError, match="depends on non-existent step"):
            planner.build_execution_plan(steps)

    def test_circular_dependency(self):
        """Test detection of circular dependencies."""
        steps = [
            StepConfig(name="step1", endpoint="/api/step1", depends_on=["step2"]),
            StepConfig(name="step2", endpoint="/api/step2", depends_on=["step1"])
        ]

        planner = ExecutionPlanner()

        with pytest.raises(ValueError, match="Circular dependency"):
            planner.build_execution_plan(steps)

    def test_complex_circular_dependency(self):
        """Test detection of complex circular dependencies."""
        steps = [
            StepConfig(name="step1", endpoint="/api/step1", depends_on=["step3"]),
            StepConfig(name="step2", endpoint="/api/step2", depends_on=["step1"]),
            StepConfig(name="step3", endpoint="/api/step3", depends_on=["step2"])
        ]

        planner = ExecutionPlanner()

        with pytest.raises(ValueError, match="Circular dependency"):
            planner.build_execution_plan(steps)


class TestWorkflowExecution:
    """Test cases for workflow execution with parallel/sequential logic."""

    @pytest.mark.asyncio
    async def test_sequential_execution(self):
        """Test sequential step execution."""
        steps = [
            StepConfig(name="step1", endpoint="/api/step1"),
            StepConfig(name="step2", endpoint="/api/step2"),
            StepConfig(name="step3", endpoint="/api/step3")
        ]

        planner = ExecutionPlanner()
        plan = planner.build_execution_plan(steps)

        executor = WorkflowExecutor()
        results = await executor.execute_plan(plan)

        assert len(results) == 3
        assert all(result.status == 'success' for result in results.values())

        # Check execution order through timestamps
        step1_time = results["step1"].start_time
        step2_time = results["step2"].start_time
        step3_time = results["step3"].start_time

        assert step1_time < step2_time < step3_time

    @pytest.mark.asyncio
    async def test_parallel_execution(self):
        """Test parallel step execution."""
        steps = [
            StepConfig(name="parallel1", endpoint="/api/p1", parallel_group="group1"),
            StepConfig(name="parallel2", endpoint="/api/p2", parallel_group="group1"),
            StepConfig(name="parallel3", endpoint="/api/p3", parallel_group="group1")
        ]

        planner = ExecutionPlanner()
        plan = planner.build_execution_plan(steps)

        executor = WorkflowExecutor()
        results = await executor.execute_plan(plan)

        assert len(results) == 3
        assert all(result.status == 'success' for result in results.values())

        # Check that parallel steps executed concurrently (overlapping times)
        start_times = [results[f"parallel{i}"].start_time for i in range(1, 4)]
        end_times = [results[f"parallel{i}"].end_time for i in range(1, 4)]

        # All should start around the same time (within 50ms)
        min_start = min(start_times)
        max_start = max(start_times)
        assert (max_start - min_start) < 0.05  # 50ms tolerance

    @pytest.mark.asyncio
    async def test_derivativ_workflow_execution(self):
        """Test execution of realistic Derivativ workflow."""
        steps = [
            # Parallel question generation
            StepConfig(name="generate_algebra", endpoint="/api/questions/generate",
                      parallel_group="question_generation"),
            StepConfig(name="generate_geometry", endpoint="/api/questions/generate",
                      parallel_group="question_generation"),

            # Document generation
            StepConfig(name="create_worksheet", endpoint="/api/documents/generate",
                      depends_on=["generate_algebra", "generate_geometry"]),
            StepConfig(name="create_answer_key", endpoint="/api/documents/generate",
                      depends_on=["generate_algebra", "generate_geometry"]),

            # Storage
            StepConfig(name="store_documents", endpoint="/api/documents/store",
                      depends_on=["create_worksheet", "create_answer_key"])
        ]

        planner = ExecutionPlanner()
        plan = planner.build_execution_plan(steps)

        executor = WorkflowExecutor()
        results = await executor.execute_plan(plan)

        assert len(results) == 5
        assert all(result.status == 'success' for result in results.values())

        # Verify execution order
        # Question generation should happen first (parallel)
        question_steps = ["generate_algebra", "generate_geometry"]
        doc_steps = ["create_worksheet", "create_answer_key"]
        storage_steps = ["store_documents"]

        question_times = [results[step].start_time for step in question_steps]
        doc_times = [results[step].start_time for step in doc_steps]
        storage_times = [results[step].start_time for step in storage_steps]

        # All question generation should start before document generation
        assert max(question_times) < min(doc_times)

        # All document generation should start before storage
        assert max(doc_times) < min(storage_times)

    @pytest.mark.asyncio
    async def test_concurrency_control(self):
        """Test concurrency control with max_parallel setting."""
        steps = [
            StepConfig(name="task1", endpoint="/api/task", parallel_group="limited", max_parallel=2),
            StepConfig(name="task2", endpoint="/api/task", parallel_group="limited", max_parallel=2),
            StepConfig(name="task3", endpoint="/api/task", parallel_group="limited", max_parallel=2),
            StepConfig(name="task4", endpoint="/api/task", parallel_group="limited", max_parallel=2)
        ]

        planner = ExecutionPlanner()
        plan = planner.build_execution_plan(steps)

        executor = WorkflowExecutor()

        # Override mock to have longer execution time to test concurrency
        async def slow_api_call(endpoint, method="POST", payload=None, step_name=""):
            await asyncio.sleep(0.1)  # 100ms delay
            return {"result": f"success_{step_name}"}

        executor.mock_api.call_api = slow_api_call

        start_time = time.time()
        results = await executor.execute_plan(plan)
        total_time = time.time() - start_time

        assert len(results) == 4
        assert all(result.status == 'success' for result in results.values())

        # With max_parallel=2 and 4 tasks of 100ms each:
        # Should take ~200ms (2 batches of 2 parallel tasks)
        # Without concurrency control would take ~100ms (all 4 parallel)
        # Sequential would take ~400ms (4 tasks in sequence)
        assert 0.15 < total_time < 0.3  # Should be around 200ms with some tolerance

    @pytest.mark.asyncio
    async def test_error_handling_continue_on_error(self):
        """Test error handling with continue_on_error flag."""
        steps = [
            StepConfig(name="step1", endpoint="/api/step1"),
            StepConfig(name="error_step", endpoint="/api/test/error", continue_on_error=True),
            StepConfig(name="step3", endpoint="/api/step3", depends_on=["step1"])
        ]

        planner = ExecutionPlanner()
        plan = planner.build_execution_plan(steps)

        executor = WorkflowExecutor()
        results = await executor.execute_plan(plan)

        assert len(results) == 3
        assert results["step1"].status == 'success'
        assert results["error_step"].status == 'skipped'  # Should be skipped due to continue_on_error
        assert results["step3"].status == 'success'

    @pytest.mark.asyncio
    async def test_error_handling_fail_fast(self):
        """Test error handling without continue_on_error (fail fast)."""
        steps = [
            StepConfig(name="step1", endpoint="/api/step1"),
            StepConfig(name="error_step", endpoint="/api/test/error", continue_on_error=False)
        ]

        planner = ExecutionPlanner()
        plan = planner.build_execution_plan(steps)

        executor = WorkflowExecutor()
        results = await executor.execute_plan(plan)

        assert len(results) == 2
        assert results["step1"].status == 'success'
        assert results["error_step"].status == 'failure'
        assert "Simulated error" in results["error_step"].error


if __name__ == "__main__":
    # Run basic integration tests
    async def test_integration():
        print("Running gimme_ai execution planning tests...")

        # Test 1: Simple execution plan
        steps = [
            StepConfig(name="init", endpoint="/api/init"),
            StepConfig(name="process", endpoint="/api/process", depends_on=["init"]),
            StepConfig(name="cleanup", endpoint="/api/cleanup", depends_on=["process"])
        ]

        planner = ExecutionPlanner()
        plan = planner.build_execution_plan(steps)
        print(f"✅ Simple plan: {len(plan.phases)} phases, {plan.total_steps} steps")

        # Test 2: Parallel execution
        parallel_steps = [
            StepConfig(name="task1", endpoint="/api/task", parallel_group="workers"),
            StepConfig(name="task2", endpoint="/api/task", parallel_group="workers"),
            StepConfig(name="task3", endpoint="/api/task", parallel_group="workers")
        ]

        parallel_plan = planner.build_execution_plan(parallel_steps)
        print(f"✅ Parallel plan: {len(parallel_plan.phases)} phases, {len(parallel_plan.phases[0].parallel_groups)} groups")

        # Test 3: Complex Derivativ workflow
        derivativ_steps = [
            StepConfig(name="generate_algebra", endpoint="/api/questions/generate", parallel_group="gen"),
            StepConfig(name="generate_geometry", endpoint="/api/questions/generate", parallel_group="gen"),
            StepConfig(name="create_worksheet", endpoint="/api/docs/generate",
                      depends_on=["generate_algebra", "generate_geometry"]),
            StepConfig(name="store_docs", endpoint="/api/docs/store", depends_on=["create_worksheet"])
        ]

        derivativ_plan = planner.build_execution_plan(derivativ_steps)
        print(f"✅ Derivativ plan: {len(derivativ_plan.phases)} phases")

        # Test 4: Execute a plan
        executor = WorkflowExecutor()
        results = await executor.execute_plan(derivativ_plan)
        success_count = sum(1 for r in results.values() if r.status == 'success')
        print(f"✅ Execution: {success_count}/{len(results)} steps successful")

        print("Integration tests completed.")

    # Run the integration test
    import asyncio
    asyncio.run(test_integration())
