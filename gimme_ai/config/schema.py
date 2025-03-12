# gimme_ai/config/schema.py
"""Configuration schema definitions for gimme_ai."""

from typing import Dict, List, Optional, Any, Union
from pydantic import BaseModel, Field, field_validator


class RateLimits(BaseModel):
    """Rate limit configuration."""

    per_ip: int = Field(5, description="Requests per IP address")
    global_limit: int = Field(100, description="Global request limit", alias="global")
    rate_window: str = Field("lifetime", description="Rate limit window")

    # Allow "global" as an alias for "global_limit"
    @field_validator('global_limit', mode='before')
    @classmethod
    def handle_global_alias(cls, v, info):
        # If we're validating the whole model and "global" is in the data
        if hasattr(info, 'data') and 'global' in info.data:
            return info.data.pop('global')  # Use "global" value and remove it from data
        return v

    class Config:
        populate_by_name = True  # Allow populating by alias or actual field name


class Endpoints(BaseModel):
    """API endpoint configuration."""

    dev: str = Field(..., description="Development endpoint URL")
    prod: str = Field(..., description="Production endpoint URL")


class GimmeConfig(BaseModel):
    """Main configuration schema."""

    project_name: str = Field(..., description="Project name")
    endpoints: Endpoints = Field(..., description="API endpoints")
    limits: Dict[str, Union[RateLimits, Dict[str, Any]]] = Field(
        default_factory=lambda: {"free_tier": {"per_ip": 5, "global": 100}}
    )
    required_keys: List[str] = Field(
        default_factory=list, description="Required API keys"
    )
    admin_password_env: str = Field(
        "GIMME_ADMIN_PASSWORD", description="Admin password environment variable name"
    )

    @field_validator("project_name")
    def validate_project_name(cls, v):
        """Validate project name."""
        if not v or not v.strip():
            raise ValueError("Project name cannot be empty")
        if len(v) > 63:
            raise ValueError("Project name must be 63 characters or less")
        if not all(c.isalnum() or c == "-" for c in v):
            raise ValueError("Project name can only contain alphanumeric characters and hyphens")
        if v.startswith("-") or v.endswith("-"):
            raise ValueError("Project name cannot start or end with a hyphen")
        return v

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GimmeConfig":
        """Create a configuration from a dictionary."""
        # Transform limits if needed
        if "limits" in data and isinstance(data["limits"], dict):
            for tier, limits in data["limits"].items():
                if isinstance(limits, dict) and not isinstance(limits, RateLimits):
                    # Handle field name mapping for global limit
                    if "global" in limits and "global_limit" not in limits:
                        # Keep both for compatibility, but prefer global_limit for internal use
                        limits["global_limit"] = limits["global"]

                    data["limits"][tier] = RateLimits(**limits)

                    # Debug output to verify the limits
                    print(f"Parsed limits for {tier}: {data['limits'][tier]}")

        # Transform endpoints if needed
        if "endpoints" in data and isinstance(data["endpoints"], dict):
            if not isinstance(data["endpoints"], Endpoints):
                data["endpoints"] = Endpoints(**data["endpoints"])

        return cls(**data)

    @classmethod
    def from_file(cls, file_path: str) -> "GimmeConfig":
        """Load configuration from a JSON file."""
        import json

        with open(file_path, "r") as f:
            data = json.load(f)

        return cls.from_dict(data)


def create_default_config(project_name: str) -> Dict[str, Any]:
    """Create a default configuration dictionary with sensible defaults.

    Args:
        project_name: Name of the project, used for endpoints and deployment

    Returns:
        Dictionary containing the default configuration
    """
    # Sanitize project name for use in URLs and identifiers
    safe_project_name = project_name.lower().replace('_', '-').replace(' ', '-')

    return {
        "project_name": safe_project_name,
        "output_dir": f"output/{safe_project_name}",  # Consistent output directory
        "endpoints": {
            "dev": "http://localhost:8000",  # Default local development endpoint
            "prod": f"https://{safe_project_name}.modal.run"  # Default production endpoint using project name
        },
        "limits": {
            "free_tier": {
                "per_ip": 10,
                "global": 100,
                "rate_window": "lifetime"
            }
        },
        "required_keys": [
            "MODAL_TOKEN_ID",
            "MODAL_TOKEN_SECRET"
        ],
        "admin_password_env": "GIMME_ADMIN_PASSWORD",
        "cors": {
            "allowed_origins": ["*"],  # Default to allow all origins
            "allowed_methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            "allowed_headers": ["Content-Type", "Authorization"]
        }
    }


def validate_config(config: Dict[str, Any]) -> List[str]:
    """Validate configuration and return any issues."""
    issues = []

    try:
        GimmeConfig.from_dict(config)
    except Exception as e:
        issues.append(str(e))

    return issues
