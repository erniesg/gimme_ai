# gimme_ai/__init__.py
"""Secure API gateway management for AI services."""

from .cli import cli
from .config import GimmeConfig, create_default_config
from .deploy import (
    DeploymentResult,
    DeploymentStatus,
    generate_deployment_files,
    deploy_to_cloudflare
)

__version__ = "0.1.0"
