#!/usr/bin/env python3
"""
Comprehensive workflow integration tests.
Tests complete workflows with both mock and live APIs.
"""

import pytest
import asyncio
import os
import time
from typing import List, Dict, Any

from gimme_ai.workflows.execution_engine import WorkflowExecutionEngine
from gimme_ai.http.workflow_client import WorkflowHTTPClient
from gimme_ai.config.workflow import WorkflowConfig, StepConfig, AuthConfig, RetryConfig
from tests.fixtures.mock_api_server import MockAPIServer, MockAPIEndpoints

class TestComprehensiveWorkflows:
    """Test complete workflow scenarios."""
    
    @pytest.fixture(scope="class")
    def mock_server(self):
        """Start mock API server for testing."""
        server = MockAPIServer(port=8899)
        
        # Add all predefined endpoints
        for endpoint in MockAPIEndpoints.derivativ_question_generation():
            server.add_endpoint(endpoint)
        
        for endpoint in MockAPIEndpoints.openai_simulation():
            server.add_endpoint(endpoint)
        
        for endpoint in MockAPIEndpoints.unreliable_api():
            server.add_endpoint(endpoint)
        
        server.start(background=True)
        yield server
        server.stop()
    
    @pytest.fixture
    def workflow_engine(self):
        """Create workflow execution engine."""
        client = WorkflowHTTPClient(base_url="http://127.0.0.1:8899")
        return WorkflowExecutionEngine(http_client=client)
    
    @pytest.mark.asyncio
    async def test_derivativ_complete_pipeline(self, mock_server, workflow_engine):
        """Test complete Derivativ-style workflow pipeline."""
        workflow = WorkflowConfig(
            name="derivativ_complete_pipeline",
            api_base=mock_server.base_url,
            auth=AuthConfig(type="bearer", token="test-token"),
            variables={
                "topics": ["algebra", "geometry"],
                "questions_per_topic": 3,
                "grade_level": 9
            },
            steps=[
                # Phase 1: Parallel question generation
                StepConfig(
                    name="generate_algebra_questions",
                    endpoint="/api/questions/generate",
                    method="POST",
                    payload_template='''
                    {
                        "topic": "algebra",
                        "count": {{ questions_per_topic }},
                        "grade_level": {{ grade_level }}
                    }
                    ''',
                    parallel_group="question_generation",
                    retry=RetryConfig(limit=2, delay="1s", backoff="constant")
                ),
                StepConfig(
                    name="generate_geometry_questions", 
                    endpoint="/api/questions/generate",
                    method="POST",
                    payload_template='''
                    {
                        "topic": "geometry",
                        "count": {{ questions_per_topic }},
                        "grade_level": {{ grade_level }}
                    }
                    ''',
                    parallel_group="question_generation",
                    retry=RetryConfig(limit=2, delay="1s", backoff="constant")
                ),
                # Phase 2: Document generation (depends on questions)
                StepConfig(
                    name="create_worksheet",
                    endpoint="/api/documents/generate",
                    method="POST",
                    payload_template='''
                    {
                        "document_type": "worksheet",
                        "question_ids": {{ (generate_algebra_questions.question_ids + generate_geometry_questions.question_ids) | list }},
                        "metadata": {
                            "topics": {{ topics | list }},
                            "grade_level": {{ grade_level }}
                        }
                    }
                    ''',
                    depends_on=["question_generation"],
                    retry=RetryConfig(limit=2, delay="2s", backoff="exponential")
                ),
                # Phase 3: Storage (depends on document)
                StepConfig(
                    name="store_document",
                    endpoint="/api/documents/store",
                    method="POST",
                    payload_template='''
                    {
                        "document_id": "{{ create_worksheet.document_id }}",
                        "formats": ["pdf", "docx"],
                        "metadata": {
                            "total_questions": {{ questions_per_topic * 2 }},
                            "created_at": "{{ now() }}"
                        }
                    }
                    ''',
                    depends_on=["create_worksheet"],
                    retry=RetryConfig(limit=3, delay="1s", backoff="linear")
                )
            ]
        )
        
        # Execute workflow
        start_time = time.time()
        result = await workflow_engine.execute_workflow(workflow)
        execution_time = time.time() - start_time
        
        # Validate results
        assert result.success is True
        assert len(result.step_results) == 4
        
        # Check phase execution order
        algebra_result = result.step_results["generate_algebra_questions"]
        geometry_result = result.step_results["generate_geometry_questions"]
        worksheet_result = result.step_results["create_worksheet"]
        storage_result = result.step_results["store_document"]
        
        # All steps should succeed
        assert algebra_result.success is True
        assert geometry_result.success is True
        assert worksheet_result.success is True
        assert storage_result.success is True
        
        # Verify data flow
        assert len(algebra_result.response_data["question_ids"]) == 3
        assert len(geometry_result.response_data["question_ids"]) == 3
        assert worksheet_result.response_data["document_id"] == "doc_123"
        assert "storage.derivativ.ai" in storage_result.response_data["url"]
        
        # Verify execution order (parallel steps should run concurrently)
        assert algebra_result.execution_order == geometry_result.execution_order  # Parallel
        assert worksheet_result.execution_order > algebra_result.execution_order  # Sequential after
        assert storage_result.execution_order > worksheet_result.execution_order  # Sequential after
        
        print(f"✅ Complete pipeline executed in {execution_time:.2f}s")
    
    @pytest.mark.asyncio
    async def test_error_recovery_workflow(self, mock_server, workflow_engine):
        """Test workflow with error recovery and retry logic."""
        workflow = WorkflowConfig(
            name="error_recovery_test",
            api_base=mock_server.base_url,
            steps=[
                # This should succeed immediately
                StepConfig(
                    name="reliable_step",
                    endpoint="/health",
                    method="GET"
                ),
                # This will fail twice then succeed
                StepConfig(
                    name="unreliable_step",
                    endpoint="/api/unreliable",
                    method="POST",
                    payload={"test": "data"},
                    retry=RetryConfig(limit=3, delay="0.5s", backoff="exponential"),
                    depends_on=["reliable_step"]
                ),
                # This should succeed after unreliable step
                StepConfig(
                    name="final_step",
                    endpoint="/health",
                    method="GET",
                    depends_on=["unreliable_step"]
                )
            ]
        )
        
        result = await workflow_engine.execute_workflow(workflow)
        
        assert result.success is True
        assert len(result.step_results) == 3
        
        # Check that unreliable step eventually succeeded
        unreliable_result = result.step_results["unreliable_step"]
        assert unreliable_result.success is True
        assert unreliable_result.retry_count == 2  # Failed twice, succeeded on 3rd
        
        print("✅ Error recovery workflow completed successfully")
    
    @pytest.mark.asyncio
    async def test_parallel_execution_performance(self, mock_server, workflow_engine):
        """Test that parallel execution actually runs concurrently."""
        # Create workflow with multiple parallel steps
        parallel_steps = []
        for i in range(5):
            parallel_steps.append(
                StepConfig(
                    name=f"parallel_step_{i}",
                    endpoint="/api/questions/generate",  # Has 2.5s delay
                    method="POST",
                    payload={"topic": f"topic_{i}", "count": 1},
                    parallel_group="parallel_group"
                )
            )
        
        workflow = WorkflowConfig(
            name="parallel_performance_test",
            api_base=mock_server.base_url,
            steps=parallel_steps
        )
        
        start_time = time.time()
        result = await workflow_engine.execute_workflow(workflow)
        execution_time = time.time() - start_time
        
        assert result.success is True
        assert len(result.step_results) == 5
        
        # All parallel steps should complete in roughly the time of the slowest step
        # If run sequentially: 5 * 2.5s = 12.5s
        # If run in parallel: ~2.5s (plus overhead)
        assert execution_time < 8.0, f"Parallel execution took {execution_time:.2f}s, expected < 8s"
        
        print(f"✅ Parallel execution completed in {execution_time:.2f}s (expected ~2.5s)")
    
    @pytest.mark.asyncio
    async def test_template_variable_substitution(self, mock_server, workflow_engine):
        """Test comprehensive template variable substitution."""
        workflow = WorkflowConfig(
            name="template_test",
            api_base=mock_server.base_url,
            variables={
                "base_topic": "mathematics",
                "difficulty_levels": ["easy", "medium", "hard"],
                "user_id": 12345,
                "metadata": {
                    "version": "1.0",
                    "created_by": "test_user"
                }
            },
            steps=[
                StepConfig(
                    name="step1",
                    endpoint="/api/questions/generate", 
                    method="POST",
                    payload_template='''
                    {
                        "topic": "{{ base_topic }}",
                        "user_id": {{ user_id }},
                        "difficulties": {{ difficulty_levels | list }},
                        "metadata": {{ metadata | tojson }},
                        "count": {{ difficulty_levels | length }}
                    }
                    '''
                ),
                StepConfig(
                    name="step2",
                    endpoint="/api/documents/generate",
                    method="POST", 
                    payload_template='''
                    {
                        "previous_questions": {{ step1.question_ids | list }},
                        "question_count": {{ step1.question_ids | length }},
                        "base_topic": "{{ base_topic }}",
                        "user_context": {
                            "user_id": {{ user_id }},
                            "version": "{{ metadata.version }}"
                        }
                    }
                    ''',
                    depends_on=["step1"]
                )
            ]
        )
        
        result = await workflow_engine.execute_workflow(workflow)
        
        assert result.success is True
        
        # Check that templates were properly substituted
        step1_result = result.step_results["step1"]
        step2_result = result.step_results["step2"]
        
        assert step1_result.success is True
        assert step2_result.success is True
        
        print("✅ Template variable substitution worked correctly")
    
    @pytest.mark.asyncio
    async def test_continue_on_error_behavior(self, mock_server, workflow_engine):
        """Test continue_on_error flag behavior."""
        workflow = WorkflowConfig(
            name="continue_on_error_test",
            api_base=mock_server.base_url,
            steps=[
                StepConfig(
                    name="step1", 
                    endpoint="/health",
                    method="GET"
                ),
                StepConfig(
                    name="failing_step",
                    endpoint="/api/nonexistent",  # This will 404
                    method="GET",
                    continue_on_error=True,
                    depends_on=["step1"]
                ),
                StepConfig(
                    name="step3",
                    endpoint="/health", 
                    method="GET",
                    depends_on=["failing_step"]
                )
            ]
        )
        
        result = await workflow_engine.execute_workflow(workflow)
        
        # Workflow should succeed overall due to continue_on_error
        assert result.success is True
        assert len(result.step_results) == 3
        
        # Check individual step results
        step1_result = result.step_results["step1"]
        failing_result = result.step_results["failing_step"]
        step3_result = result.step_results["step3"]
        
        assert step1_result.success is True
        assert failing_result.success is False  # This step failed
        assert step3_result.success is True    # But workflow continued
        
        print("✅ Continue on error behavior works correctly")


@pytest.mark.integration
class TestLiveAPIIntegration:
    """Test integration with real live APIs."""
    
    @pytest.fixture
    def openai_api_key(self):
        """Get OpenAI API key from environment."""
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            pytest.skip("OPENAI_API_KEY not found in environment")
        return api_key
    
    @pytest.mark.asyncio
    async def test_openai_question_generation_workflow(self, openai_api_key):
        """Test realistic question generation workflow with OpenAI."""
        client = WorkflowHTTPClient(base_url="https://api.openai.com")
        engine = WorkflowExecutionEngine(http_client=client)
        
        workflow = WorkflowConfig(
            name="openai_education_workflow",
            api_base="https://api.openai.com",
            auth=AuthConfig(type="bearer", token=openai_api_key),
            variables={
                "subject": "algebra",
                "grade_level": "grade 9",
                "question_types": ["word problems", "equations", "graphing"]
            },
            steps=[
                # Generate questions for different types in parallel
                StepConfig(
                    name="generate_word_problems",
                    endpoint="/v1/chat/completions",
                    method="POST",
                    headers={"Content-Type": "application/json"},
                    payload_template='''
                    {
                        "model": "gpt-3.5-turbo",
                        "messages": [
                            {"role": "system", "content": "You are an expert math teacher creating {{ grade_level }} {{ subject }} questions."},
                            {"role": "user", "content": "Create 2 word problems for {{ subject }}. Format as JSON with 'questions' array."}
                        ],
                        "max_tokens": 300,
                        "temperature": 0.7
                    }
                    ''',
                    parallel_group="question_generation",
                    timeout="30s"
                ),
                StepConfig(
                    name="generate_equations",
                    endpoint="/v1/chat/completions", 
                    method="POST",
                    headers={"Content-Type": "application/json"},
                    payload_template='''
                    {
                        "model": "gpt-3.5-turbo",
                        "messages": [
                            {"role": "system", "content": "You are an expert math teacher creating {{ grade_level }} {{ subject }} questions."},
                            {"role": "user", "content": "Create 2 equation-solving problems for {{ subject }}. Format as JSON with 'questions' array."}
                        ],
                        "max_tokens": 300,
                        "temperature": 0.7
                    }
                    ''',
                    parallel_group="question_generation",
                    timeout="30s"
                ),
                # Create a summary after all questions are generated
                StepConfig(
                    name="create_question_summary",
                    endpoint="/v1/chat/completions",
                    method="POST", 
                    headers={"Content-Type": "application/json"},
                    payload_template='''
                    {
                        "model": "gpt-3.5-turbo",
                        "messages": [
                            {"role": "user", "content": "Summarize these {{ subject }} questions:\\n\\nWord Problems: {{ generate_word_problems.choices[0].message.content }}\\n\\nEquations: {{ generate_equations.choices[0].message.content }}\\n\\nProvide a brief summary of the question types and difficulty."}
                        ],
                        "max_tokens": 150
                    }
                    ''',
                    depends_on=["question_generation"],
                    timeout="30s"
                )
            ]
        )
        
        start_time = time.time()
        result = await workflow_engine.execute_workflow(workflow)
        execution_time = time.time() - start_time
        
        # Validate results
        assert result.success is True
        assert len(result.step_results) == 3
        
        word_problems_result = result.step_results["generate_word_problems"]
        equations_result = result.step_results["generate_equations"]
        summary_result = result.step_results["create_question_summary"]
        
        assert word_problems_result.success is True
        assert equations_result.success is True
        assert summary_result.success is True
        
        # Verify content was generated
        word_content = word_problems_result.response_data["choices"][0]["message"]["content"]
        equation_content = equations_result.response_data["choices"][0]["message"]["content"]
        summary_content = summary_result.response_data["choices"][0]["message"]["content"]
        
        assert len(word_content.strip()) > 50
        assert len(equation_content.strip()) > 50
        assert len(summary_content.strip()) > 20
        
        print(f"✅ OpenAI education workflow completed in {execution_time:.2f}s")
        print(f"   Generated word problems: {len(word_content)} chars")
        print(f"   Generated equations: {len(equation_content)} chars")
        print(f"   Generated summary: {len(summary_content)} chars")
    
    @pytest.mark.asyncio
    async def test_multi_provider_workflow(self, openai_api_key):
        """Test workflow that could use multiple AI providers."""
        # This test simulates switching between providers
        # In a real scenario, you might have fallback logic
        
        client = WorkflowHTTPClient(base_url="https://api.openai.com")
        engine = WorkflowExecutionEngine(http_client=client)
        
        workflow = WorkflowConfig(
            name="multi_provider_simulation",
            api_base="https://api.openai.com",
            auth=AuthConfig(type="bearer", token=openai_api_key),
            steps=[
                # Primary provider (OpenAI)
                StepConfig(
                    name="primary_generation",
                    endpoint="/v1/chat/completions",
                    method="POST",
                    headers={"Content-Type": "application/json"},
                    payload={
                        "model": "gpt-3.5-turbo",
                        "messages": [
                            {"role": "user", "content": "Generate a simple math question about fractions."}
                        ],
                        "max_tokens": 100
                    },
                    retry=RetryConfig(limit=2, delay="2s", backoff="exponential"),
                    timeout="30s"
                ),
                # Quality check step
                StepConfig(
                    name="quality_check",
                    endpoint="/v1/chat/completions", 
                    method="POST",
                    headers={"Content-Type": "application/json"},
                    payload_template='''
                    {
                        "model": "gpt-3.5-turbo",
                        "messages": [
                            {"role": "user", "content": "Rate the quality of this math question on a scale of 1-10:\\n{{ primary_generation.choices[0].message.content }}\\n\\nProvide just the number."}
                        ],
                        "max_tokens": 10
                    }
                    ''',
                    depends_on=["primary_generation"]
                )
            ]
        )
        
        result = await workflow_engine.execute_workflow(workflow)
        
        assert result.success is True
        assert len(result.step_results) == 2
        
        primary_result = result.step_results["primary_generation"]
        quality_result = result.step_results["quality_check"]
        
        assert primary_result.success is True
        assert quality_result.success is True
        
        generated_question = primary_result.response_data["choices"][0]["message"]["content"]
        quality_score = quality_result.response_data["choices"][0]["message"]["content"]
        
        print(f"✅ Multi-provider workflow simulation completed")
        print(f"   Generated question: {generated_question[:100]}...")
        print(f"   Quality score: {quality_score.strip()}")


if __name__ == "__main__":
    # Run basic mock server test
    import asyncio
    
    async def run_basic_test():
        from tests.fixtures.mock_api_server import test_mock_server
        await test_mock_server()
    
    asyncio.run(run_basic_test())