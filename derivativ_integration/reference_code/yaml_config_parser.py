"""YAML Configuration Parser with Jinja2 templating for gimme_ai workflows.

This module provides comprehensive YAML configuration parsing and validation
with Jinja2 templating support for dynamic workflow configurations.
"""

import json
import os
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional, Union

import jinja2
import yaml


@dataclass
class ParsedWorkflowConfig:
    """Parsed and validated workflow configuration."""
    name: str
    description: Optional[str]
    schedule: Optional[str]
    timezone: Optional[str]
    api_base: str
    auth: Optional[dict[str, Any]]
    variables: dict[str, Any]
    steps: list[dict[str, Any]]
    monitoring: Optional[dict[str, Any]]

    # Metadata
    config_file_path: Optional[str] = None
    parsed_at: Optional[datetime] = None
    validation_errors: list[str] = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary format."""
        return {
            "name": self.name,
            "description": self.description,
            "schedule": self.schedule,
            "timezone": self.timezone,
            "api_base": self.api_base,
            "auth": self.auth,
            "variables": self.variables,
            "steps": self.steps,
            "monitoring": self.monitoring
        }


class YAMLConfigParser:
    """YAML configuration parser with Jinja2 templating and validation."""

    def __init__(self, template_dir: Optional[str] = None):
        """Initialize parser with optional template directory."""
        self.template_dir = template_dir
        self.jinja_env = self._create_jinja_environment()
        self.validation_errors: list[str] = []

    def _create_jinja_environment(self) -> jinja2.Environment:
        """Create Jinja2 environment with custom filters and functions."""

        # Setup template loader
        if self.template_dir and os.path.exists(self.template_dir):
            loader = jinja2.FileSystemLoader(self.template_dir)
        else:
            loader = jinja2.BaseLoader()

        env = jinja2.Environment(
            loader=loader,
            undefined=jinja2.DebugUndefined,  # Allow undefined variables for flexibility
            trim_blocks=True,
            lstrip_blocks=True
        )

        # Add custom filters
        env.filters.update({
            'tojson': json.dumps,
            'fromjson': json.loads,
            'flatten': self._flatten_list,
            'collect_question_ids': self._collect_question_ids,
            'format_duration': self._format_duration,
            'singapore_time': self._convert_to_singapore_time
        })

        # Add custom functions
        env.globals.update({
            'now': datetime.now,
            'env': os.environ.get,
            'file_exists': os.path.exists,
            'generate_uuid': self._generate_uuid
        })

        return env

    def parse_yaml_file(
        self,
        config_path: str,
        template_variables: Optional[dict[str, Any]] = None
    ) -> ParsedWorkflowConfig:
        """Parse YAML configuration file with template rendering."""

        if not os.path.exists(config_path):
            raise FileNotFoundError(f"Configuration file not found: {config_path}")

        # Read raw YAML content
        with open(config_path, encoding='utf-8') as file:
            raw_content = file.read()

        # Render templates if variables provided
        if template_variables:
            rendered_content = self._render_template_content(raw_content, template_variables)
        else:
            rendered_content = raw_content

        # Parse YAML
        try:
            config_data = yaml.safe_load(rendered_content)
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML syntax in {config_path}: {e}")

        # Validate and parse configuration
        parsed_config = self._parse_config_data(config_data)
        parsed_config.config_file_path = config_path
        parsed_config.parsed_at = datetime.now()

        return parsed_config

    def parse_yaml_string(
        self,
        yaml_content: str,
        template_variables: Optional[dict[str, Any]] = None
    ) -> ParsedWorkflowConfig:
        """Parse YAML configuration from string."""

        # Render templates if variables provided
        if template_variables:
            rendered_content = self._render_template_content(yaml_content, template_variables)
        else:
            rendered_content = yaml_content

        # Parse YAML
        try:
            config_data = yaml.safe_load(rendered_content)
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML syntax: {e}")

        # Validate and parse configuration
        parsed_config = self._parse_config_data(config_data)
        parsed_config.parsed_at = datetime.now()

        return parsed_config

    def _render_template_content(self, content: str, variables: dict[str, Any]) -> str:
        """Render Jinja2 templates in YAML content."""
        try:
            template = self.jinja_env.from_string(content)
            rendered = template.render(**variables)
            return rendered
        except jinja2.TemplateError as e:
            raise ValueError(f"Template rendering error: {e}")

    def _parse_config_data(self, data: dict[str, Any]) -> ParsedWorkflowConfig:
        """Parse and validate configuration data."""
        self.validation_errors = []

        # Extract and validate required fields
        name = self._extract_required_string(data, "name")
        api_base = self._extract_required_string(data, "api_base")
        steps = self._extract_required_list(data, "steps")

        # Extract optional fields
        description = data.get("description")
        schedule = data.get("schedule")
        timezone = data.get("timezone", "UTC")
        auth = data.get("auth")
        variables = data.get("variables", {})
        monitoring = data.get("monitoring")

        # Validate configuration
        self._validate_workflow_config(data)

        # Create parsed config
        config = ParsedWorkflowConfig(
            name=name,
            description=description,
            schedule=schedule,
            timezone=timezone,
            api_base=api_base,
            auth=auth,
            variables=variables,
            steps=steps,
            monitoring=monitoring,
            validation_errors=self.validation_errors.copy()
        )

        if self.validation_errors:
            error_summary = "; ".join(self.validation_errors)
            raise ValueError(f"Configuration validation failed: {error_summary}")

        return config

    def _extract_required_string(self, data: dict[str, Any], field: str) -> str:
        """Extract required string field with validation."""
        if field not in data:
            self.validation_errors.append(f"Missing required field: {field}")
            return ""

        value = data[field]
        if not isinstance(value, str) or not value.strip():
            self.validation_errors.append(f"Field '{field}' must be a non-empty string")
            return ""

        return value.strip()

    def _extract_required_list(self, data: dict[str, Any], field: str) -> list[Any]:
        """Extract required list field with validation."""
        if field not in data:
            self.validation_errors.append(f"Missing required field: {field}")
            return []

        value = data[field]
        if not isinstance(value, list):
            self.validation_errors.append(f"Field '{field}' must be a list")
            return []

        if len(value) == 0:
            self.validation_errors.append(f"Field '{field}' cannot be empty")
            return []

        return value

    def _validate_workflow_config(self, data: dict[str, Any]) -> None:
        """Validate complete workflow configuration."""

        # Validate API base URL
        if "api_base" in data:
            api_base = data["api_base"]
            if not (api_base.startswith("http://") or api_base.startswith("https://")):
                self.validation_errors.append("api_base must be a valid HTTP/HTTPS URL")

        # Validate schedule (cron format)
        if "schedule" in data and data["schedule"]:
            self._validate_cron_schedule(data["schedule"])

        # Validate timezone
        if "timezone" in data:
            self._validate_timezone(data["timezone"])

        # Validate authentication
        if "auth" in data and data["auth"]:
            self._validate_auth_config(data["auth"])

        # Validate steps
        if "steps" in data:
            self._validate_steps_config(data["steps"])

        # Validate monitoring
        if "monitoring" in data and data["monitoring"]:
            self._validate_monitoring_config(data["monitoring"])

    def _validate_cron_schedule(self, schedule: str) -> None:
        """Validate cron schedule format."""
        if not isinstance(schedule, str):
            self.validation_errors.append("Schedule must be a string")
            return

        parts = schedule.strip().split()
        if len(parts) != 5:
            self.validation_errors.append("Cron schedule must have exactly 5 fields")
            return

        # Basic field validation
        field_ranges = [
            (0, 59),   # minute
            (0, 23),   # hour
            (1, 31),   # day
            (1, 12),   # month
            (0, 7)     # weekday (0 and 7 are Sunday)
        ]

        field_names = ["minute", "hour", "day", "month", "weekday"]

        for i, (part, (min_val, max_val), name) in enumerate(zip(parts, field_ranges, field_names)):
            if not self._validate_cron_field(part, min_val, max_val):
                self.validation_errors.append(f"Invalid {name} in cron schedule: {part}")

    def _validate_cron_field(self, field: str, min_val: int, max_val: int) -> bool:
        """Validate individual cron field."""
        # Wildcard
        if field == "*":
            return True

        # Range (e.g., 1-5)
        if "-" in field and "/" not in field:
            try:
                start, end = field.split("-", 1)
                start_num = int(start)
                end_num = int(end)
                return min_val <= start_num <= max_val and min_val <= end_num <= max_val and start_num <= end_num
            except ValueError:
                return False

        # Step values (e.g., */5, 1-10/2)
        if "/" in field:
            try:
                base, step = field.split("/", 1)
                step_num = int(step)
                if step_num <= 0:
                    return False

                if base == "*":
                    return True
                elif "-" in base:
                    start, end = base.split("-", 1)
                    start_num = int(start)
                    end_num = int(end)
                    return min_val <= start_num <= max_val and min_val <= end_num <= max_val
                else:
                    base_num = int(base)
                    return min_val <= base_num <= max_val
            except ValueError:
                return False

        # Comma-separated values (e.g., 1,3,5)
        if "," in field:
            try:
                values = [int(v.strip()) for v in field.split(",")]
                return all(min_val <= v <= max_val for v in values)
            except ValueError:
                return False

        # Single numeric value
        try:
            num = int(field)
            return min_val <= num <= max_val
        except ValueError:
            return False

    def _validate_timezone(self, timezone: str) -> None:
        """Validate timezone string."""
        valid_timezones = [
            "UTC", "GMT",
            "Asia/Singapore", "Asia/Hong_Kong", "Asia/Tokyo", "Asia/Seoul",
            "America/New_York", "America/Los_Angeles", "America/Chicago", "America/Denver",
            "Europe/London", "Europe/Berlin", "Europe/Paris", "Europe/Rome",
            "Australia/Sydney", "Australia/Melbourne"
        ]

        if timezone not in valid_timezones:
            self.validation_errors.append(f"Unsupported timezone: {timezone}")

    def _validate_auth_config(self, auth: dict[str, Any]) -> None:
        """Validate authentication configuration."""
        if not isinstance(auth, dict):
            self.validation_errors.append("Auth configuration must be a dictionary")
            return

        if "type" not in auth:
            self.validation_errors.append("Auth configuration must specify 'type'")
            return

        auth_type = auth["type"]
        valid_types = ["none", "bearer", "api_key", "basic", "custom"]

        if auth_type not in valid_types:
            self.validation_errors.append(f"Invalid auth type: {auth_type}")
            return

        # Type-specific validation
        if auth_type == "bearer" and "token" not in auth:
            self.validation_errors.append("Bearer auth requires 'token' field")
        elif auth_type == "api_key" and "api_key" not in auth:
            self.validation_errors.append("API key auth requires 'api_key' field")
        elif auth_type == "basic":
            if "username" not in auth or "password" not in auth:
                self.validation_errors.append("Basic auth requires 'username' and 'password' fields")
        elif auth_type == "custom" and "custom_headers" not in auth:
            self.validation_errors.append("Custom auth requires 'custom_headers' field")

    def _validate_steps_config(self, steps: list[dict[str, Any]]) -> None:
        """Validate workflow steps configuration."""
        if not isinstance(steps, list):
            self.validation_errors.append("Steps must be a list")
            return

        step_names = set()

        for i, step in enumerate(steps):
            if not isinstance(step, dict):
                self.validation_errors.append(f"Step {i} must be a dictionary")
                continue

            # Required fields
            if "name" not in step:
                self.validation_errors.append(f"Step {i} missing required field: name")
            elif step["name"] in step_names:
                self.validation_errors.append(f"Duplicate step name: {step['name']}")
            else:
                step_names.add(step["name"])

            if "endpoint" not in step:
                self.validation_errors.append(f"Step {i} missing required field: endpoint")

            # HTTP method validation
            if "method" in step:
                valid_methods = ["GET", "POST", "PUT", "DELETE", "PATCH"]
                if step["method"] not in valid_methods:
                    self.validation_errors.append(f"Step {i} invalid HTTP method: {step['method']}")

            # Retry configuration validation
            if "retry" in step:
                self._validate_retry_config(step["retry"], i)

        # Validate dependencies
        for i, step in enumerate(steps):
            if "depends_on" in step:
                if not isinstance(step["depends_on"], list):
                    self.validation_errors.append(f"Step {i} depends_on must be a list")
                else:
                    for dep in step["depends_on"]:
                        if dep not in step_names:
                            self.validation_errors.append(f"Step {i} depends on non-existent step: {dep}")

    def _validate_retry_config(self, retry: dict[str, Any], step_index: int) -> None:
        """Validate retry configuration."""
        if not isinstance(retry, dict):
            self.validation_errors.append(f"Step {step_index} retry config must be a dictionary")
            return

        # Required fields
        if "limit" not in retry:
            self.validation_errors.append(f"Step {step_index} retry config missing 'limit'")
        elif not isinstance(retry["limit"], int) or retry["limit"] < 0:
            self.validation_errors.append(f"Step {step_index} retry limit must be a non-negative integer")

        if "delay" not in retry:
            self.validation_errors.append(f"Step {step_index} retry config missing 'delay'")
        elif not self._validate_duration_string(retry["delay"]):
            self.validation_errors.append(f"Step {step_index} retry delay must be valid duration (e.g., '5s', '1m')")

        # Optional fields
        if "backoff" in retry:
            valid_backoff = ["constant", "linear", "exponential"]
            if retry["backoff"] not in valid_backoff:
                self.validation_errors.append(f"Step {step_index} invalid backoff strategy: {retry['backoff']}")

    def _validate_monitoring_config(self, monitoring: dict[str, Any]) -> None:
        """Validate monitoring configuration."""
        if not isinstance(monitoring, dict):
            self.validation_errors.append("Monitoring configuration must be a dictionary")
            return

        # Validate webhook URL
        if "webhook_url" in monitoring:
            webhook_url = monitoring["webhook_url"]
            if not isinstance(webhook_url, str) or not (webhook_url.startswith("http://") or webhook_url.startswith("https://")):
                self.validation_errors.append("Monitoring webhook_url must be a valid HTTP/HTTPS URL")

    def _validate_duration_string(self, duration: str) -> bool:
        """Validate duration string format."""
        if not isinstance(duration, str):
            return False

        pattern = r"^\d+[smh]$"
        return bool(re.match(pattern, duration))

    # Custom Jinja2 filters and functions

    def _flatten_list(self, nested_list: list[Any]) -> list[Any]:
        """Flatten nested list."""
        result = []
        for item in nested_list:
            if isinstance(item, list):
                result.extend(self._flatten_list(item))
            else:
                result.append(item)
        return result

    def _collect_question_ids(self, step_results: dict[str, Any]) -> list[str]:
        """Collect question IDs from step results."""
        question_ids = []

        for step_name, result in step_results.items():
            if isinstance(result, dict) and "question_ids" in result:
                ids = result["question_ids"]
                if isinstance(ids, list):
                    question_ids.extend(ids)
                elif isinstance(ids, str):
                    question_ids.append(ids)

        return question_ids

    def _format_duration(self, duration_ms: Union[int, float]) -> str:
        """Format duration in milliseconds to human-readable string."""
        if duration_ms < 1000:
            return f"{duration_ms:.0f}ms"
        elif duration_ms < 60000:
            return f"{duration_ms/1000:.1f}s"
        elif duration_ms < 3600000:
            return f"{duration_ms/60000:.1f}m"
        else:
            return f"{duration_ms/3600000:.1f}h"

    def _convert_to_singapore_time(self, utc_cron: str) -> str:
        """Convert UTC cron schedule to Singapore time equivalent."""
        # SGT is UTC+8, so subtract 8 hours from cron hour
        parts = utc_cron.strip().split()
        if len(parts) != 5:
            return utc_cron  # Return as-is if invalid format

        try:
            minute, hour, day, month, weekday = parts
            hour_num = int(hour)

            # Convert UTC to SGT (subtract 8 hours)
            sgt_hour = (hour_num - 8) % 24

            return f"{minute} {sgt_hour} {day} {month} {weekday}"
        except ValueError:
            return utc_cron  # Return as-is if can't parse

    def _generate_uuid(self) -> str:
        """Generate UUID for templates."""
        import uuid
        return str(uuid.uuid4())


class DerivativConfigTemplates:
    """Pre-built configuration templates for Derivativ workflows."""

    @staticmethod
    def daily_question_generation_template() -> str:
        """Template for daily question generation workflow."""
        return """
name: "derivativ_cambridge_igcse_daily"
description: "Daily Cambridge IGCSE question generation for multiple topics"
schedule: "0 18 * * *"  # 2 AM Singapore Time (6 PM UTC previous day)
timezone: "Asia/Singapore"
api_base: "{{ api_base_url }}"

auth:
  type: "bearer"
  token: "{{ derivativ_api_key }}"

variables:
  topics: {{ topics | tojson }}
  questions_per_topic: {{ questions_per_topic | default(8) }}
  grade_level: {{ grade_level | default(9) }}
  quality_threshold: {{ quality_threshold | default(0.75) }}
  total_target: {{ (topics | length) * (questions_per_topic | default(8)) }}
  request_id: "daily-{{ now().strftime('%Y%m%d') }}-{{ generate_uuid()[:8] }}"
  workflow_date: "{{ now().strftime('%Y-%m-%d') }}"

steps:
  # Phase 1: Parallel Question Generation by Topic
  {% for topic in topics %}
  - name: "generate_{{ topic }}_questions"
    description: "Generate {{ questions_per_topic | default(8) }} {{ topic }} questions"
    endpoint: "/api/questions/generate"
    method: "POST"
    parallel_group: "question_generation"
    retry:
      limit: 3
      delay: "10s"
      backoff: "exponential"
      timeout: "5m"
    payload_template: |
      {
        "topic": "{{ topic }}",
        "count": {{ questions_per_topic | default(8) }},
        "grade_level": {{ grade_level | default(9) }},
        "quality_threshold": {{ quality_threshold | default(0.75) }},
        "request_id": "{{ request_id }}-{{ topic }}",
        "workflow_date": "{{ workflow_date }}"
      }
    output_key: "{{ topic }}_results"
  {% endfor %}

  # Phase 2: Document Generation (depends on all question generation)
  - name: "create_worksheet"
    description: "Create student worksheet with all generated questions"
    endpoint: "/api/documents/generate"
    method: "POST"
    depends_on: [{% for topic in topics %}"generate_{{ topic }}_questions"{% if not loop.last %}, {% endif %}{% endfor %}]
    retry:
      limit: 2
      delay: "5s"
      timeout: "10m"
    payload_template: |
      {
        "document_type": "worksheet",
        "question_ids": [{% for topic in topics %}"{{ topic }}_q1", "{{ topic }}_q2"{% if not loop.last %}, {% endif %}{% endfor %}],
        "detail_level": "medium",
        "include_solutions": false,
        "metadata": {
          "generated_date": "{{ workflow_date }}",
          "topics": {{ topics | tojson }},
          "total_questions": {{ total_target }}
        }
      }
    output_key: "worksheet_result"

  - name: "create_answer_key"
    description: "Create answer key with detailed solutions"
    endpoint: "/api/documents/generate"
    method: "POST"
    depends_on: [{% for topic in topics %}"generate_{{ topic }}_questions"{% if not loop.last %}, {% endif %}{% endfor %}]
    payload_template: |
      {
        "document_type": "answer_key",
        "question_ids": [{% for topic in topics %}"{{ topic }}_q1", "{{ topic }}_q2"{% if not loop.last %}, {% endif %}{% endfor %}],
        "include_solutions": true,
        "include_marking_schemes": true,
        "metadata": {
          "generated_date": "{{ workflow_date }}",
          "topics": {{ topics | tojson }}
        }
      }
    output_key: "answer_key_result"

  - name: "create_teaching_notes"
    description: "Create teaching notes with pedagogical guidance"
    endpoint: "/api/documents/generate"
    method: "POST"
    depends_on: [{% for topic in topics %}"generate_{{ topic }}_questions"{% if not loop.last %}, {% endif %}{% endfor %}]
    payload_template: |
      {
        "document_type": "teaching_notes",
        "question_ids": [{% for topic in topics %}"{{ topic }}_q1", "{{ topic }}_q2"{% if not loop.last %}, {% endif %}{% endfor %}],
        "include_pedagogy": true,
        "include_common_mistakes": true,
        "metadata": {
          "generated_date": "{{ workflow_date }}",
          "topics": {{ topics | tojson }}
        }
      }
    output_key: "teaching_notes_result"

  # Phase 3: Storage and Export
  - name: "store_documents"
    description: "Store all generated documents with dual versions"
    endpoint: "/api/documents/store"
    method: "POST"
    depends_on: ["create_worksheet", "create_answer_key", "create_teaching_notes"]
    payload_template: |
      {
        "documents": [
          {
            "id": "worksheet-{{ workflow_date }}",
            "type": "worksheet",
            "formats": ["pdf", "docx", "html"]
          },
          {
            "id": "answer-key-{{ workflow_date }}",
            "type": "answer_key",
            "formats": ["pdf", "docx"]
          },
          {
            "id": "teaching-notes-{{ workflow_date }}",
            "type": "teaching_notes",
            "formats": ["pdf", "html"]
          }
        ],
        "create_dual_versions": true,
        "metadata": {
          "workflow_id": "{{ request_id }}",
          "generation_date": "{{ workflow_date }}",
          "total_questions": {{ total_target }}
        }
      }

monitoring:
  webhook_url: "{{ webhook_url | default('https://api.derivativ.ai/webhooks/workflow_complete') }}"
  alerts:
    on_failure: true
    on_long_duration: "30m"
"""

    @staticmethod
    def simple_api_test_template() -> str:
        """Simple template for API testing."""
        return """
name: "{{ workflow_name | default('simple_api_test') }}"
description: "Simple API workflow for testing"
api_base: "{{ api_base_url }}"

{% if auth_token %}
auth:
  type: "bearer"
  token: "{{ auth_token }}"
{% endif %}

variables:
  test_data: {{ test_data | default('{"test": true}') | tojson }}
  request_id: "{{ generate_uuid() }}"

steps:
  - name: "test_endpoint"
    description: "Test API endpoint connectivity"
    endpoint: "{{ test_endpoint | default('/api/test') }}"
    method: "{{ http_method | default('POST') }}"
    payload_template: |
      {
        "request_id": "{{ request_id }}",
        "test_data": {{ test_data | tojson }},
        "timestamp": "{{ now().isoformat() }}"
      }
    retry:
      limit: {{ retry_limit | default(2) }}
      delay: "{{ retry_delay | default('5s') }}"
      backoff: "{{ retry_backoff | default('exponential') }}"
"""


if __name__ == "__main__":
    # Test the YAML parser with sample configurations

    print("Testing YAML Configuration Parser...")

    parser = YAMLConfigParser()

    # Test 1: Simple configuration
    simple_config = """
name: "test-workflow"
api_base: "https://api.example.com"
variables:
  test_value: 42
steps:
  - name: "step1"
    endpoint: "/api/test"
    method: "POST"
    retry:
      limit: 2
      delay: "5s"
      backoff: "exponential"
"""

    try:
        config = parser.parse_yaml_string(simple_config)
        print("✅ Simple configuration parsed successfully")
        print(f"   Workflow name: {config.name}")
        print(f"   Steps count: {len(config.steps)}")
    except Exception as e:
        print(f"❌ Simple configuration failed: {e}")

    # Test 2: Template rendering
    template_config = DerivativConfigTemplates.daily_question_generation_template()
    template_vars = {
        "api_base_url": "https://api.derivativ.ai",
        "derivativ_api_key": "test-api-key",
        "topics": ["algebra", "geometry", "statistics"],
        "questions_per_topic": 6,
        "grade_level": 9,
        "quality_threshold": 0.8
    }

    try:
        config = parser.parse_yaml_string(template_config, template_vars)
        print("✅ Derivativ template parsed successfully")
        print(f"   Workflow name: {config.name}")
        print(f"   Total steps: {len(config.steps)}")
        print(f"   Parallel groups: {len([s for s in config.steps if s.get('parallel_group')])}")
    except Exception as e:
        print(f"❌ Derivativ template failed: {e}")

    # Test 3: Invalid configuration
    invalid_config = """
name: ""  # Invalid empty name
api_base: "not-a-url"  # Invalid URL
schedule: "invalid cron"  # Invalid cron
steps: []  # Empty steps
"""

    try:
        config = parser.parse_yaml_string(invalid_config)
        print("❌ Invalid configuration should have failed")
    except ValueError as e:
        print("✅ Invalid configuration correctly rejected")
        print(f"   Validation errors detected: {len(parser.validation_errors)}")

    print("YAML parser testing completed.")
