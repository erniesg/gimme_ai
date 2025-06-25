"""Workflow configuration schema definitions for gimme_ai."""

import os
import re
import json
import base64
from typing import Dict, List, Optional, Any, Union, Literal
from pydantic import BaseModel, Field, field_validator, model_validator
import logging
from jinja2 import Template, Environment, TemplateError

logger = logging.getLogger(__name__)


class AuthConfig(BaseModel):
    """Authentication configuration for workflow APIs."""
    
    type: Literal["none", "bearer", "api_key", "basic", "custom"] = Field(
        ..., description="Authentication type"
    )
    
    # Bearer token auth
    token: Optional[str] = Field(None, description="Bearer token")
    
    # API key auth
    header_name: Optional[str] = Field(None, description="Header name for API key")
    api_key: Optional[str] = Field(None, description="API key value")
    
    # Basic auth
    username: Optional[str] = Field(None, description="Username for basic auth")
    password: Optional[str] = Field(None, description="Password for basic auth")
    
    # Custom headers
    custom_headers: Optional[Dict[str, str]] = Field(None, description="Custom headers")
    
    @model_validator(mode='after')
    def validate_auth_fields(self):
        """Validate required fields based on auth type."""
        if self.type == "bearer" and not self.token:
            raise ValueError("Bearer auth requires 'token' field")
        
        if self.type == "api_key":
            if not self.header_name or not self.api_key:
                raise ValueError("API key auth requires 'header_name' and 'api_key' fields")
        
        if self.type == "basic":
            if not self.username or not self.password:
                raise ValueError("Basic auth requires 'username' and 'password' fields")
        
        if self.type == "custom" and not self.custom_headers:
            raise ValueError("Custom auth requires 'custom_headers' field")
        
        return self
    
    def resolve_env_vars(self) -> 'AuthConfig':
        """Resolve environment variables in auth configuration."""
        resolved_data = {}
        
        for field_name, field_value in self.model_dump().items():
            if isinstance(field_value, str) and field_value.startswith("${") and field_value.endswith("}"):
                env_var = field_value[2:-1]  # Remove ${ and }
                if env_var not in os.environ:
                    raise ValueError(f"Environment variable '{env_var}' not found")
                resolved_data[field_name] = os.environ[env_var]
            elif isinstance(field_value, dict):
                # Handle custom_headers
                resolved_dict = {}
                for key, value in field_value.items():
                    if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
                        env_var = value[2:-1]
                        if env_var not in os.environ:
                            raise ValueError(f"Environment variable '{env_var}' not found")
                        resolved_dict[key] = os.environ[env_var]
                    else:
                        resolved_dict[key] = value
                resolved_data[field_name] = resolved_dict
            else:
                resolved_data[field_name] = field_value
        
        return AuthConfig(**resolved_data)
    
    def to_request_headers(self) -> Dict[str, str]:
        """Convert auth config to HTTP request headers."""
        headers = {}
        
        if self.type == "bearer" and self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        
        elif self.type == "api_key" and self.header_name and self.api_key:
            headers[self.header_name] = self.api_key
        
        elif self.type == "basic" and self.username and self.password:
            credentials = base64.b64encode(f"{self.username}:{self.password}".encode()).decode()
            headers["Authorization"] = f"Basic {credentials}"
        
        elif self.type == "custom" and self.custom_headers:
            headers.update(self.custom_headers)
        
        return headers


class RetryConfig(BaseModel):
    """Retry configuration for workflow steps."""
    
    limit: int = Field(..., description="Maximum number of retry attempts", ge=1, le=10)
    delay: str = Field(..., description="Initial delay between retries (e.g., '5s', '1m')")
    backoff: Literal["constant", "linear", "exponential"] = Field(
        "exponential", description="Backoff strategy"
    )
    timeout: Optional[str] = Field(None, description="Per-attempt timeout")
    
    @field_validator('delay', 'timeout')
    def validate_duration(cls, v):
        """Validate duration format."""
        if v is None:
            return v
        
        if not re.match(r'^(\d+\.?\d*|\.\d+)[smh]$', v):
            raise ValueError("Duration must be in format '5s', '1.5m', or '2h'")
        return v
    
    def parse_delay_seconds(self) -> float:
        """Parse delay string to seconds."""
        if self.delay.endswith('s'):
            return float(self.delay[:-1])
        elif self.delay.endswith('m'):
            return float(self.delay[:-1]) * 60
        elif self.delay.endswith('h'):
            return float(self.delay[:-1]) * 3600
        else:
            raise ValueError(f"Invalid delay format: {self.delay}")


class StepConfig(BaseModel):
    """Configuration for a single workflow step."""
    
    name: str = Field(..., description="Unique step identifier")
    description: Optional[str] = Field(None, description="Step description")
    endpoint: str = Field(..., description="API endpoint path")
    method: Literal["GET", "POST", "PUT", "DELETE", "PATCH"] = Field("POST", description="HTTP method")
    
    # Execution control
    depends_on: Optional[List[str]] = Field(None, description="Step dependencies")
    parallel_group: Optional[str] = Field(None, description="Parallel execution group")
    max_parallel: Optional[int] = Field(None, description="Max concurrent executions", ge=1, le=10)
    
    # Request configuration
    headers: Optional[Dict[str, str]] = Field(None, description="Additional request headers")
    payload_template: Optional[str] = Field(None, description="Jinja2 template for request body")
    payload: Optional[Any] = Field(None, description="Static request payload")
    
    # File handling
    download_response: bool = Field(False, description="Download response as file instead of parsing")
    upload_files: Optional[Dict[str, str]] = Field(None, description="Files to upload (field_name: file_path)")
    
    # Async job handling
    poll_for_completion: bool = Field(False, description="Poll URL until job completes")
    poll_interval: str = Field("10s", description="Polling interval")
    poll_timeout: str = Field("30m", description="Maximum polling time")
    completion_field: str = Field("status", description="Field to check for completion")
    completion_values: List[str] = Field(["completed", "succeeded"], description="Values indicating completion")
    result_field: Optional[str] = Field(None, description="Field containing final result")
    
    # Error handling
    retry: Optional[RetryConfig] = Field(None, description="Retry configuration")
    timeout: Optional[str] = Field(None, description="Step timeout")
    continue_on_error: bool = Field(False, description="Continue workflow if step fails")
    
    # Response processing
    response_transform: Optional[str] = Field(None, description="Jinja2 template for response transformation")
    output_key: Optional[str] = Field(None, description="Key to store result under")
    extract_fields: Optional[Dict[str, str]] = Field(None, description="Extract specific fields from response")
    
    # Storage
    store_in_r2: bool = Field(False, description="Store response/file in R2")
    r2_bucket: Optional[str] = Field(None, description="R2 bucket name")
    r2_key_template: Optional[str] = Field(None, description="R2 key template")
    
    @field_validator('name')
    def validate_name(cls, v):
        """Validate step name format."""
        if not v or not v.strip():
            raise ValueError("Step name cannot be empty")
        
        if not re.match(r'^[a-zA-Z0-9_]+$', v):
            raise ValueError("Step name can only contain alphanumeric characters and underscores")
        
        return v
    
    @field_validator('endpoint')
    def validate_endpoint(cls, v):
        """Validate endpoint format."""
        if not v.startswith('/'):
            raise ValueError("Endpoint must start with '/'")
        return v
    
    @field_validator('poll_interval')
    def validate_poll_interval(cls, v):
        """Validate polling interval format."""
        if not re.match(r'^\d+[smh]$', v):
            raise ValueError("Poll interval must be in format '5s', '1m', or '2h'")
        return v
    
    @field_validator('poll_timeout')
    def validate_poll_timeout(cls, v):
        """Validate polling timeout format."""
        if not re.match(r'^\d+[smh]$', v):
            raise ValueError("Poll timeout must be in format '5s', '1m', or '2h'")
        return v
    
    @field_validator('timeout')
    def validate_timeout(cls, v):
        """Validate step timeout format."""
        if v is None:
            return v
        if not re.match(r'^\d+[smh]$', v):
            raise ValueError("Timeout must be in format '5s', '1m', or '2h'")
        return v
    
    @model_validator(mode='after')
    def validate_payload_config(self):
        """Validate payload configuration."""
        if self.payload_template and self.payload:
            raise ValueError("Cannot specify both 'payload_template' and 'payload'")
        return self
    
    def render_payload(self, context: Dict[str, Any]) -> Any:
        """Render payload template with context data."""
        if self.payload_template:
            try:
                env = Environment()
                template = env.from_string(self.payload_template)
                rendered = template.render(**context)
                return json.loads(rendered)
            except (TemplateError, json.JSONDecodeError) as e:
                raise ValueError(f"Failed to render payload template: {e}")
        
        return self.payload


class MonitoringConfig(BaseModel):
    """Monitoring and notification configuration."""
    
    webhook_url: Optional[str] = Field(None, description="Webhook URL for notifications")
    alerts: Optional[Dict[str, Any]] = Field(None, description="Alert configuration")
    logging_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field("INFO")


class WorkflowConfig(BaseModel):
    """Complete workflow configuration."""
    
    name: str = Field(..., description="Unique workflow identifier")
    description: Optional[str] = Field(None, description="Workflow description")
    
    # Scheduling
    schedule: Optional[str] = Field(None, description="Cron schedule expression")
    timezone: Optional[str] = Field(None, description="Timezone for scheduling")
    
    # API configuration
    api_base: str = Field(..., description="Base URL for API calls")
    auth: Optional[AuthConfig] = Field(None, description="Authentication configuration")
    
    # Template variables
    variables: Optional[Dict[str, Any]] = Field(None, description="Global template variables")
    
    # Workflow steps
    steps: List[StepConfig] = Field(..., description="Workflow steps", min_length=1)
    
    # Monitoring
    monitoring: Optional[MonitoringConfig] = Field(None, description="Monitoring configuration")
    
    @field_validator('name')
    def validate_name(cls, v):
        """Validate workflow name."""
        if not v or not v.strip():
            raise ValueError("Workflow name cannot be empty")
        
        if len(v) > 63:
            raise ValueError("Workflow name must be 63 characters or less")
        
        if not re.match(r'^[a-zA-Z0-9_-]+$', v):
            raise ValueError("Workflow name can only contain alphanumeric characters, underscores, and hyphens")
        
        return v
    
    @field_validator('api_base')
    def validate_api_base(cls, v):
        """Validate API base URL."""
        if not v.startswith(('http://', 'https://')):
            raise ValueError("api_base must be a valid URL starting with http:// or https://")
        return v
    
    @field_validator('schedule')
    def validate_schedule(cls, v):
        """Validate cron schedule format."""
        if v is None:
            return v
        
        # Basic cron validation (5 or 6 fields)
        fields = v.split()
        if len(fields) not in [5, 6]:
            raise ValueError("Cron schedule must have 5 or 6 fields")
        
        # Validate individual fields (basic check)
        minute, hour, day, month, weekday = fields[:5]
        
        # Check minute (0-59)
        if not re.match(r'^(\*|[0-5]?\d|[0-5]?\d-[0-5]?\d|\*/\d+)$', minute):
            raise ValueError("Invalid minute field in cron schedule")
        
        # Check hour (0-23)
        if not re.match(r'^(\*|[01]?\d|2[0-3]|[01]?\d-[01]?\d|2[0-3]-2[0-3]|\*/\d+)$', hour):
            raise ValueError("Invalid hour field in cron schedule")
        
        return v
    
    @model_validator(mode='after')
    def validate_step_names_unique(self):
        """Validate that step names are unique."""
        step_names = [step.name for step in self.steps]
        if len(step_names) != len(set(step_names)):
            raise ValueError("Step names must be unique")
        return self
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WorkflowConfig":
        """Create workflow config from dictionary."""
        # Transform nested objects
        if "auth" in data and isinstance(data["auth"], dict):
            data["auth"] = AuthConfig(**data["auth"])
        
        if "steps" in data:
            steps = []
            for step_data in data["steps"]:
                if isinstance(step_data, dict):
                    # Transform retry config if present
                    if "retry" in step_data and isinstance(step_data["retry"], dict):
                        step_data["retry"] = RetryConfig(**step_data["retry"])
                    steps.append(StepConfig(**step_data))
                else:
                    steps.append(step_data)
            data["steps"] = steps
        
        if "monitoring" in data and isinstance(data["monitoring"], dict):
            data["monitoring"] = MonitoringConfig(**data["monitoring"])
        
        return cls(**data)
    
    def resolve_env_vars(self) -> 'WorkflowConfig':
        """Resolve environment variables in the entire configuration."""
        data = self.model_dump()
        
        # Resolve auth
        if data.get("auth"):
            auth_config = AuthConfig(**data["auth"])
            data["auth"] = auth_config.resolve_env_vars().model_dump()
        
        # Resolve variables
        if data.get("variables"):
            resolved_vars = {}
            for key, value in data["variables"].items():
                if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
                    env_var = value[2:-1]
                    if env_var not in os.environ:
                        raise ValueError(f"Environment variable '{env_var}' not found")
                    resolved_vars[key] = os.environ[env_var]
                else:
                    resolved_vars[key] = value
            data["variables"] = resolved_vars
        
        return WorkflowConfig.from_dict(data)


def validate_workflow_config(config_data: Dict[str, Any]) -> List[str]:
    """Validate workflow configuration and return list of issues."""
    issues = []
    
    try:
        WorkflowConfig.from_dict(config_data)
    except Exception as e:
        issues.append(str(e))
    
    return issues


def resolve_workflow_dependencies(steps: List[StepConfig]) -> List[List[StepConfig]]:
    """
    Resolve workflow dependencies and return steps grouped by execution phases.
    
    Returns:
        List of execution phases, where each phase is a list of steps that can run in parallel.
    """
    step_map = {step.name: step for step in steps}
    remaining_steps = set(step.name for step in steps)
    completed_steps = set()
    execution_phases = []
    
    # Track parallel groups
    parallel_groups = {}
    for step in steps:
        if step.parallel_group:
            if step.parallel_group not in parallel_groups:
                parallel_groups[step.parallel_group] = []
            parallel_groups[step.parallel_group].append(step)
    
    # Detect circular dependencies
    def has_circular_dependency(step_name: str, visited: set, path: set) -> bool:
        if step_name in path:
            return True
        if step_name in visited:
            return False
        
        visited.add(step_name)
        path.add(step_name)
        
        step = step_map.get(step_name)
        if step and step.depends_on:
            for dep in step.depends_on:
                if dep in step_map and has_circular_dependency(dep, visited, path):
                    return True
        
        path.remove(step_name)
        return False
    
    # Check for circular dependencies
    visited = set()
    for step_name in remaining_steps:
        if has_circular_dependency(step_name, visited, set()):
            raise ValueError(f"Circular dependency detected involving step '{step_name}'")
    
    # Check for missing dependencies
    for step in steps:
        if step.depends_on:
            for dep in step.depends_on:
                if dep not in step_map and dep not in parallel_groups:
                    raise ValueError(f"Missing dependency '{dep}' for step '{step.name}'")
    
    # Resolve dependencies phase by phase
    while remaining_steps:
        current_phase = []
        processed_in_phase = set()
        
        for step_name in list(remaining_steps):
            step = step_map[step_name]
            
            # Check if all dependencies are satisfied
            dependencies_satisfied = True
            if step.depends_on:
                for dep in step.depends_on:
                    if dep in parallel_groups:
                        # Check if all steps in parallel group are completed
                        group_steps = [s.name for s in parallel_groups[dep]]
                        if not all(s in completed_steps for s in group_steps):
                            dependencies_satisfied = False
                            break
                    elif dep not in completed_steps:
                        dependencies_satisfied = False
                        break
            
            if dependencies_satisfied:
                current_phase.append(step)
                processed_in_phase.add(step_name)
        
        if not current_phase:
            # No progress made - this shouldn't happen with proper dependency validation
            unresolved = list(remaining_steps)
            raise ValueError(f"Cannot resolve dependencies for steps: {unresolved}")
        
        execution_phases.append(current_phase)
        remaining_steps -= processed_in_phase
        completed_steps.update(processed_in_phase)
        
        # Mark parallel groups as completed
        for step in current_phase:
            if step.parallel_group and step.parallel_group not in completed_steps:
                group_steps = [s.name for s in parallel_groups[step.parallel_group]]
                if all(s in completed_steps for s in group_steps):
                    completed_steps.add(step.parallel_group)
    
    return execution_phases