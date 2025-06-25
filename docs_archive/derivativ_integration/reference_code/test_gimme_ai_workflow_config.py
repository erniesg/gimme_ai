"""Unit tests for gimme_ai generic workflow configuration schema validation.

This module tests the configuration schema and validation for the enhanced
gimme_ai workflow engine that supports generic API orchestration.
"""

from typing import Any

import yaml


class WorkflowConfigValidator:
    """Validator for generic workflow configuration schema."""

    @staticmethod
    def validate_workflow_config(config: dict[str, Any]) -> list[str]:
        """Validate a workflow configuration and return list of errors."""
        errors = []

        # Required top-level fields
        required_fields = ['name', 'api_base', 'steps']
        for field in required_fields:
            if field not in config:
                errors.append(f"Missing required field: {field}")

        # Validate name
        if 'name' in config:
            if not isinstance(config['name'], str) or not config['name'].strip():
                errors.append("Field 'name' must be a non-empty string")

        # Validate api_base
        if 'api_base' in config:
            api_base = config['api_base']
            if not isinstance(api_base, str):
                errors.append("Field 'api_base' must be a string")
            elif not (api_base.startswith('http://') or api_base.startswith('https://')):
                errors.append("Field 'api_base' must be a valid HTTP/HTTPS URL")

        # Validate schedule (optional)
        if 'schedule' in config:
            schedule_errors = WorkflowConfigValidator._validate_cron_schedule(config['schedule'])
            errors.extend(schedule_errors)

        # Validate timezone (optional)
        if 'timezone' in config:
            tz_errors = WorkflowConfigValidator._validate_timezone(config['timezone'])
            errors.extend(tz_errors)

        # Validate auth (optional)
        if 'auth' in config:
            auth_errors = WorkflowConfigValidator._validate_auth_config(config['auth'])
            errors.extend(auth_errors)

        # Validate steps
        if 'steps' in config:
            if not isinstance(config['steps'], list):
                errors.append("Field 'steps' must be a list")
            elif len(config['steps']) == 0:
                errors.append("Field 'steps' cannot be empty")
            else:
                step_errors = WorkflowConfigValidator._validate_steps(config['steps'])
                errors.extend(step_errors)

        return errors

    @staticmethod
    def _validate_cron_schedule(schedule: str) -> list[str]:
        """Validate cron schedule format."""
        errors = []

        if not isinstance(schedule, str):
            errors.append("Schedule must be a string")
            return errors

        parts = schedule.strip().split()
        if len(parts) != 5:
            errors.append("Cron schedule must have exactly 5 fields (minute hour day month weekday)")
            return errors

        # Basic validation for each field
        minute, hour, day, month, weekday = parts

        # Minute validation (0-59)
        if not WorkflowConfigValidator._validate_cron_field(minute, 0, 59):
            errors.append("Invalid minute in cron schedule (must be 0-59 or valid cron expression)")

        # Hour validation (0-23)
        if not WorkflowConfigValidator._validate_cron_field(hour, 0, 23):
            errors.append("Invalid hour in cron schedule (must be 0-23 or valid cron expression)")

        # Day validation (1-31)
        if not WorkflowConfigValidator._validate_cron_field(day, 1, 31):
            errors.append("Invalid day in cron schedule (must be 1-31 or valid cron expression)")

        # Month validation (1-12)
        if not WorkflowConfigValidator._validate_cron_field(month, 1, 12):
            errors.append("Invalid month in cron schedule (must be 1-12 or valid cron expression)")

        # Weekday validation (0-7, where 0 and 7 are Sunday)
        if not WorkflowConfigValidator._validate_cron_field(weekday, 0, 7):
            errors.append("Invalid weekday in cron schedule (must be 0-7 or valid cron expression)")

        return errors

    @staticmethod
    def _validate_cron_field(field: str, min_val: int, max_val: int) -> bool:
        """Validate a single cron field."""
        # Allow wildcard
        if field == '*':
            return True

        # Allow ranges (e.g., 1-5)
        if '-' in field:
            try:
                start, end = field.split('-', 1)
                start_num = int(start)
                end_num = int(end)
                return min_val <= start_num <= max_val and min_val <= end_num <= max_val and start_num <= end_num
            except ValueError:
                return False

        # Allow step values (e.g., */5, 1-10/2)
        if '/' in field:
            try:
                base, step = field.split('/', 1)
                step_num = int(step)
                if base == '*':
                    return step_num > 0
                elif '-' in base:
                    start, end = base.split('-', 1)
                    start_num = int(start)
                    end_num = int(end)
                    return min_val <= start_num <= max_val and min_val <= end_num <= max_val and step_num > 0
                else:
                    base_num = int(base)
                    return min_val <= base_num <= max_val and step_num > 0
            except ValueError:
                return False

        # Allow comma-separated values (e.g., 1,3,5)
        if ',' in field:
            try:
                values = [int(v.strip()) for v in field.split(',')]
                return all(min_val <= v <= max_val for v in values)
            except ValueError:
                return False

        # Allow single numeric values
        try:
            num = int(field)
            return min_val <= num <= max_val
        except ValueError:
            return False

    @staticmethod
    def _validate_timezone(timezone: str) -> list[str]:
        """Validate timezone string."""
        errors = []

        if not isinstance(timezone, str):
            errors.append("Timezone must be a string")
            return errors

        # Common timezone validation
        valid_timezones = [
            'UTC', 'GMT',
            'Asia/Singapore', 'Asia/Hong_Kong', 'Asia/Tokyo',
            'America/New_York', 'America/Los_Angeles', 'America/Chicago',
            'Europe/London', 'Europe/Berlin', 'Europe/Paris'
        ]

        if timezone not in valid_timezones:
            errors.append(f"Unsupported timezone: {timezone}. Supported: {', '.join(valid_timezones)}")

        return errors

    @staticmethod
    def _validate_auth_config(auth: dict[str, Any]) -> list[str]:
        """Validate authentication configuration."""
        errors = []

        if not isinstance(auth, dict):
            errors.append("Auth configuration must be a dictionary")
            return errors

        # Validate auth type
        if 'type' not in auth:
            errors.append("Auth configuration must specify 'type'")
        else:
            valid_types = ['none', 'bearer', 'api_key', 'basic', 'custom']
            if auth['type'] not in valid_types:
                errors.append(f"Invalid auth type: {auth['type']}. Valid types: {', '.join(valid_types)}")

            # Type-specific validation
            if auth['type'] == 'bearer' and 'token' not in auth:
                errors.append("Bearer auth requires 'token' field")
            elif auth['type'] == 'api_key' and 'api_key' not in auth:
                errors.append("API key auth requires 'api_key' field")
            elif auth['type'] == 'basic':
                if 'username' not in auth or 'password' not in auth:
                    errors.append("Basic auth requires 'username' and 'password' fields")
            elif auth['type'] == 'custom' and 'custom_headers' not in auth:
                errors.append("Custom auth requires 'custom_headers' field")

        return errors

    @staticmethod
    def _validate_steps(steps: list[dict[str, Any]]) -> list[str]:
        """Validate workflow steps configuration."""
        errors = []
        step_names = set()

        for i, step in enumerate(steps):
            if not isinstance(step, dict):
                errors.append(f"Step {i} must be a dictionary")
                continue

            # Required fields for each step
            required_step_fields = ['name', 'endpoint']
            for field in required_step_fields:
                if field not in step:
                    errors.append(f"Step {i} missing required field: {field}")

            # Validate step name uniqueness
            if 'name' in step:
                if step['name'] in step_names:
                    errors.append(f"Duplicate step name: {step['name']}")
                step_names.add(step['name'])

            # Validate endpoint
            if 'endpoint' in step:
                if not isinstance(step['endpoint'], str) or not step['endpoint'].strip():
                    errors.append(f"Step {i} endpoint must be a non-empty string")

            # Validate HTTP method (optional)
            if 'method' in step:
                valid_methods = ['GET', 'POST', 'PUT', 'DELETE', 'PATCH']
                if step['method'] not in valid_methods:
                    errors.append(f"Step {i} invalid HTTP method: {step['method']}")

            # Validate retry configuration (optional)
            if 'retry' in step:
                retry_errors = WorkflowConfigValidator._validate_retry_config(step['retry'], i)
                errors.extend(retry_errors)

            # Validate dependencies (optional)
            if 'depends_on' in step:
                if not isinstance(step['depends_on'], list):
                    errors.append(f"Step {i} depends_on must be a list")

        # Validate dependency references
        for i, step in enumerate(steps):
            if 'depends_on' in step:
                for dep in step['depends_on']:
                    if dep not in step_names:
                        errors.append(f"Step {i} depends on non-existent step: {dep}")

        return errors

    @staticmethod
    def _validate_retry_config(retry: dict[str, Any], step_index: int) -> list[str]:
        """Validate retry configuration for a step."""
        errors = []

        if not isinstance(retry, dict):
            errors.append(f"Step {step_index} retry config must be a dictionary")
            return errors

        # Validate limit
        if 'limit' not in retry:
            errors.append(f"Step {step_index} retry config missing 'limit'")
        elif not isinstance(retry['limit'], int) or retry['limit'] < 0:
            errors.append(f"Step {step_index} retry limit must be a non-negative integer")

        # Validate delay
        if 'delay' not in retry:
            errors.append(f"Step {step_index} retry config missing 'delay'")
        elif not WorkflowConfigValidator._validate_duration_string(retry['delay']):
            errors.append(f"Step {step_index} retry delay must be a valid duration (e.g., '5s', '1m')")

        # Validate backoff strategy
        if 'backoff' in retry:
            valid_backoff = ['constant', 'linear', 'exponential']
            if retry['backoff'] not in valid_backoff:
                errors.append(f"Step {step_index} invalid backoff strategy: {retry['backoff']}")

        return errors

    @staticmethod
    def _validate_duration_string(duration: str) -> bool:
        """Validate duration string format (e.g., '5s', '1m', '2h')."""
        if not isinstance(duration, str):
            return False

        import re
        pattern = r'^\d+[smh]$'
        return bool(re.match(pattern, duration))


class TestWorkflowConfigValidation:
    """Test cases for workflow configuration validation."""

    def test_valid_minimal_config(self):
        """Test minimal valid configuration."""
        config = {
            "name": "test-workflow",
            "api_base": "https://api.example.com",
            "steps": [
                {
                    "name": "step1",
                    "endpoint": "/api/test"
                }
            ]
        }

        errors = WorkflowConfigValidator.validate_workflow_config(config)
        assert errors == []

    def test_valid_complete_config(self):
        """Test complete valid configuration with all optional fields."""
        config = {
            "name": "derivativ-daily-generation",
            "description": "Daily question generation for Cambridge IGCSE",
            "schedule": "0 18 * * *",
            "timezone": "Asia/Singapore",
            "api_base": "https://api.derivativ.ai",
            "auth": {
                "type": "bearer",
                "token": "${DERIVATIV_API_KEY}"
            },
            "variables": {
                "topics": ["algebra", "geometry"],
                "questions_per_topic": 8
            },
            "steps": [
                {
                    "name": "generate_algebra",
                    "endpoint": "/api/questions/generate",
                    "method": "POST",
                    "parallel_group": "question_generation",
                    "retry": {
                        "limit": 3,
                        "delay": "10s",
                        "backoff": "exponential"
                    },
                    "payload_template": "{}",
                    "timeout": "5m"
                },
                {
                    "name": "create_document",
                    "endpoint": "/api/documents/generate",
                    "method": "POST",
                    "depends_on": ["generate_algebra"],
                    "retry": {
                        "limit": 2,
                        "delay": "5s",
                        "backoff": "linear"
                    }
                }
            ]
        }

        errors = WorkflowConfigValidator.validate_workflow_config(config)
        assert errors == []

    def test_missing_required_fields(self):
        """Test validation with missing required fields."""
        config = {
            "description": "Missing name and api_base"
        }

        errors = WorkflowConfigValidator.validate_workflow_config(config)
        assert "Missing required field: name" in errors
        assert "Missing required field: api_base" in errors
        assert "Missing required field: steps" in errors

    def test_invalid_api_base(self):
        """Test validation with invalid API base URL."""
        config = {
            "name": "test",
            "api_base": "not-a-url",
            "steps": [{"name": "step1", "endpoint": "/test"}]
        }

        errors = WorkflowConfigValidator.validate_workflow_config(config)
        assert any("api_base" in error and "HTTP" in error for error in errors)

    def test_invalid_cron_schedule(self):
        """Test validation with invalid cron schedule."""
        config = {
            "name": "test",
            "api_base": "https://api.example.com",
            "schedule": "invalid cron",
            "steps": [{"name": "step1", "endpoint": "/test"}]
        }

        errors = WorkflowConfigValidator.validate_workflow_config(config)
        assert any("cron schedule" in error.lower() for error in errors)

    def test_valid_cron_schedules(self):
        """Test validation with various valid cron schedules."""
        valid_schedules = [
            "0 18 * * *",      # Daily at 6 PM UTC (2 AM SGT)
            "*/15 * * * *",    # Every 15 minutes
            "0 9-17 * * 1-5",  # Weekdays 9-5
            "0 0 1 * *",       # First day of month
            "0 12 * * 0,6"     # Weekends at noon
        ]

        for schedule in valid_schedules:
            config = {
                "name": "test",
                "api_base": "https://api.example.com",
                "schedule": schedule,
                "steps": [{"name": "step1", "endpoint": "/test"}]
            }

            errors = WorkflowConfigValidator.validate_workflow_config(config)
            schedule_errors = [e for e in errors if "cron" in e.lower()]
            assert schedule_errors == [], f"Valid schedule '{schedule}' failed validation: {schedule_errors}"

    def test_invalid_timezone(self):
        """Test validation with invalid timezone."""
        config = {
            "name": "test",
            "api_base": "https://api.example.com",
            "timezone": "Invalid/Timezone",
            "steps": [{"name": "step1", "endpoint": "/test"}]
        }

        errors = WorkflowConfigValidator.validate_workflow_config(config)
        assert any("timezone" in error.lower() for error in errors)

    def test_invalid_auth_config(self):
        """Test validation with invalid auth configuration."""
        configs = [
            # Missing auth type
            {
                "name": "test",
                "api_base": "https://api.example.com",
                "auth": {"token": "test"},
                "steps": [{"name": "step1", "endpoint": "/test"}]
            },
            # Invalid auth type
            {
                "name": "test",
                "api_base": "https://api.example.com",
                "auth": {"type": "invalid"},
                "steps": [{"name": "step1", "endpoint": "/test"}]
            },
            # Bearer auth missing token
            {
                "name": "test",
                "api_base": "https://api.example.com",
                "auth": {"type": "bearer"},
                "steps": [{"name": "step1", "endpoint": "/test"}]
            }
        ]

        for config in configs:
            errors = WorkflowConfigValidator.validate_workflow_config(config)
            assert any("auth" in error.lower() for error in errors)

    def test_empty_steps(self):
        """Test validation with empty steps list."""
        config = {
            "name": "test",
            "api_base": "https://api.example.com",
            "steps": []
        }

        errors = WorkflowConfigValidator.validate_workflow_config(config)
        assert any("steps" in error and "empty" in error for error in errors)

    def test_invalid_step_config(self):
        """Test validation with invalid step configuration."""
        config = {
            "name": "test",
            "api_base": "https://api.example.com",
            "steps": [
                {
                    "name": "step1",
                    "endpoint": "/test",
                    "method": "INVALID_METHOD",
                    "retry": {
                        "limit": -1,  # Invalid negative limit
                        "delay": "invalid"  # Invalid delay format
                    }
                }
            ]
        }

        errors = WorkflowConfigValidator.validate_workflow_config(config)
        assert any("HTTP method" in error for error in errors)
        assert any("retry limit" in error for error in errors)
        assert any("retry delay" in error for error in errors)

    def test_duplicate_step_names(self):
        """Test validation with duplicate step names."""
        config = {
            "name": "test",
            "api_base": "https://api.example.com",
            "steps": [
                {"name": "duplicate", "endpoint": "/test1"},
                {"name": "duplicate", "endpoint": "/test2"}
            ]
        }

        errors = WorkflowConfigValidator.validate_workflow_config(config)
        assert any("duplicate" in error.lower() for error in errors)

    def test_invalid_step_dependencies(self):
        """Test validation with invalid step dependencies."""
        config = {
            "name": "test",
            "api_base": "https://api.example.com",
            "steps": [
                {
                    "name": "step1",
                    "endpoint": "/test1",
                    "depends_on": ["nonexistent_step"]
                }
            ]
        }

        errors = WorkflowConfigValidator.validate_workflow_config(config)
        assert any("non-existent" in error.lower() for error in errors)

    def test_yaml_config_parsing(self):
        """Test parsing YAML configuration format."""
        yaml_config = """
name: "derivativ_cambridge_igcse_daily"
schedule: "0 18 * * *"
timezone: "Asia/Singapore"
api_base: "https://api.derivativ.ai"
auth:
  type: "bearer"
  token: "${DERIVATIV_API_KEY}"

variables:
  topics: ["algebra", "geometry", "statistics"]
  questions_per_topic: 8
  grade_level: 9

steps:
  - name: "generate_algebra_questions"
    endpoint: "/api/questions/generate"
    method: "POST"
    parallel_group: "question_generation"
    retry:
      limit: 3
      delay: "10s"
      backoff: "exponential"
      timeout: "5m"

  - name: "create_worksheet"
    endpoint: "/api/documents/generate"
    method: "POST"
    depends_on: ["generate_algebra_questions"]
    retry:
      limit: 2
      delay: "5s"
      timeout: "10m"
"""

        config = yaml.safe_load(yaml_config)
        errors = WorkflowConfigValidator.validate_workflow_config(config)
        assert errors == []

    def test_singapore_timezone_cron_conversion(self):
        """Test Singapore timezone scheduling logic."""
        # 2 AM SGT = 6 PM UTC previous day
        sgt_2am_config = {
            "name": "test",
            "api_base": "https://api.example.com",
            "schedule": "0 18 * * *",  # 6 PM UTC = 2 AM SGT+8
            "timezone": "Asia/Singapore",
            "steps": [{"name": "step1", "endpoint": "/test"}]
        }

        errors = WorkflowConfigValidator.validate_workflow_config(sgt_2am_config)
        assert errors == []


class TestRetryConfiguration:
    """Test cases for retry configuration validation."""

    def test_valid_retry_configs(self):
        """Test various valid retry configurations."""
        valid_configs = [
            {
                "limit": 3,
                "delay": "5s",
                "backoff": "exponential"
            },
            {
                "limit": 1,
                "delay": "1m",
                "backoff": "linear"
            },
            {
                "limit": 0,  # No retries
                "delay": "10s",
                "backoff": "constant"
            }
        ]

        for retry_config in valid_configs:
            errors = WorkflowConfigValidator._validate_retry_config(retry_config, 0)
            assert errors == [], f"Valid retry config failed validation: {retry_config}"

    def test_duration_string_validation(self):
        """Test duration string format validation."""
        valid_durations = ["1s", "30s", "5m", "2h", "10s", "60m"]
        invalid_durations = ["1", "s", "1sec", "5 minutes", "", "1.5s"]

        for duration in valid_durations:
            assert WorkflowConfigValidator._validate_duration_string(duration), f"Valid duration '{duration}' failed validation"

        for duration in invalid_durations:
            assert not WorkflowConfigValidator._validate_duration_string(duration), f"Invalid duration '{duration}' passed validation"


if __name__ == "__main__":
    # Run basic validation test
    print("Running gimme_ai workflow config validation tests...")

    # Test minimal config
    minimal_config = {
        "name": "test-workflow",
        "api_base": "https://api.example.com",
        "steps": [{"name": "step1", "endpoint": "/api/test"}]
    }

    errors = WorkflowConfigValidator.validate_workflow_config(minimal_config)
    print(f"Minimal config validation: {'PASS' if not errors else 'FAIL'}")
    if errors:
        for error in errors:
            print(f"  - {error}")

    print("Basic validation test complete.")
