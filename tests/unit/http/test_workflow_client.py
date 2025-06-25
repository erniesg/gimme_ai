"""Test workflow HTTP client with multiple authentication types."""

import pytest
import responses
import json
from unittest.mock import patch, Mock
from gimme_ai.http.workflow_client import (
    WorkflowHTTPClient,
    AuthenticationError,
    RetryExhaustedError,
    TimeoutError
)
from gimme_ai.config.workflow import AuthConfig, RetryConfig


class TestWorkflowHTTPClient:
    """Test HTTP client for workflow execution."""
    
    def setup_method(self):
        """Set up test client."""
        self.base_url = "https://api.example.com"
        self.client = WorkflowHTTPClient(base_url=self.base_url)
    
    @responses.activate
    def test_make_request_no_auth(self):
        """Test making request without authentication."""
        responses.add(
            responses.POST,
            f"{self.base_url}/api/test",
            json={"success": True},
            status=200
        )
        
        response = self.client.make_request(
            endpoint="/api/test",
            method="POST",
            payload={"data": "test"}
        )
        
        assert response["success"] is True
    
    @responses.activate
    def test_make_request_bearer_auth(self):
        """Test making request with bearer token authentication."""
        auth = AuthConfig(type="bearer", token="test-token")
        self.client.set_auth(auth)
        
        def check_auth_header(request):
            assert request.headers["Authorization"] == "Bearer test-token"
            return (200, {}, json.dumps({"success": True}))
        
        responses.add_callback(
            responses.POST,
            f"{self.base_url}/api/test",
            callback=check_auth_header
        )
        
        response = self.client.make_request(
            endpoint="/api/test",
            method="POST",
            payload={"data": "test"}
        )
        
        assert response["success"] is True
    
    @responses.activate
    def test_make_request_api_key_auth(self):
        """Test making request with API key authentication."""
        auth = AuthConfig(
            type="api_key",
            header_name="X-API-Key",
            api_key="test-api-key"
        )
        self.client.set_auth(auth)
        
        def check_auth_header(request):
            assert request.headers["X-API-Key"] == "test-api-key"
            return (200, {}, json.dumps({"success": True}))
        
        responses.add_callback(
            responses.POST,
            f"{self.base_url}/api/test",
            callback=check_auth_header
        )
        
        response = self.client.make_request(
            endpoint="/api/test",
            method="POST",
            payload={"data": "test"}
        )
        
        assert response["success"] is True
    
    @responses.activate
    def test_make_request_basic_auth(self):
        """Test making request with basic authentication."""
        auth = AuthConfig(
            type="basic",
            username="testuser",
            password="testpass"
        )
        self.client.set_auth(auth)
        
        def check_auth_header(request):
            import base64
            expected = base64.b64encode(b"testuser:testpass").decode()
            assert request.headers["Authorization"] == f"Basic {expected}"
            return (200, {}, json.dumps({"success": True}))
        
        responses.add_callback(
            responses.POST,
            f"{self.base_url}/api/test",
            callback=check_auth_header
        )
        
        response = self.client.make_request(
            endpoint="/api/test",
            method="POST",
            payload={"data": "test"}
        )
        
        assert response["success"] is True
    
    @responses.activate
    def test_make_request_custom_auth(self):
        """Test making request with custom headers authentication."""
        auth = AuthConfig(
            type="custom",
            custom_headers={
                "Authorization": "Token secret-token",
                "X-Client-ID": "client-123"
            }
        )
        self.client.set_auth(auth)
        
        def check_auth_headers(request):
            assert request.headers["Authorization"] == "Token secret-token"
            assert request.headers["X-Client-ID"] == "client-123"
            return (200, {}, json.dumps({"success": True}))
        
        responses.add_callback(
            responses.POST,
            f"{self.base_url}/api/test",
            callback=check_auth_headers
        )
        
        response = self.client.make_request(
            endpoint="/api/test",
            method="POST",
            payload={"data": "test"}
        )
        
        assert response["success"] is True
    
    @responses.activate
    def test_make_request_with_custom_headers(self):
        """Test making request with additional custom headers."""
        responses.add(
            responses.POST,
            f"{self.base_url}/api/test",
            json={"success": True},
            status=200
        )
        
        def check_headers(request):
            assert request.headers["Content-Type"] == "application/json"
            assert request.headers["X-Custom-Header"] == "custom-value"
            return (200, {}, json.dumps({"success": True}))
        
        responses.add_callback(
            responses.POST,
            f"{self.base_url}/api/test",
            callback=check_headers
        )
        
        response = self.client.make_request(
            endpoint="/api/test",
            method="POST",
            payload={"data": "test"},
            headers={
                "Content-Type": "application/json",
                "X-Custom-Header": "custom-value"
            }
        )
        
        assert response["success"] is True
    
    @responses.activate
    def test_retry_on_server_error(self):
        """Test retry logic on server errors."""
        retry_config = RetryConfig(limit=3, delay="1s", backoff="constant")
        self.client.set_retry_config(retry_config)
        
        # First two calls fail, third succeeds
        responses.add(responses.POST, f"{self.base_url}/api/test", status=500)
        responses.add(responses.POST, f"{self.base_url}/api/test", status=500)
        responses.add(
            responses.POST,
            f"{self.base_url}/api/test",
            json={"success": True},
            status=200
        )
        
        with patch('time.sleep'):  # Mock sleep to speed up test
            response = self.client.make_request(
                endpoint="/api/test",
                method="POST",
                payload={"data": "test"}
            )
        
        assert response["success"] is True
        assert len(responses.calls) == 3
    
    @responses.activate
    def test_retry_exhausted(self):
        """Test retry exhaustion on persistent errors."""
        retry_config = RetryConfig(limit=2, delay="1s", backoff="constant")
        self.client.set_retry_config(retry_config)
        
        # All calls fail
        responses.add(responses.POST, f"{self.base_url}/api/test", status=500)
        responses.add(responses.POST, f"{self.base_url}/api/test", status=500)
        responses.add(responses.POST, f"{self.base_url}/api/test", status=500)
        
        with patch('time.sleep'):
            with pytest.raises(RetryExhaustedError):
                self.client.make_request(
                    endpoint="/api/test",
                    method="POST",
                    payload={"data": "test"}
                )
        
        assert len(responses.calls) == 3  # Initial + 2 retries
    
    @responses.activate
    def test_no_retry_on_client_error(self):
        """Test no retry on client errors (4xx)."""
        retry_config = RetryConfig(limit=3, delay="1s")
        self.client.set_retry_config(retry_config)
        
        responses.add(responses.POST, f"{self.base_url}/api/test", status=400)
        
        with pytest.raises(Exception):  # Should raise immediately
            self.client.make_request(
                endpoint="/api/test",
                method="POST",
                payload={"data": "test"}
            )
        
        assert len(responses.calls) == 1  # No retries on 4xx
    
    @responses.activate
    def test_exponential_backoff(self):
        """Test exponential backoff retry strategy."""
        retry_config = RetryConfig(limit=3, delay="1s", backoff="exponential")
        self.client.set_retry_config(retry_config)
        
        responses.add(responses.POST, f"{self.base_url}/api/test", status=500)
        responses.add(responses.POST, f"{self.base_url}/api/test", status=500)
        responses.add(
            responses.POST,
            f"{self.base_url}/api/test",
            json={"success": True},
            status=200
        )
        
        with patch('time.sleep') as mock_sleep:
            response = self.client.make_request(
                endpoint="/api/test",
                method="POST",
                payload={"data": "test"}
            )
        
        # Check exponential backoff: 1s, 2s, 4s
        expected_delays = [1.0, 2.0]
        actual_delays = [call.args[0] for call in mock_sleep.call_args_list]
        assert actual_delays == expected_delays
    
    @responses.activate
    def test_linear_backoff(self):
        """Test linear backoff retry strategy."""
        retry_config = RetryConfig(limit=3, delay="1s", backoff="linear")
        self.client.set_retry_config(retry_config)
        
        responses.add(responses.POST, f"{self.base_url}/api/test", status=500)
        responses.add(responses.POST, f"{self.base_url}/api/test", status=500)
        responses.add(
            responses.POST,
            f"{self.base_url}/api/test",
            json={"success": True},
            status=200
        )
        
        with patch('time.sleep') as mock_sleep:
            response = self.client.make_request(
                endpoint="/api/test",
                method="POST",
                payload={"data": "test"}
            )
        
        # Check linear backoff: 1s, 2s, 3s
        expected_delays = [1.0, 2.0]
        actual_delays = [call.args[0] for call in mock_sleep.call_args_list]
        assert actual_delays == expected_delays
    
    @responses.activate
    def test_timeout_handling(self):
        """Test request timeout handling."""
        from requests.exceptions import Timeout
        
        def timeout_callback(request):
            raise Timeout("Request timed out")
        
        responses.add_callback(
            responses.POST,
            f"{self.base_url}/api/test",
            callback=timeout_callback
        )
        
        with pytest.raises(TimeoutError):
            self.client.make_request(
                endpoint="/api/test",
                method="POST",
                payload={"data": "test"},
                timeout=5
            )
    
    def test_auth_config_validation(self):
        """Test authentication configuration validation."""
        # Valid bearer auth
        auth = AuthConfig(type="bearer", token="test-token")
        self.client.set_auth(auth)
        
        # Invalid auth type
        with pytest.raises(ValueError, match="Unsupported auth type"):
            invalid_auth = Mock()
            invalid_auth.type = "invalid"
            self.client.set_auth(invalid_auth)
    
    @responses.activate
    def test_response_json_parsing(self):
        """Test JSON response parsing."""
        responses.add(
            responses.POST,
            f"{self.base_url}/api/test",
            json={"message": "success", "data": {"id": 123}},
            status=200
        )
        
        response = self.client.make_request(
            endpoint="/api/test",
            method="POST",
            payload={"data": "test"}
        )
        
        assert response["message"] == "success"
        assert response["data"]["id"] == 123
    
    @responses.activate
    def test_response_text_fallback(self):
        """Test fallback to text when JSON parsing fails."""
        responses.add(
            responses.POST,
            f"{self.base_url}/api/test",
            body="Plain text response",
            status=200,
            content_type="text/plain"
        )
        
        response = self.client.make_request(
            endpoint="/api/test",
            method="POST",
            payload={"data": "test"}
        )
        
        assert response == "Plain text response"
    
    @responses.activate
    def test_environment_variable_resolution(self):
        """Test environment variable resolution in auth tokens."""
        import os
        os.environ["TEST_TOKEN"] = "resolved-token-value"
        
        auth = AuthConfig(type="bearer", token="${TEST_TOKEN}")
        resolved_auth = auth.resolve_env_vars()
        self.client.set_auth(resolved_auth)
        
        def check_resolved_token(request):
            assert request.headers["Authorization"] == "Bearer resolved-token-value"
            return (200, {}, json.dumps({"success": True}))
        
        responses.add_callback(
            responses.POST,
            f"{self.base_url}/api/test",
            callback=check_resolved_token
        )
        
        response = self.client.make_request(
            endpoint="/api/test",
            method="POST",
            payload={"data": "test"}
        )
        
        assert response["success"] is True
        
        # Cleanup
        del os.environ["TEST_TOKEN"]


class TestHTTPMethods:
    """Test different HTTP methods."""
    
    def setup_method(self):
        """Set up test client."""
        self.client = WorkflowHTTPClient(base_url="https://api.example.com")
    
    @responses.activate
    def test_get_request(self):
        """Test GET request."""
        responses.add(
            responses.GET,
            "https://api.example.com/api/data",
            json={"data": "retrieved"},
            status=200
        )
        
        response = self.client.make_request(
            endpoint="/api/data",
            method="GET"
        )
        
        assert response["data"] == "retrieved"
    
    @responses.activate
    def test_put_request(self):
        """Test PUT request."""
        responses.add(
            responses.PUT,
            "https://api.example.com/api/data/123",
            json={"updated": True},
            status=200
        )
        
        response = self.client.make_request(
            endpoint="/api/data/123",
            method="PUT",
            payload={"name": "updated"}
        )
        
        assert response["updated"] is True
    
    @responses.activate
    def test_delete_request(self):
        """Test DELETE request."""
        responses.add(
            responses.DELETE,
            "https://api.example.com/api/data/123",
            json={"deleted": True},
            status=200
        )
        
        response = self.client.make_request(
            endpoint="/api/data/123",
            method="DELETE"
        )
        
        assert response["deleted"] is True


class TestRealAPIPatterns:
    """Test patterns for real API integrations."""
    
    def setup_method(self):
        """Set up test client."""
        self.client = WorkflowHTTPClient(base_url="https://api.openai.com")
    
    @responses.activate
    def test_openai_api_pattern(self):
        """Test OpenAI API integration pattern."""
        auth = AuthConfig(type="bearer", token="sk-test-token")
        self.client.set_auth(auth)
        
        def check_openai_request(request):
            assert request.headers["Authorization"] == "Bearer sk-test-token"
            assert request.headers["Content-Type"] == "application/json"
            
            body = json.loads(request.body)
            assert body["model"] == "gpt-3.5-turbo"
            assert len(body["messages"]) == 1
            
            return (200, {}, json.dumps({
                "id": "chatcmpl-123",
                "choices": [{
                    "message": {"content": "Hello! How can I help?"}
                }]
            }))
        
        responses.add_callback(
            responses.POST,
            "https://api.openai.com/v1/chat/completions",
            callback=check_openai_request
        )
        
        response = self.client.make_request(
            endpoint="/v1/chat/completions",
            method="POST",
            headers={"Content-Type": "application/json"},
            payload={
                "model": "gpt-3.5-turbo",
                "messages": [{"role": "user", "content": "Hello"}]
            }
        )
        
        assert response["id"] == "chatcmpl-123"
        assert response["choices"][0]["message"]["content"] == "Hello! How can I help?"
    
    @responses.activate
    def test_replicate_api_pattern(self):
        """Test Replicate API integration pattern."""
        auth = AuthConfig(
            type="api_key",
            header_name="Authorization",
            api_key="Token r8_test-token"
        )
        self.client.set_auth(auth)
        
        def check_replicate_request(request):
            assert request.headers["Authorization"] == "Token r8_test-token"
            assert request.headers["Content-Type"] == "application/json"
            
            body = json.loads(request.body)
            assert "input" in body
            
            return (201, {}, json.dumps({
                "id": "pred-123",
                "status": "starting",
                "urls": {"get": "https://api.replicate.com/predictions/pred-123"}
            }))
        
        responses.add_callback(
            responses.POST,
            "https://api.openai.com/v1/predictions",
            callback=check_replicate_request
        )
        
        response = self.client.make_request(
            endpoint="/v1/predictions",
            method="POST",
            headers={"Content-Type": "application/json"},
            payload={
                "version": "model-version-id",
                "input": {"prompt": "A beautiful landscape"}
            }
        )
        
        assert response["id"] == "pred-123"
        assert response["status"] == "starting"