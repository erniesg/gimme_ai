"""Test workflow configuration schema validation."""

import pytest
from pydantic import ValidationError
from gimme_ai.config.workflow import (
    WorkflowConfig,
    StepConfig,
    AuthConfig,
    RetryConfig,
    validate_workflow_config,
    resolve_workflow_dependencies
)


class TestAuthConfig:
    """Test authentication configuration validation."""
    
    def test_bearer_auth_valid(self):
        """Test valid bearer token authentication."""
        auth = AuthConfig(
            type="bearer",
            token="${OPENAI_API_KEY}"
        )
        assert auth.type == "bearer"
        assert auth.token == "${OPENAI_API_KEY}"
    
    def test_api_key_auth_valid(self):
        """Test valid API key authentication."""
        auth = AuthConfig(
            type="api_key",
            header_name="X-API-Key",
            api_key="${REPLICATE_TOKEN}"
        )
        assert auth.type == "api_key"
        assert auth.header_name == "X-API-Key"
        assert auth.api_key == "${REPLICATE_TOKEN}"
    
    def test_basic_auth_valid(self):
        """Test valid basic authentication."""
        auth = AuthConfig(
            type="basic",
            username="admin",
            password="${ADMIN_PASSWORD}"
        )
        assert auth.type == "basic"
        assert auth.username == "admin"
        assert auth.password == "${ADMIN_PASSWORD}"
    
    def test_custom_auth_valid(self):
        """Test valid custom header authentication."""
        auth = AuthConfig(
            type="custom",
            custom_headers={
                "Authorization": "Token ${API_TOKEN}",
                "X-Client-ID": "${CLIENT_ID}"
            }
        )
        assert auth.type == "custom"
        assert len(auth.custom_headers) == 2
    
    def test_no_auth_valid(self):
        """Test no authentication configuration."""
        auth = AuthConfig(type="none")
        assert auth.type == "none"
    
    def test_bearer_auth_missing_token(self):
        """Test bearer auth validation fails without token."""
        with pytest.raises(ValidationError, match="Bearer auth requires.*token"):
            AuthConfig(type="bearer")
    
    def test_api_key_auth_missing_fields(self):
        """Test API key auth validation fails without required fields."""
        with pytest.raises(ValidationError):
            AuthConfig(type="api_key", api_key="token")  # Missing header_name
        
        with pytest.raises(ValidationError):
            AuthConfig(type="api_key", header_name="X-API-Key")  # Missing api_key
    
    def test_basic_auth_missing_fields(self):
        """Test basic auth validation fails without credentials."""
        with pytest.raises(ValidationError):
            AuthConfig(type="basic", username="admin")  # Missing password


class TestRetryConfig:
    """Test retry configuration validation."""
    
    def test_retry_config_valid(self):
        """Test valid retry configuration."""
        retry = RetryConfig(
            limit=3,
            delay="10s",
            backoff="exponential",
            timeout="5m"
        )
        assert retry.limit == 3
        assert retry.delay == "10s"
        assert retry.backoff == "exponential"
        assert retry.timeout == "5m"
    
    def test_retry_config_defaults(self):
        """Test retry configuration with defaults."""
        retry = RetryConfig(limit=2, delay="5s")
        assert retry.limit == 2
        assert retry.delay == "5s"
        assert retry.backoff == "exponential"  # default
        assert retry.timeout is None
    
    def test_retry_limit_validation(self):
        """Test retry limit validation."""
        with pytest.raises(ValidationError, match="greater than or equal to 1"):
            RetryConfig(limit=0, delay="5s")
        
        with pytest.raises(ValidationError, match="less than or equal to 10"):
            RetryConfig(limit=15, delay="5s")
    
    def test_backoff_type_validation(self):
        """Test backoff type validation."""
        with pytest.raises(ValidationError):
            RetryConfig(limit=3, delay="5s", backoff="invalid")


class TestStepConfig:
    """Test step configuration validation."""
    
    def test_step_config_minimal(self):
        """Test minimal valid step configuration."""
        step = StepConfig(
            name="test_step",
            endpoint="/api/test"
        )
        assert step.name == "test_step"
        assert step.endpoint == "/api/test"
        assert step.method == "POST"  # default
    
    def test_step_config_full(self):
        """Test complete step configuration."""
        step = StepConfig(
            name="generate_questions",
            endpoint="/api/questions/generate",
            method="POST",
            depends_on=["init_step"],
            parallel_group="question_generation",
            max_parallel=3,
            headers={"Content-Type": "application/json"},
            payload_template='{"topic": "{{ topic }}", "count": {{ count }}}',
            retry=RetryConfig(limit=3, delay="10s"),
            timeout="5m",
            continue_on_error=False
        )
        
        assert step.name == "generate_questions"
        assert step.depends_on == ["init_step"]
        assert step.parallel_group == "question_generation"
        assert step.max_parallel == 3
        assert step.retry.limit == 3
    
    def test_step_name_validation(self):
        """Test step name validation."""
        with pytest.raises(ValidationError, match="name.*empty"):
            StepConfig(name="", endpoint="/api/test")
        
        with pytest.raises(ValidationError, match="name.*alphanumeric"):
            StepConfig(name="invalid-step-name!", endpoint="/api/test")
    
    def test_step_endpoint_validation(self):
        """Test endpoint validation."""
        with pytest.raises(ValidationError, match="start with"):
            StepConfig(name="test", endpoint="api/test")
    
    def test_step_method_validation(self):
        """Test HTTP method validation."""
        valid_methods = ["GET", "POST", "PUT", "DELETE", "PATCH"]
        for method in valid_methods:
            step = StepConfig(name="test", endpoint="/api/test", method=method)
            assert step.method == method
        
        with pytest.raises(ValidationError):
            StepConfig(name="test", endpoint="/api/test", method="INVALID")


class TestWorkflowConfig:
    """Test complete workflow configuration validation."""
    
    def test_workflow_config_minimal(self):
        """Test minimal valid workflow configuration."""
        config = WorkflowConfig(
            name="test_workflow",
            api_base="https://api.example.com",
            steps=[
                StepConfig(name="step1", endpoint="/api/test")
            ]
        )
        
        assert config.name == "test_workflow"
        assert config.api_base == "https://api.example.com"
        assert len(config.steps) == 1
    
    def test_workflow_config_full(self):
        """Test complete workflow configuration."""
        config = WorkflowConfig(
            name="derivativ_daily",
            description="Daily question generation for Cambridge IGCSE",
            schedule="0 18 * * *",  # 2 AM SGT
            timezone="Asia/Singapore",
            api_base="https://api.derivativ.ai",
            auth=AuthConfig(type="bearer", token="${DERIVATIV_API_KEY}"),
            variables={
                "topics": ["algebra", "geometry"],
                "questions_per_topic": 8
            },
            steps=[
                StepConfig(name="generate_algebra", endpoint="/api/questions/generate"),
                StepConfig(name="generate_geometry", endpoint="/api/questions/generate"),
                StepConfig(
                    name="create_worksheet",
                    endpoint="/api/documents/generate",
                    depends_on=["generate_algebra", "generate_geometry"]
                )
            ]
        )
        
        assert config.name == "derivativ_daily"
        assert config.schedule == "0 18 * * *"
        assert config.timezone == "Asia/Singapore"
        assert config.auth.type == "bearer"
        assert len(config.steps) == 3
    
    def test_workflow_name_validation(self):
        """Test workflow name validation."""
        with pytest.raises(ValidationError, match="name.*empty"):
            WorkflowConfig(name="", api_base="https://api.test.com", steps=[])
        
        # Test name length limit
        long_name = "a" * 65
        with pytest.raises(ValidationError, match="name.*63 characters"):
            WorkflowConfig(name=long_name, api_base="https://api.test.com", steps=[])
    
    def test_api_base_validation(self):
        """Test API base URL validation."""
        with pytest.raises(ValidationError, match="api_base.*valid URL"):
            WorkflowConfig(
                name="test",
                api_base="not-a-url",
                steps=[StepConfig(name="step1", endpoint="/api/test")]
            )
    
    def test_cron_schedule_validation(self):
        """Test cron schedule validation."""
        # Valid cron expressions
        valid_crons = [
            "0 18 * * *",      # Daily at 6 PM UTC
            "*/15 * * * *",    # Every 15 minutes
            "0 0 1 * *",       # First day of every month
            "0 9-17 * * 1-5"   # Business hours, weekdays
        ]
        
        for cron in valid_crons:
            config = WorkflowConfig(
                name="test",
                api_base="https://api.test.com",
                schedule=cron,
                steps=[StepConfig(name="step1", endpoint="/api/test")]
            )
            assert config.schedule == cron
        
        # Invalid cron expressions
        invalid_crons = [
            "invalid",
            "0 25 * * *",  # Invalid hour
            "60 * * * *",  # Invalid minute
        ]
        
        for cron in invalid_crons:
            with pytest.raises(ValidationError, match="(Cron schedule|Invalid.*field|Value error)"):
                WorkflowConfig(
                    name="test",
                    api_base="https://api.test.com",
                    schedule=cron,
                    steps=[StepConfig(name="step1", endpoint="/api/test")]
                )


class TestWorkflowValidation:
    """Test workflow validation functions."""
    
    def test_validate_workflow_config_success(self):
        """Test successful workflow validation."""
        config_data = {
            "name": "test_workflow",
            "api_base": "https://api.test.com",
            "steps": [
                {"name": "step1", "endpoint": "/api/test"}
            ]
        }
        
        issues = validate_workflow_config(config_data)
        assert len(issues) == 0
    
    def test_validate_workflow_config_failures(self):
        """Test workflow validation with errors."""
        config_data = {
            "name": "",  # Invalid name
            "api_base": "not-a-url",  # Invalid URL
            "steps": []  # Empty steps
        }
        
        issues = validate_workflow_config(config_data)
        assert len(issues) > 0
        assert any("name" in issue.lower() for issue in issues)
        assert any("api_base" in issue.lower() for issue in issues)


class TestDependencyResolution:
    """Test workflow dependency resolution."""
    
    def test_resolve_dependencies_sequential(self):
        """Test resolving sequential dependencies."""
        steps = [
            StepConfig(name="step3", endpoint="/api/3", depends_on=["step2"]),
            StepConfig(name="step1", endpoint="/api/1"),
            StepConfig(name="step2", endpoint="/api/2", depends_on=["step1"])
        ]
        
        resolved = resolve_workflow_dependencies(steps)
        
        # Should return 3 phases for sequential dependencies
        assert len(resolved) == 3
        
        # First phase should contain step1
        assert len(resolved[0]) == 1
        assert resolved[0][0].name == "step1"
        
        # Second phase should contain step2
        assert len(resolved[1]) == 1
        assert resolved[1][0].name == "step2"
        
        # Third phase should contain step3
        assert len(resolved[2]) == 1
        assert resolved[2][0].name == "step3"
    
    def test_resolve_dependencies_parallel(self):
        """Test resolving parallel groups."""
        steps = [
            StepConfig(name="step1", endpoint="/api/1", parallel_group="group1"),
            StepConfig(name="step2", endpoint="/api/2", parallel_group="group1"),
            StepConfig(name="step3", endpoint="/api/3", depends_on=["group1"])
        ]
        
        resolved = resolve_workflow_dependencies(steps)
        
        # Should return 2 phases
        assert len(resolved) == 2
        
        # First phase should contain the parallel group steps
        assert len(resolved[0]) == 2
        step_names = {step.name for step in resolved[0]}
        assert step_names == {"step1", "step2"}
        
        # Both steps should be in the same parallel group
        for step in resolved[0]:
            assert step.parallel_group == "group1"
        
        # Second phase should contain step3
        assert len(resolved[1]) == 1
        assert resolved[1][0].name == "step3"
        assert "group1" in resolved[1][0].depends_on
    
    def test_circular_dependency_detection(self):
        """Test circular dependency detection."""
        steps = [
            StepConfig(name="step1", endpoint="/api/1", depends_on=["step2"]),
            StepConfig(name="step2", endpoint="/api/2", depends_on=["step1"])
        ]
        
        with pytest.raises(ValueError, match="Circular dependency"):
            resolve_workflow_dependencies(steps)
    
    def test_missing_dependency_detection(self):
        """Test missing dependency detection."""
        steps = [
            StepConfig(name="step1", endpoint="/api/1", depends_on=["nonexistent"])
        ]
        
        with pytest.raises(ValueError, match="Missing dependency"):
            resolve_workflow_dependencies(steps)


class TestEnvironmentVariableSubstitution:
    """Test environment variable substitution in configurations."""
    
    def test_env_var_substitution_in_auth(self):
        """Test environment variable substitution in auth config."""
        import os
        os.environ["TEST_API_KEY"] = "test-key-value"
        
        auth = AuthConfig(type="bearer", token="${TEST_API_KEY}")
        resolved_auth = auth.resolve_env_vars()
        
        assert resolved_auth.token == "test-key-value"
        
        # Cleanup
        del os.environ["TEST_API_KEY"]
    
    def test_env_var_substitution_missing(self):
        """Test handling of missing environment variables."""
        auth = AuthConfig(type="bearer", token="${MISSING_API_KEY}")
        
        with pytest.raises(ValueError, match="Environment variable.*not found"):
            auth.resolve_env_vars()