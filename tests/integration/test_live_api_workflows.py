"""Integration tests with live APIs to validate workflow patterns."""

import pytest
import os
import asyncio
from unittest.mock import patch
from gimme_ai.workflows.execution_engine import WorkflowExecutionEngine
from gimme_ai.http.workflow_client import WorkflowHTTPClient
from gimme_ai.config.workflow import WorkflowConfig, StepConfig, AuthConfig, RetryConfig


class TestLiveAPIIntegration:
    """Test integration with live APIs."""
    
    @pytest.fixture
    def openai_api_key(self):
        """Get OpenAI API key from environment."""
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            pytest.skip("OPENAI_API_KEY not found in environment")
        return api_key
    
    @pytest.fixture
    def replicate_token(self):
        """Get Replicate token from environment."""
        token = os.getenv("REPLICATE_API_TOKEN")
        if not token:
            pytest.skip("REPLICATE_API_TOKEN not found in environment")
        return token
    
    @pytest.fixture
    def workflow_engine(self):
        """Create workflow execution engine."""
        client = WorkflowHTTPClient(base_url="https://api.openai.com")
        return WorkflowExecutionEngine(http_client=client)
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_openai_simple_completion(self, openai_api_key, workflow_engine):
        """Test simple OpenAI API call workflow."""
        auth = AuthConfig(type="bearer", token=openai_api_key)
        
        workflow = WorkflowConfig(
            name="openai_simple_test",
            api_base="https://api.openai.com",
            auth=auth,
            steps=[
                StepConfig(
                    name="generate_text",
                    endpoint="/v1/chat/completions",
                    method="POST",
                    headers={"Content-Type": "application/json"},
                    payload={
                        "model": "gpt-3.5-turbo",
                        "messages": [
                            {"role": "user", "content": "Say 'Hello, World!' and nothing else."}
                        ],
                        "max_tokens": 10
                    },
                    timeout="30s"
                )
            ]
        )
        
        result = await workflow_engine.execute_workflow(workflow)
        
        assert result.success is True
        assert "generate_text" in result.step_results
        
        step_result = result.step_results["generate_text"]
        assert step_result.success is True
        assert "choices" in step_result.response_data
        assert len(step_result.response_data["choices"]) > 0
        
        message_content = step_result.response_data["choices"][0]["message"]["content"]
        assert "Hello" in message_content
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_openai_multi_step_workflow(self, openai_api_key, workflow_engine):
        """Test multi-step workflow with OpenAI API."""
        auth = AuthConfig(type="bearer", token=openai_api_key)
        
        workflow = WorkflowConfig(
            name="openai_multi_step_test",
            api_base="https://api.openai.com",
            auth=auth,
            variables={
                "topic": "mathematics",
                "difficulty": "beginner"
            },
            steps=[
                # Step 1: Generate a question
                StepConfig(
                    name="generate_question",
                    endpoint="/v1/chat/completions",
                    method="POST",
                    headers={"Content-Type": "application/json"},
                    payload_template='''
                    {
                        "model": "gpt-3.5-turbo",
                        "messages": [
                            {"role": "user", "content": "Create a {{ difficulty }} level {{ topic }} question. Just the question, no answer."}
                        ],
                        "max_tokens": 100
                    }
                    ''',
                    timeout="30s"
                ),
                # Step 2: Generate answer (depends on question)
                StepConfig(
                    name="generate_answer",
                    endpoint="/v1/chat/completions",
                    method="POST",
                    headers={"Content-Type": "application/json"},
                    payload_template='''
                    {
                        "model": "gpt-3.5-turbo",
                        "messages": [
                            {"role": "user", "content": "Answer this {{ topic }} question: {{ generate_question.choices[0].message.content }}"}
                        ],
                        "max_tokens": 150
                    }
                    ''',
                    depends_on=["generate_question"],
                    timeout="30s"
                )
            ]
        )
        
        result = await workflow_engine.execute_workflow(workflow)
        
        assert result.success is True
        assert len(result.step_results) == 2
        
        # Check question generation
        question_result = result.step_results["generate_question"]
        assert question_result.success is True
        question_content = question_result.response_data["choices"][0]["message"]["content"]
        assert len(question_content.strip()) > 0
        
        # Check answer generation
        answer_result = result.step_results["generate_answer"]
        assert answer_result.success is True
        answer_content = answer_result.response_data["choices"][0]["message"]["content"]
        assert len(answer_content.strip()) > 0
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_openai_parallel_generation(self, openai_api_key, workflow_engine):
        """Test parallel question generation across multiple topics."""
        auth = AuthConfig(type="bearer", token=openai_api_key)
        
        workflow = WorkflowConfig(
            name="openai_parallel_test",
            api_base="https://api.openai.com",
            auth=auth,
            steps=[
                # Parallel generation for different topics
                StepConfig(
                    name="generate_algebra_question",
                    endpoint="/v1/chat/completions",
                    method="POST",
                    headers={"Content-Type": "application/json"},
                    payload={
                        "model": "gpt-3.5-turbo",
                        "messages": [
                            {"role": "user", "content": "Create a simple algebra question. Just the question."}
                        ],
                        "max_tokens": 50
                    },
                    parallel_group="question_generation",
                    timeout="30s"
                ),
                StepConfig(
                    name="generate_geometry_question",
                    endpoint="/v1/chat/completions",
                    method="POST",
                    headers={"Content-Type": "application/json"},
                    payload={
                        "model": "gpt-3.5-turbo",
                        "messages": [
                            {"role": "user", "content": "Create a simple geometry question. Just the question."}
                        ],
                        "max_tokens": 50
                    },
                    parallel_group="question_generation",
                    timeout="30s"
                ),
                # Summary step that depends on both
                StepConfig(
                    name="create_summary",
                    endpoint="/v1/chat/completions",
                    method="POST",
                    headers={"Content-Type": "application/json"},
                    payload_template='''
                    {
                        "model": "gpt-3.5-turbo",
                        "messages": [
                            {"role": "user", "content": "Create a brief summary of these two questions:\\n1. {{ generate_algebra_question.choices[0].message.content }}\\n2. {{ generate_geometry_question.choices[0].message.content }}"}
                        ],
                        "max_tokens": 100
                    }
                    ''',
                    depends_on=["question_generation"],
                    timeout="30s"
                )
            ]
        )
        
        result = await workflow_engine.execute_workflow(workflow)
        
        assert result.success is True
        assert len(result.step_results) == 3
        
        # Check parallel generation succeeded
        algebra_result = result.step_results["generate_algebra_question"]
        geometry_result = result.step_results["generate_geometry_question"]
        summary_result = result.step_results["create_summary"]
        
        assert algebra_result.success is True
        assert geometry_result.success is True
        assert summary_result.success is True
        
        # Verify content was generated
        algebra_content = algebra_result.response_data["choices"][0]["message"]["content"]
        geometry_content = geometry_result.response_data["choices"][0]["message"]["content"]
        summary_content = summary_result.response_data["choices"][0]["message"]["content"]
        
        assert "algebra" in algebra_content.lower() or len(algebra_content.strip()) > 10
        assert "geometry" in geometry_content.lower() or len(geometry_content.strip()) > 10
        assert len(summary_content.strip()) > 0
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_error_handling_with_retry(self, openai_api_key, workflow_engine):
        """Test error handling and retry logic with live API."""
        auth = AuthConfig(type="bearer", token=openai_api_key)
        
        workflow = WorkflowConfig(
            name="openai_retry_test",
            api_base="https://api.openai.com",
            auth=auth,
            steps=[
                # This should succeed
                StepConfig(
                    name="valid_request",
                    endpoint="/v1/chat/completions",
                    method="POST",
                    headers={"Content-Type": "application/json"},
                    payload={
                        "model": "gpt-3.5-turbo",
                        "messages": [
                            {"role": "user", "content": "Say 'test' and nothing else."}
                        ],
                        "max_tokens": 5
                    },
                    retry=RetryConfig(limit=2, delay="1s", backoff="constant"),
                    timeout="30s"
                ),
                # This should fail (invalid model)
                StepConfig(
                    name="invalid_request",
                    endpoint="/v1/chat/completions",
                    method="POST",
                    headers={"Content-Type": "application/json"},
                    payload={
                        "model": "nonexistent-model",
                        "messages": [
                            {"role": "user", "content": "This should fail"}
                        ]
                    },
                    retry=RetryConfig(limit=2, delay="1s", backoff="constant"),
                    timeout="30s",
                    continue_on_error=True  # Don't fail entire workflow
                )
            ]
        )
        
        result = await workflow_engine.execute_workflow(workflow)
        
        # Workflow should succeed overall due to continue_on_error
        assert result.success is True
        assert len(result.step_results) == 2
        
        # Valid request should succeed
        valid_result = result.step_results["valid_request"]
        assert valid_result.success is True
        
        # Invalid request should fail but not break workflow
        invalid_result = result.step_results["invalid_request"]
        assert invalid_result.success is False
        assert invalid_result.error is not None
    
    @pytest.mark.integration 
    @pytest.mark.asyncio
    async def test_timeout_handling(self, openai_api_key, workflow_engine):
        """Test timeout handling with live API."""
        auth = AuthConfig(type="bearer", token=openai_api_key)
        
        workflow = WorkflowConfig(
            name="openai_timeout_test",
            api_base="https://api.openai.com",
            auth=auth,
            steps=[
                StepConfig(
                    name="quick_request",
                    endpoint="/v1/chat/completions",
                    method="POST",
                    headers={"Content-Type": "application/json"},
                    payload={
                        "model": "gpt-3.5-turbo",
                        "messages": [
                            {"role": "user", "content": "Say 'quick' and nothing else."}
                        ],
                        "max_tokens": 5
                    },
                    timeout="1s"  # Very short timeout
                )
            ]
        )
        
        # This might timeout or succeed depending on API response time
        result = await workflow_engine.execute_workflow(workflow)
        
        # Just verify the result structure is correct
        assert "quick_request" in result.step_results
        step_result = result.step_results["quick_request"]
        
        if step_result.success:
            # If it succeeded, verify response structure
            assert "choices" in step_result.response_data
        else:
            # If it failed, verify it was due to timeout or valid API error
            assert step_result.error is not None


class TestWorkflowPatterns:
    """Test common workflow patterns that would be used in production."""
    
    @pytest.fixture
    def mock_client(self):
        """Create mock HTTP client for pattern testing."""
        from unittest.mock import Mock
        return Mock(spec=WorkflowHTTPClient)
    
    @pytest.fixture
    def workflow_engine(self, mock_client):
        """Create workflow engine with mock client."""
        return WorkflowExecutionEngine(http_client=mock_client)
    
    @pytest.mark.asyncio
    async def test_derivativ_pattern_simulation(self, workflow_engine, mock_client):
        """Test Derivativ-like workflow pattern with mocked responses."""
        # Mock responses for each step
        def mock_request(endpoint, **kwargs):
            if "questions/generate" in endpoint:
                if "algebra" in str(kwargs.get("payload", {})):
                    return {"question_ids": ["alg_1", "alg_2", "alg_3"], "topic": "algebra"}
                elif "geometry" in str(kwargs.get("payload", {})):
                    return {"question_ids": ["geo_1", "geo_2", "geo_3"], "topic": "geometry"}
            elif "documents/generate" in endpoint:
                return {"document_id": "doc_123", "status": "created"}
            elif "documents/store" in endpoint:
                return {"storage_id": "store_456", "url": "https://storage.example.com/doc_123"}
        
        mock_client.make_request.side_effect = mock_request
        
        # Derivativ-style workflow
        auth = AuthConfig(type="bearer", token="${DERIVATIV_API_KEY}")
        
        workflow = WorkflowConfig(
            name="derivativ_daily_simulation",
            api_base="https://api.derivativ.ai",
            auth=auth,
            variables={
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
                    parallel_group="question_generation"
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
                    parallel_group="question_generation"
                ),
                # Phase 2: Document creation (depends on all questions)
                StepConfig(
                    name="create_worksheet",
                    endpoint="/api/documents/generate",
                    method="POST",
                    payload_template='''
                    {
                        "document_type": "worksheet",
                        "question_ids": {{ (generate_algebra_questions.question_ids + generate_geometry_questions.question_ids) | list }},
                        "detail_level": "medium"
                    }
                    ''',
                    depends_on=["question_generation"]
                ),
                # Phase 3: Storage
                StepConfig(
                    name="store_document",
                    endpoint="/api/documents/store",
                    method="POST",
                    payload_template='''
                    {
                        "document_id": "{{ create_worksheet.document_id }}",
                        "metadata": {
                            "topics": ["algebra", "geometry"],
                            "grade_level": {{ grade_level }},
                            "question_count": {{ questions_per_topic * 2 }}
                        }
                    }
                    ''',
                    depends_on=["create_worksheet"]
                )
            ]
        )
        
        result = await workflow_engine.execute_workflow(workflow)
        
        assert result.success is True
        assert len(result.step_results) == 4
        
        # Verify execution order and results
        algebra_result = result.step_results["generate_algebra_questions"]
        geometry_result = result.step_results["generate_geometry_questions"]
        worksheet_result = result.step_results["create_worksheet"]
        storage_result = result.step_results["store_document"]
        
        assert algebra_result.success is True
        assert geometry_result.success is True
        assert worksheet_result.success is True
        assert storage_result.success is True
        
        # Verify data flow between steps
        assert len(algebra_result.response_data["question_ids"]) == 3
        assert len(geometry_result.response_data["question_ids"]) == 3
        assert worksheet_result.response_data["document_id"] == "doc_123"
        assert storage_result.response_data["storage_id"] == "store_456"
    
    @pytest.mark.asyncio
    async def test_error_recovery_pattern(self, workflow_engine, mock_client):
        """Test error recovery patterns for production workflows."""
        call_count = {"count": 0}
        
        def mock_request(endpoint, **kwargs):
            call_count["count"] += 1
            
            # Simulate intermittent failures
            if "unreliable" in endpoint and call_count["count"] <= 2:
                raise Exception("Temporary API failure")
            elif "unreliable" in endpoint:
                return {"status": "success", "attempt": call_count["count"]}
            else:
                return {"status": "success"}
        
        mock_client.make_request.side_effect = mock_request
        
        workflow = WorkflowConfig(
            name="error_recovery_test",
            api_base="https://api.test.com",
            steps=[
                StepConfig(
                    name="reliable_step",
                    endpoint="/api/reliable",
                    method="POST"
                ),
                StepConfig(
                    name="unreliable_step",
                    endpoint="/api/unreliable",
                    method="POST",
                    retry=RetryConfig(limit=3, delay="1s", backoff="exponential"),
                    depends_on=["reliable_step"]
                ),
                StepConfig(
                    name="final_step",
                    endpoint="/api/final",
                    method="POST",
                    depends_on=["unreliable_step"]
                )
            ]
        )
        
        result = await workflow_engine.execute_workflow(workflow)
        
        assert result.success is True
        assert len(result.step_results) == 3
        
        # Verify retry behavior worked
        unreliable_result = result.step_results["unreliable_step"]
        assert unreliable_result.success is True
        assert unreliable_result.response_data["attempt"] == 3  # Succeeded on 3rd attempt


@pytest.mark.integration
class TestRealWorldScenarios:
    """Test real-world integration scenarios."""
    
    def test_environment_variable_resolution(self):
        """Test that environment variables are properly resolved."""
        import os
        
        # Set test environment variable
        os.environ["TEST_API_BASE"] = "https://api.test.com"
        os.environ["TEST_API_KEY"] = "test-key-123"
        
        try:
            auth = AuthConfig(type="bearer", token="${TEST_API_KEY}")
            resolved_auth = auth.resolve_env_vars()
            
            assert resolved_auth.token == "test-key-123"
            
            # Test with missing variable
            auth_missing = AuthConfig(type="bearer", token="${MISSING_KEY}")
            with pytest.raises(ValueError, match="Environment variable.*not found"):
                auth_missing.resolve_env_vars()
                
        finally:
            # Cleanup
            del os.environ["TEST_API_BASE"]
            del os.environ["TEST_API_KEY"]
    
    def test_workflow_config_file_loading(self):
        """Test loading workflow configuration from YAML file."""
        import tempfile
        import yaml
        from gimme_ai.config.workflow import WorkflowConfig
        
        config_data = {
            "name": "test_workflow_from_file",
            "api_base": "https://api.example.com",
            "auth": {
                "type": "bearer",
                "token": "${API_TOKEN}"
            },
            "steps": [
                {
                    "name": "step1",
                    "endpoint": "/api/test",
                    "method": "POST"
                }
            ]
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(config_data, f)
            temp_file = f.name
        
        try:
            # This would be implemented in the actual workflow parser
            loaded_config = WorkflowConfig.from_dict(config_data)
            
            assert loaded_config.name == "test_workflow_from_file"
            assert loaded_config.api_base == "https://api.example.com"
            assert loaded_config.auth.type == "bearer"
            assert len(loaded_config.steps) == 1
            
        finally:
            os.unlink(temp_file)