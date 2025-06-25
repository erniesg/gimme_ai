"""
Production-ready testing fixtures and utilities for gimme_ai workflows.
Provides isolated testing environments with proper mock/staging setup.
"""

import os
import json
import tempfile
import asyncio
from typing import Dict, Any, Optional, List, ContextManager
from contextlib import asynccontextmanager, contextmanager
from unittest.mock import Mock, patch
from dataclasses import dataclass
from pathlib import Path

from ..config.secrets import SecretsManager, SecretBackend
from ..config.workflow import WorkflowConfig
from ..http.workflow_client import WorkflowHTTPClient
from ..workflows.execution_engine import WorkflowExecutionEngine


@dataclass
class TestEnvironment:
    """Test environment configuration."""
    name: str
    secrets: Dict[str, str]
    temp_dir: Path
    cleanup_callbacks: List[callable]


class MockAPIServer:
    """Mock API server for testing workflows without external dependencies."""
    
    def __init__(self, port: int = 8080):
        self.port = port
        self.responses: Dict[str, Any] = {}
        self.requests_log: List[Dict[str, Any]] = []
        self.running = False
    
    def add_response(self, endpoint: str, method: str = "GET", response: Dict[str, Any] = None, status_code: int = 200):
        """Add a mock response for an endpoint."""
        key = f"{method}:{endpoint}"
        self.responses[key] = {
            "status_code": status_code,
            "response": response or {"status": "success"},
            "headers": {"Content-Type": "application/json"}
        }
    
    def add_openai_response(self, content: str = "Mock OpenAI response", tokens: int = 10):
        """Add a mock OpenAI API response."""
        self.add_response("/v1/chat/completions", "POST", {
            "choices": [{"message": {"content": content}}],
            "usage": {"total_tokens": tokens}
        })
    
    def add_replicate_response(self, image_url: str = "https://mock.replicate.com/image.png"):
        """Add a mock Replicate API response with polling."""
        # Initial prediction creation
        self.add_response("/v1/predictions", "POST", {
            "id": "mock-prediction-123",
            "status": "starting",
            "urls": {"get": "https://api.replicate.com/v1/predictions/mock-prediction-123"}
        })
        
        # Polling responses
        self.add_response("/v1/predictions/mock-prediction-123", "GET", {
            "id": "mock-prediction-123", 
            "status": "succeeded",
            "output": [image_url]
        })
    
    def add_elevenlabs_response(self, audio_data: bytes = b"mock-audio-data"):
        """Add a mock ElevenLabs API response."""
        self.add_response("/v1/text-to-speech/21m00Tcm4TlvDq8ikWAM", "POST", 
                         response=None, status_code=200)
    
    @asynccontextmanager 
    async def run(self):
        """Run the mock server."""
        try:
            # Patch both requests.request and requests.Session methods
            self.running = True
            with patch('requests.request', side_effect=self._handle_request), \
                 patch('requests.Session.request', side_effect=self._handle_request):
                yield self
        finally:
            self.running = False
    
    def _handle_request(self, method: str, url: str, **kwargs):
        """Handle mocked requests."""
        from urllib.parse import urlparse
        parsed = urlparse(url)
        endpoint = parsed.path
        key = f"{method}:{endpoint}"
        
        # Log the request
        self.requests_log.append({
            "method": method,
            "url": url,
            "endpoint": endpoint,
            "headers": kwargs.get("headers", {}),
            "data": kwargs.get("json", kwargs.get("data"))
        })
        
        # Return mock response
        if key in self.responses:
            mock_response = Mock()
            response_data = self.responses[key]
            mock_response.status_code = response_data["status_code"]
            mock_response.headers = response_data["headers"]
            mock_response.json.return_value = response_data["response"]
            mock_response.content = json.dumps(response_data["response"]).encode()
            mock_response.raise_for_status.return_value = None
            return mock_response
        else:
            # Return 404 for unmocked endpoints
            mock_response = Mock()
            mock_response.status_code = 404
            mock_response.json.return_value = {"error": f"Mock endpoint not found: {key}"}
            return mock_response


class WorkflowTestFixture:
    """Test fixture for workflow execution with proper isolation."""
    
    def __init__(self, 
                 environment: str = "test",
                 use_mock_apis: bool = True,
                 use_real_secrets: bool = False):
        self.environment = environment
        self.use_mock_apis = use_mock_apis
        self.use_real_secrets = use_real_secrets
        self.test_env: Optional[TestEnvironment] = None
        self.mock_server: Optional[MockAPIServer] = None
        self.secrets_manager: Optional[SecretsManager] = None
    
    @asynccontextmanager
    async def setup(self):
        """Set up isolated test environment."""
        # Create temporary directory
        temp_dir = Path(tempfile.mkdtemp(prefix="gimme_ai_test_"))
        
        try:
            # Set up secrets
            if self.use_real_secrets:
                self.secrets_manager = SecretsManager(
                    backend=SecretBackend.ENVIRONMENT,
                    environment=self.environment
                )
            else:
                # Create mock secrets
                test_secrets = {
                    "OPENAI_API_KEY": "sk-test" + "0" * 44,
                    "REPLICATE_API_TOKEN": "r8_test" + "0" * 36,
                    "ELEVENLABS_API_KEY": "test-elevenlabs-key",
                    "CLOUDFLARE_ACCOUNT_ID": "test-account-id",
                    "R2_ACCESS_KEY_ID": "test-access-key",
                    "R2_SECRET_ACCESS_KEY": "test-secret-key",
                    "GIMME_ADMIN_PASSWORD": "test-admin-password"
                }
                
                # Write test env file
                test_env_file = temp_dir / ".env.test"
                with open(test_env_file, 'w') as f:
                    for key, value in test_secrets.items():
                        f.write(f"{key}={value}\n")
                
                self.secrets_manager = SecretsManager(
                    backend=SecretBackend.ENV_FILE,
                    environment="test",
                    env_file=str(test_env_file)
                )
            
            # Set up test environment
            self.test_env = TestEnvironment(
                name=self.environment,
                secrets=self.secrets_manager.export_for_workflow([
                    "OPENAI_API_KEY", "REPLICATE_API_TOKEN", "ELEVENLABS_API_KEY"
                ]),
                temp_dir=temp_dir,
                cleanup_callbacks=[]
            )
            
            # Set up mock API server if needed
            if self.use_mock_apis:
                self.mock_server = MockAPIServer()
                # Pre-configure common responses
                self.mock_server.add_openai_response()
                self.mock_server.add_replicate_response()
                self.mock_server.add_elevenlabs_response()
                
                async with self.mock_server.run():
                    yield self
            else:
                yield self
                
        finally:
            # Cleanup
            if self.test_env:
                for cleanup_func in self.test_env.cleanup_callbacks:
                    try:
                        cleanup_func()
                    except Exception as e:
                        print(f"Cleanup error: {e}")
            
            # Remove temp directory
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)
    
    def create_test_workflow(self, workflow_type: str = "minimal") -> WorkflowConfig:
        """Create a test workflow configuration."""
        if workflow_type == "minimal":
            config_data = {
                "name": "test_minimal_workflow",
                "api_base": "https://api.openai.com" if not self.use_mock_apis else "http://localhost:8080",
                "variables": {"test_input": "sustainable living"},
                "steps": [
                    {
                        "name": "generate_content",
                        "endpoint": "/v1/chat/completions",
                        "method": "POST",
                        "auth": {"type": "bearer", "token": "${OPENAI_API_KEY}"},
                        "headers": {"Content-Type": "application/json"},
                        "payload_template": """{
                            "model": "gpt-3.5-turbo",
                            "messages": [{"role": "user", "content": "Write 50 words about {{ test_input }}"}],
                            "max_tokens": 100
                        }""",
                        "extract_fields": {
                            "content": "choices.0.message.content",
                            "tokens": "usage.total_tokens"
                        }
                    }
                ]
            }
        elif workflow_type == "multi_api":
            config_data = {
                "name": "test_multi_api_workflow",
                "api_base": "https://api.openai.com" if not self.use_mock_apis else "http://localhost:8080",
                "variables": {"topic": "artificial intelligence"},
                "steps": [
                    {
                        "name": "generate_script",
                        "endpoint": "/v1/chat/completions",
                        "method": "POST",
                        "auth": {"type": "bearer", "token": "${OPENAI_API_KEY}"},
                        "headers": {"Content-Type": "application/json"},
                        "payload_template": """{
                            "model": "gpt-3.5-turbo",
                            "messages": [{"role": "user", "content": "Write a script about {{ topic }}"}],
                            "max_tokens": 200
                        }""",
                        "extract_fields": {"script": "choices.0.message.content"}
                    },
                    {
                        "name": "generate_image",
                        "api_base": "https://api.replicate.com" if not self.use_mock_apis else "http://localhost:8080",
                        "endpoint": "/v1/predictions",
                        "method": "POST",
                        "auth": {"type": "api_key", "header_name": "Authorization", "api_key": "Token ${REPLICATE_API_TOKEN}"},
                        "depends_on": ["generate_script"],
                        "poll_for_completion": True,
                        "poll_interval": "1s",
                        "poll_timeout": "30s",
                        "completion_field": "status",
                        "completion_values": ["succeeded"],
                        "extract_fields": {"image_url": "output.0"}
                    }
                ]
            }
        else:
            raise ValueError(f"Unknown workflow type: {workflow_type}")
        
        return WorkflowConfig.from_dict(config_data)
    
    async def execute_workflow(self, workflow: WorkflowConfig) -> Any:
        """Execute a workflow with proper environment setup."""
        # Resolve environment variables
        resolved_workflow = workflow.resolve_env_vars()
        
        # Create HTTP client
        client = WorkflowHTTPClient(base_url=workflow.api_base)
        if not self.use_mock_apis:
            client.setup_r2_client()
        
        # Create execution engine
        engine = WorkflowExecutionEngine(http_client=client)
        
        # Execute workflow
        return await engine.execute_workflow(resolved_workflow)
    
    def get_mock_requests(self) -> List[Dict[str, Any]]:
        """Get logged mock API requests for verification."""
        return self.mock_server.requests_log if self.mock_server else []


@contextmanager
def isolated_test_env(environment: str = "test", **kwargs):
    """Context manager for isolated testing environment."""
    fixture = WorkflowTestFixture(environment=environment, **kwargs)
    
    async def _run_fixture():
        async with fixture.setup():
            return fixture
    
    # Run async context manager in sync context
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        fixture_instance = loop.run_until_complete(_run_fixture())
        yield fixture_instance
    finally:
        loop.close()


# Pre-configured test fixtures
def test_minimal_workflow():
    """Quick test with minimal OpenAI workflow."""
    return isolated_test_env(environment="test", use_mock_apis=True, use_real_secrets=False)


def test_multi_api_workflow():
    """Test with multi-API workflow (OpenAI + Replicate)."""
    return isolated_test_env(environment="test", use_mock_apis=True, use_real_secrets=False)


def test_live_api_workflow():
    """Test with real APIs (requires actual API keys)."""
    return isolated_test_env(environment="test", use_mock_apis=False, use_real_secrets=True)