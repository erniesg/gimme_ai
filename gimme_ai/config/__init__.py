"""Configuration management for gimme_ai."""

from .schema import (
    GimmeConfig,
    RateLimits,
    Endpoints,
    create_default_config,
    validate_config,
)

import json
from pathlib import Path
from typing import Dict, Any, List, Optional

__all__ = [
    "GimmeConfig",
    "RateLimits",
    "Endpoints",
    "create_default_config",
    "validate_config",
]

def load_config(config_file: str) -> GimmeConfig:
    """Load configuration from a file."""
    try:
        with open(config_file, "r") as f:
            config_data = json.load(f)

        # Validate config
        issues = validate_config(config_data)
        if issues:
            issues_str = "\n- ".join(issues)
            raise ValueError(f"Invalid configuration:\n- {issues_str}")

        return GimmeConfig.from_dict(config_data)
    except FileNotFoundError:
        raise FileNotFoundError(f"Configuration file not found: {config_file}")
    except json.JSONDecodeError:
        raise ValueError(f"Invalid JSON in configuration file: {config_file}")
