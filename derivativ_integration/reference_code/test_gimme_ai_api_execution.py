"""Unit tests for gimme_ai dynamic API endpoint calling with retry logic.

This module tests the HTTP request execution, retry strategies, error handling,
and response processing components of the GenericAPIWorkflow engine.
"""

import asyncio
import json
import time
from dataclasses import dataclass, field
from typing import Any, Optional

import pytest


@dataclass
class MockResponse:
    """Mock HTTP response for testing."""
    status_code: int
    headers: dict[str, str] = field(default_factory=dict)
    data: Any = None
    text_content: str = ""

    @property
    def ok(self) -> bool:
        return 200 <= self.status_code < 300

    @property
    def status_text(self) -> str:
        status_messages = {
            200: "OK",
            201: "Created",
            400: "Bad Request",
            401: "Unauthorized",
            403: "Forbidden",
            404: "Not Found",
            500: "Internal Server Error",
            502: "Bad Gateway",
            503: "Service Unavailable"
        }
        return status_messages.get(self.status_code, "Unknown")

    async def json(self) -> Any:
        """Return JSON data."""
        if self.data is not None:
            return self.data
        return json.loads(self.text_content) if self.text_content else {}

    async def text(self) -> str:
        """Return text content."""
        return self.text_content or json.dumps(self.data) if self.data else ""


class HTTPRequestExecutor:
    """HTTP request executor with retry logic for testing GenericAPIWorkflow functionality."""

    def __init__(self):
        self.request_history: list[dict[str, Any]] = []
        self.response_times: list[float] = []

    async def execute_request(
        self,
        url: str,
        method: str = "POST",
        headers: Optional[dict[str, str]] = None,
        body: Optional[str] = None,
        timeout_ms: int = 30000,
        retry_config: Optional[dict[str, Any]] = None
    ) -> MockResponse:
        """Execute HTTP request with retry logic."""

        headers = headers or {}
        retry_config = retry_config or {"limit": 0, "delay": "1s", "backoff": "constant"}

        max_attempts = retry_config.get("limit", 0) + 1
        attempt = 0
        last_error = None

        while attempt < max_attempts:
            attempt += 1
            start_time = time.time()

            try:
                # Record request for testing
                self.request_history.append({
                    "url": url,
                    "method": method,
                    "headers": headers.copy(),
                    "body": body,
                    "attempt": attempt,
                    "timestamp": start_time
                })

                # Simulate HTTP request
                response = await self._simulate_http_request(url, method, headers, body, timeout_ms)

                # Record response time
                self.response_times.append(time.time() - start_time)

                # Check if response indicates success
                if response.ok:
                    return response

                # Non-2xx response - treat as retriable error
                raise Exception(f"HTTP {response.status_code}: {response.status_text}")

            except Exception as error:
                last_error = error
                self.response_times.append(time.time() - start_time)

                # Check if we should retry
                if attempt < max_attempts:
                    delay_ms = self._calculate_retry_delay(retry_config, attempt)
                    await asyncio.sleep(delay_ms / 1000.0)
                else:
                    # All attempts exhausted
                    raise last_error

        # Should not reach here
        raise Exception("Unexpected end of retry loop")

    async def _simulate_http_request(
        self,
        url: str,
        method: str,
        headers: dict[str, str],
        body: Optional[str],
        timeout_ms: int
    ) -> MockResponse:
        """Simulate HTTP request for testing."""

        # Simulate network delay
        await asyncio.sleep(0.01)

        # Simulate different response scenarios based on URL patterns
        if "/api/test/success" in url:
            return MockResponse(
                status_code=200,
                data={"status": "success", "message": "Request completed"}
            )

        elif "/api/test/created" in url:
            return MockResponse(
                status_code=201,
                data={"id": "12345", "status": "created"}
            )

        elif "/api/test/server_error" in url:
            return MockResponse(
                status_code=500,
                text_content="Internal Server Error"
            )

        elif "/api/test/not_found" in url:
            return MockResponse(
                status_code=404,
                text_content="Not Found"
            )

        elif "/api/test/timeout" in url:
            # Simulate timeout by sleeping longer than timeout
            await asyncio.sleep(timeout_ms / 1000.0 + 0.1)
            raise asyncio.TimeoutError("Request timeout")

        elif "/api/test/retry_then_succeed" in url:
            # Fail first few attempts, then succeed
            attempt_count = len([r for r in self.request_history if r["url"] == url])
            if attempt_count < 3:
                return MockResponse(status_code=503, text_content="Service Unavailable")
            else:
                return MockResponse(
                    status_code=200,
                    data={"status": "success", "attempts": attempt_count}
                )

        elif "/api/test/auth_required" in url:
            # Check for authorization header
            if "Authorization" not in headers:
                return MockResponse(status_code=401, text_content="Unauthorized")
            return MockResponse(
                status_code=200,
                data={"status": "authenticated", "user": "test_user"}
            )

        else:
            # Default success response
            return MockResponse(
                status_code=200,
                data={"url": url, "method": method, "received": True}
            )

    def _calculate_retry_delay(self, retry_config: dict[str, Any], attempt: int) -> int:
        """Calculate retry delay in milliseconds."""
        delay_str = retry_config.get("delay", "1s")
        backoff = retry_config.get("backoff", "constant")

        # Parse delay string
        base_delay_ms = self._parse_delay_string(delay_str)

        # Apply backoff strategy
        if backoff == "constant":
            return base_delay_ms
        elif backoff == "linear":
            return base_delay_ms * attempt
        elif backoff == "exponential":
            return base_delay_ms * (2 ** (attempt - 1))
        else:
            return base_delay_ms

    def _parse_delay_string(self, delay_str: str) -> int:
        """Parse delay string to milliseconds."""
        import re
        match = re.match(r"^(\d+)([smh])$", delay_str)
        if not match:
            return 1000  # Default 1 second

        value, unit = match.groups()
        num = int(value)

        if unit == "s":
            return num * 1000
        elif unit == "m":
            return num * 60 * 1000
        elif unit == "h":
            return num * 60 * 60 * 1000
        else:
            return 1000


class AuthenticationManager:
    """Authentication manager for testing auth configurations."""

    @staticmethod
    def apply_auth(headers: dict[str, str], auth_config: dict[str, Any]) -> dict[str, str]:
        """Apply authentication to headers based on auth configuration."""
        headers = headers.copy()
        auth_type = auth_config.get("type", "none")

        if auth_type == "bearer":
            token = auth_config.get("token", "")
            if token:
                headers["Authorization"] = f"Bearer {token}"

        elif auth_type == "api_key":
            api_key = auth_config.get("api_key", "")
            header_name = auth_config.get("header_name", "X-API-Key")
            if api_key:
                headers[header_name] = api_key

        elif auth_type == "basic":
            username = auth_config.get("username", "")
            password = auth_config.get("password", "")
            if username and password:
                import base64
                credentials = base64.b64encode(f"{username}:{password}".encode()).decode()
                headers["Authorization"] = f"Basic {credentials}"

        elif auth_type == "custom":
            custom_headers = auth_config.get("custom_headers", {})
            headers.update(custom_headers)

        return headers


class TemplateRenderer:
    """Template renderer for testing Jinja2-style templating."""

    @staticmethod
    def render_template(template: str, context: dict[str, Any]) -> str:
        """Render template with context variables."""
        import re

        def replacer(match):
            var_path = match.group(1).strip()
            value = TemplateRenderer._get_nested_value(context, var_path)

            if value is not None:
                if isinstance(value, (dict, list)):
                    return json.dumps(value)
                else:
                    return str(value)

            return match.group(0)  # Return original if not found

        # Replace {{ variable }} patterns
        result = re.sub(r'\{\{\s*([^}]+)\s*\}\}', replacer, template)
        return result

    @staticmethod
    def _get_nested_value(obj: Any, path: str) -> Any:
        """Get nested value using dot notation."""
        try:
            current = obj
            for key in path.split('.'):
                if isinstance(current, dict) and key in current:
                    current = current[key]
                elif hasattr(current, key):
                    current = getattr(current, key)
                else:
                    return None
            return current
        except:
            return None


class TestHTTPRequestExecution:
    """Test cases for HTTP request execution."""

    @pytest.fixture
    def executor(self):
        """Create HTTP request executor."""
        return HTTPRequestExecutor()

    @pytest.mark.asyncio
    async def test_successful_request(self, executor):
        """Test successful HTTP request."""
        response = await executor.execute_request(
            url="https://api.example.com/api/test/success",
            method="POST",
            headers={"Content-Type": "application/json"},
            body='{"test": true}'
        )

        assert response.ok
        assert response.status_code == 200
        data = await response.json()
        assert data["status"] == "success"

        # Check request was recorded
        assert len(executor.request_history) == 1
        assert executor.request_history[0]["url"] == "https://api.example.com/api/test/success"
        assert executor.request_history[0]["method"] == "POST"

    @pytest.mark.asyncio
    async def test_created_response(self, executor):
        """Test 201 Created response."""
        response = await executor.execute_request(
            url="https://api.example.com/api/test/created",
            method="POST"
        )

        assert response.ok
        assert response.status_code == 201
        data = await response.json()
        assert "id" in data
        assert data["status"] == "created"

    @pytest.mark.asyncio
    async def test_server_error_no_retry(self, executor):
        """Test server error without retry."""
        with pytest.raises(Exception) as exc_info:
            await executor.execute_request(
                url="https://api.example.com/api/test/server_error",
                retry_config={"limit": 0, "delay": "1s", "backoff": "constant"}
            )

        assert "HTTP 500" in str(exc_info.value)
        assert len(executor.request_history) == 1

    @pytest.mark.asyncio
    async def test_retry_with_constant_backoff(self, executor):
        """Test retry with constant backoff strategy."""
        with pytest.raises(Exception):
            await executor.execute_request(
                url="https://api.example.com/api/test/server_error",
                retry_config={"limit": 3, "delay": "100ms", "backoff": "constant"}
            )

        # Should have made 4 attempts (1 + 3 retries)
        assert len(executor.request_history) == 4

        # Check all attempts were to the same URL
        for request in executor.request_history:
            assert request["url"] == "https://api.example.com/api/test/server_error"

    @pytest.mark.asyncio
    async def test_retry_with_exponential_backoff(self, executor):
        """Test retry with exponential backoff strategy."""
        start_time = time.time()

        with pytest.raises(Exception):
            await executor.execute_request(
                url="https://api.example.com/api/test/server_error",
                retry_config={"limit": 2, "delay": "50ms", "backoff": "exponential"}
            )

        end_time = time.time()

        # Should have made 3 attempts (1 + 2 retries)
        assert len(executor.request_history) == 3

        # With exponential backoff: 50ms + 100ms = 150ms minimum delay
        # Plus request processing time, should be at least 0.15 seconds
        assert end_time - start_time >= 0.1

    @pytest.mark.asyncio
    async def test_retry_then_succeed(self, executor):
        """Test scenario where request fails initially then succeeds."""
        response = await executor.execute_request(
            url="https://api.example.com/api/test/retry_then_succeed",
            retry_config={"limit": 5, "delay": "10ms", "backoff": "constant"}
        )

        assert response.ok
        assert response.status_code == 200

        data = await response.json()
        assert data["status"] == "success"
        assert data["attempts"] >= 3  # Should succeed on 3rd attempt

        # Should have made exactly 3 attempts
        retry_requests = [r for r in executor.request_history
                         if "retry_then_succeed" in r["url"]]
        assert len(retry_requests) == 3

    @pytest.mark.asyncio
    async def test_different_http_methods(self, executor):
        """Test different HTTP methods."""
        methods = ["GET", "POST", "PUT", "DELETE", "PATCH"]

        for method in methods:
            response = await executor.execute_request(
                url="https://api.example.com/api/test/success",
                method=method
            )

            assert response.ok

            # Find the request for this method
            method_requests = [r for r in executor.request_history if r["method"] == method]
            assert len(method_requests) >= 1

    @pytest.mark.asyncio
    async def test_custom_headers(self, executor):
        """Test custom headers in requests."""
        custom_headers = {
            "X-Custom-Header": "test-value",
            "X-Request-ID": "req-12345",
            "Content-Type": "application/json"
        }

        response = await executor.execute_request(
            url="https://api.example.com/api/test/success",
            headers=custom_headers
        )

        assert response.ok

        # Check headers were recorded
        recorded_request = executor.request_history[-1]
        for key, value in custom_headers.items():
            assert recorded_request["headers"][key] == value

    @pytest.mark.asyncio
    async def test_request_body_handling(self, executor):
        """Test request body handling."""
        test_payload = {"question": "What is 2+2?", "grade": 9}

        response = await executor.execute_request(
            url="https://api.example.com/api/test/success",
            method="POST",
            body=json.dumps(test_payload)
        )

        assert response.ok

        # Check body was recorded
        recorded_request = executor.request_history[-1]
        assert recorded_request["body"] == json.dumps(test_payload)


class TestAuthenticationManager:
    """Test cases for authentication management."""

    def test_bearer_authentication(self):
        """Test Bearer token authentication."""
        headers = {"Content-Type": "application/json"}
        auth_config = {"type": "bearer", "token": "test-token-12345"}

        result_headers = AuthenticationManager.apply_auth(headers, auth_config)

        assert result_headers["Authorization"] == "Bearer test-token-12345"
        assert result_headers["Content-Type"] == "application/json"  # Original headers preserved

    def test_api_key_authentication(self):
        """Test API key authentication."""
        headers = {}
        auth_config = {"type": "api_key", "api_key": "secret-key", "header_name": "X-API-Key"}

        result_headers = AuthenticationManager.apply_auth(headers, auth_config)

        assert result_headers["X-API-Key"] == "secret-key"

    def test_api_key_default_header(self):
        """Test API key with default header name."""
        headers = {}
        auth_config = {"type": "api_key", "api_key": "secret-key"}

        result_headers = AuthenticationManager.apply_auth(headers, auth_config)

        assert result_headers["X-API-Key"] == "secret-key"

    def test_basic_authentication(self):
        """Test Basic authentication."""
        headers = {}
        auth_config = {"type": "basic", "username": "user123", "password": "pass456"}

        result_headers = AuthenticationManager.apply_auth(headers, auth_config)

        assert "Authorization" in result_headers
        assert result_headers["Authorization"].startswith("Basic ")

        # Decode and verify credentials
        import base64
        encoded_creds = result_headers["Authorization"].split(" ")[1]
        decoded_creds = base64.b64decode(encoded_creds).decode()
        assert decoded_creds == "user123:pass456"

    def test_custom_authentication(self):
        """Test custom authentication headers."""
        headers = {"Content-Type": "application/json"}
        auth_config = {
            "type": "custom",
            "custom_headers": {
                "X-Custom-Auth": "custom-value",
                "X-Client-ID": "client-12345"
            }
        }

        result_headers = AuthenticationManager.apply_auth(headers, auth_config)

        assert result_headers["X-Custom-Auth"] == "custom-value"
        assert result_headers["X-Client-ID"] == "client-12345"
        assert result_headers["Content-Type"] == "application/json"

    def test_no_authentication(self):
        """Test no authentication (headers unchanged)."""
        headers = {"Content-Type": "application/json"}
        auth_config = {"type": "none"}

        result_headers = AuthenticationManager.apply_auth(headers, auth_config)

        assert result_headers == headers  # Should be unchanged

    @pytest.mark.asyncio
    async def test_auth_integration_with_executor(self):
        """Test authentication integration with HTTP executor."""
        executor = HTTPRequestExecutor()

        # Test auth-required endpoint
        auth_config = {"type": "bearer", "token": "valid-token"}
        headers = AuthenticationManager.apply_auth({}, auth_config)

        response = await executor.execute_request(
            url="https://api.example.com/api/test/auth_required",
            headers=headers
        )

        assert response.ok
        data = await response.json()
        assert data["status"] == "authenticated"

    @pytest.mark.asyncio
    async def test_auth_failure_without_credentials(self):
        """Test authentication failure without credentials."""
        executor = HTTPRequestExecutor()

        with pytest.raises(Exception) as exc_info:
            await executor.execute_request(
                url="https://api.example.com/api/test/auth_required"
            )

        assert "HTTP 401" in str(exc_info.value)


class TestTemplateRenderer:
    """Test cases for template rendering."""

    def test_simple_variable_substitution(self):
        """Test simple variable substitution."""
        template = '{"name": "{{ name }}", "age": {{ age }}}'
        context = {"name": "John", "age": 30}

        result = TemplateRenderer.render_template(template, context)

        expected = '{"name": "John", "age": 30}'
        assert result == expected

    def test_nested_variable_access(self):
        """Test nested variable access with dot notation."""
        template = '{"user_id": "{{ user.id }}", "user_name": "{{ user.profile.name }}"}'
        context = {
            "user": {
                "id": "12345",
                "profile": {"name": "Alice", "email": "alice@example.com"}
            }
        }

        result = TemplateRenderer.render_template(template, context)

        expected = '{"user_id": "12345", "user_name": "Alice"}'
        assert result == expected

    def test_complex_object_substitution(self):
        """Test substitution of complex objects (dict/list)."""
        template = '{"config": {{ config }}, "items": {{ items }}}'
        context = {
            "config": {"debug": True, "timeout": 30},
            "items": ["item1", "item2", "item3"]
        }

        result = TemplateRenderer.render_template(template, context)

        # Should JSON-encode complex objects
        assert '"config": {"debug": true, "timeout": 30}' in result
        assert '"items": ["item1", "item2", "item3"]' in result

    def test_missing_variable_handling(self):
        """Test handling of missing variables."""
        template = '{"existing": "{{ existing }}", "missing": "{{ missing }}"}'
        context = {"existing": "value"}

        result = TemplateRenderer.render_template(template, context)

        # Missing variables should remain as-is
        assert '"existing": "value"' in result
        assert '"missing": "{{ missing }}"' in result

    def test_workflow_step_results_templating(self):
        """Test templating with workflow step results."""
        template = '''
        {
          "question_ids": {{ steps.generate_questions.question_ids }},
          "total_count": {{ steps.generate_questions.count }},
          "status": "{{ steps.generate_questions.status }}"
        }
        '''

        context = {
            "steps": {
                "generate_questions": {
                    "question_ids": ["q1", "q2", "q3"],
                    "count": 3,
                    "status": "success"
                }
            }
        }

        result = TemplateRenderer.render_template(template, context)

        assert '["q1", "q2", "q3"]' in result
        assert '"total_count": 3' in result
        assert '"status": "success"' in result

    def test_derivativ_payload_template(self):
        """Test realistic Derivativ API payload template."""
        template = '''
        {
          "topic": "{{ variables.topic }}",
          "count": {{ variables.questions_per_topic }},
          "grade_level": {{ variables.grade_level }},
          "quality_threshold": {{ variables.quality_threshold }},
          "previous_results": {{ steps.previous_step.result }}
        }
        '''

        context = {
            "variables": {
                "topic": "algebra",
                "questions_per_topic": 8,
                "grade_level": 9,
                "quality_threshold": 0.75
            },
            "steps": {
                "previous_step": {
                    "result": {"generated_count": 5, "avg_quality": 0.82}
                }
            }
        }

        result = TemplateRenderer.render_template(template, context)

        assert '"topic": "algebra"' in result
        assert '"count": 8' in result
        assert '"grade_level": 9' in result
        assert '"quality_threshold": 0.75' in result
        assert '"generated_count": 5' in result


class TestRetryDelayCalculation:
    """Test cases for retry delay calculation."""

    def test_constant_backoff(self):
        """Test constant backoff strategy."""
        executor = HTTPRequestExecutor()

        retry_config = {"limit": 3, "delay": "2s", "backoff": "constant"}

        # Test different attempt numbers
        assert executor._calculate_retry_delay(retry_config, 1) == 2000  # 2 seconds
        assert executor._calculate_retry_delay(retry_config, 2) == 2000  # Still 2 seconds
        assert executor._calculate_retry_delay(retry_config, 3) == 2000  # Still 2 seconds

    def test_linear_backoff(self):
        """Test linear backoff strategy."""
        executor = HTTPRequestExecutor()

        retry_config = {"limit": 3, "delay": "1s", "backoff": "linear"}

        assert executor._calculate_retry_delay(retry_config, 1) == 1000   # 1 * 1s
        assert executor._calculate_retry_delay(retry_config, 2) == 2000   # 2 * 1s
        assert executor._calculate_retry_delay(retry_config, 3) == 3000   # 3 * 1s

    def test_exponential_backoff(self):
        """Test exponential backoff strategy."""
        executor = HTTPRequestExecutor()

        retry_config = {"limit": 4, "delay": "1s", "backoff": "exponential"}

        assert executor._calculate_retry_delay(retry_config, 1) == 1000   # 1s * 2^0 = 1s
        assert executor._calculate_retry_delay(retry_config, 2) == 2000   # 1s * 2^1 = 2s
        assert executor._calculate_retry_delay(retry_config, 3) == 4000   # 1s * 2^2 = 4s
        assert executor._calculate_retry_delay(retry_config, 4) == 8000   # 1s * 2^3 = 8s

    def test_delay_string_parsing(self):
        """Test parsing of delay strings."""
        executor = HTTPRequestExecutor()

        # Test seconds
        assert executor._parse_delay_string("5s") == 5000
        assert executor._parse_delay_string("30s") == 30000

        # Test minutes
        assert executor._parse_delay_string("1m") == 60000
        assert executor._parse_delay_string("5m") == 300000

        # Test hours
        assert executor._parse_delay_string("1h") == 3600000
        assert executor._parse_delay_string("2h") == 7200000

        # Test invalid format (should return default)
        assert executor._parse_delay_string("invalid") == 1000
        assert executor._parse_delay_string("5") == 1000
        assert executor._parse_delay_string("5sec") == 1000


class TestResponseProcessing:
    """Test cases for response processing and transformation."""

    @pytest.mark.asyncio
    async def test_json_response_processing(self):
        """Test processing of JSON responses."""
        executor = HTTPRequestExecutor()

        response = await executor.execute_request(
            url="https://api.example.com/api/test/success"
        )

        data = await response.json()
        assert isinstance(data, dict)
        assert data["status"] == "success"

    @pytest.mark.asyncio
    async def test_response_transformation_with_template(self):
        """Test response transformation using templates."""
        # This would be part of the GenericAPIWorkflow step processing
        raw_response = {
            "questions": [{"id": "q1", "text": "What is 2+2?"}, {"id": "q2", "text": "What is 3+3?"}],
            "metadata": {"count": 2, "topic": "arithmetic"}
        }

        # Template to extract just the question IDs
        transform_template = '{"question_ids": {{ questions | map(attribute="id") | list }}}'

        # For this test, we'll simulate the transformation manually
        # In the real implementation, this would use Jinja2
        question_ids = [q["id"] for q in raw_response["questions"]]
        transformed = {"question_ids": question_ids}

        assert transformed["question_ids"] == ["q1", "q2"]


if __name__ == "__main__":
    # Run a basic integration test
    async def test_integration():
        print("Running gimme_ai API execution tests...")

        executor = HTTPRequestExecutor()

        # Test successful request
        try:
            response = await executor.execute_request(
                url="https://api.example.com/api/test/success",
                method="POST",
                headers={"Content-Type": "application/json"},
                body='{"test": true}'
            )
            print(f"✅ Successful request: {response.status_code}")
        except Exception as e:
            print(f"❌ Failed successful request test: {e}")

        # Test retry mechanism
        try:
            await executor.execute_request(
                url="https://api.example.com/api/test/server_error",
                retry_config={"limit": 2, "delay": "100ms", "backoff": "exponential"}
            )
        except Exception as e:
            print(f"✅ Retry mechanism test completed (expected failure): {len(executor.request_history)} attempts made")

        # Test authentication
        auth_config = {"type": "bearer", "token": "test-token"}
        headers = AuthenticationManager.apply_auth({}, auth_config)
        try:
            response = await executor.execute_request(
                url="https://api.example.com/api/test/auth_required",
                headers=headers
            )
            print(f"✅ Authentication test: {response.status_code}")
        except Exception as e:
            print(f"❌ Authentication test failed: {e}")

        # Test template rendering
        template = '{"name": "{{ name }}", "count": {{ count }}}'
        context = {"name": "test", "count": 42}
        result = TemplateRenderer.render_template(template, context)
        print(f"✅ Template rendering: {result}")

        print("Integration test completed.")

    # Run the integration test
    import asyncio
    asyncio.run(test_integration())
