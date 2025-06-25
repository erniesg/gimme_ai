"""
Secure secrets management for gimme_ai workflows.
Supports multiple backends: env files, AWS Secrets Manager, HashiCorp Vault, etc.
"""

import os
import json
import logging
from typing import Dict, Any, Optional, Union, List
from pathlib import Path
from enum import Enum
from dataclasses import dataclass, field
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class SecretBackend(Enum):
    """Supported secret management backends."""
    ENV_FILE = "env_file"
    ENVIRONMENT = "environment"
    AWS_SECRETS = "aws_secrets"
    VAULT = "vault"
    AZURE_KEYVAULT = "azure_keyvault"


@dataclass
class SecretDefinition:
    """Definition of a required secret."""
    name: str
    description: str
    required: bool = True
    environments: List[str] = field(default_factory=lambda: ["development", "staging", "production"])
    validation_regex: Optional[str] = None
    sensitive: bool = True


class SecretProvider(ABC):
    """Abstract base class for secret providers."""
    
    @abstractmethod
    def get_secret(self, key: str) -> Optional[str]:
        """Get a secret value by key."""
        pass
    
    @abstractmethod
    def list_secrets(self) -> List[str]:
        """List available secret keys."""
        pass
    
    @abstractmethod
    def health_check(self) -> bool:
        """Check if the provider is healthy."""
        pass


class EnvironmentSecretProvider(SecretProvider):
    """Provider for environment variables."""
    
    def get_secret(self, key: str) -> Optional[str]:
        return os.getenv(key)
    
    def list_secrets(self) -> List[str]:
        return list(os.environ.keys())
    
    def health_check(self) -> bool:
        return True


class EnvFileSecretProvider(SecretProvider):
    """Provider for .env files with environment-specific support."""
    
    def __init__(self, env_file: Optional[str] = None, environment: str = "development"):
        self.environment = environment
        self.secrets: Dict[str, str] = {}
        
        # Load environment-specific env file
        if env_file:
            env_paths = [env_file]
        else:
            env_paths = [
                f".env.{environment}",
                f".env.{environment}.local",
                ".env.local",
                ".env"
            ]
        
        for env_path in env_paths:
            if os.path.exists(env_path):
                self._load_env_file(env_path)
                logger.debug(f"Loaded secrets from {env_path}")
                break
        else:
            logger.warning(f"No env file found for environment: {environment}")
    
    def _load_env_file(self, file_path: str) -> None:
        """Load secrets from env file."""
        try:
            with open(file_path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        # Remove quotes if present
                        value = value.strip('"\'')
                        self.secrets[key.strip()] = value
        except Exception as e:
            logger.error(f"Failed to load env file {file_path}: {e}")
    
    def get_secret(self, key: str) -> Optional[str]:
        return self.secrets.get(key)
    
    def list_secrets(self) -> List[str]:
        return list(self.secrets.keys())
    
    def health_check(self) -> bool:
        return True


class AWSSecretsProvider(SecretProvider):
    """Provider for AWS Secrets Manager."""
    
    def __init__(self, region: str = "us-east-1"):
        try:
            import boto3
            self.client = boto3.client('secretsmanager', region_name=region)
            self._cache: Dict[str, str] = {}
        except ImportError:
            raise ImportError("boto3 required for AWS Secrets Manager support")
    
    def get_secret(self, key: str) -> Optional[str]:
        if key in self._cache:
            return self._cache[key]
        
        try:
            response = self.client.get_secret_value(SecretId=key)
            secret_value = response['SecretString']
            self._cache[key] = secret_value
            return secret_value
        except Exception as e:
            logger.error(f"Failed to get secret {key}: {e}")
            return None
    
    def list_secrets(self) -> List[str]:
        try:
            response = self.client.list_secrets()
            return [secret['Name'] for secret in response['SecretList']]
        except Exception as e:
            logger.error(f"Failed to list secrets: {e}")
            return []
    
    def health_check(self) -> bool:
        try:
            self.client.list_secrets(MaxResults=1)
            return True
        except Exception:
            return False


class SecretsManager:
    """Centralized secrets management with multiple backend support."""
    
    # Standard secret definitions for gimme_ai
    STANDARD_SECRETS = [
        # Core API keys
        SecretDefinition(
            name="OPENAI_API_KEY",
            description="OpenAI API key for GPT models",
            validation_regex=r"^sk-"
        ),
        SecretDefinition(
            name="REPLICATE_API_TOKEN", 
            description="Replicate API token for image generation",
            validation_regex=r"^r8_"
        ),
        SecretDefinition(
            name="ELEVENLABS_API_KEY",
            description="ElevenLabs API key for voice synthesis"
        ),
        
        # Cloudflare R2 Storage
        SecretDefinition(
            name="CLOUDFLARE_ACCOUNT_ID",
            description="Cloudflare account ID for R2 storage",
            required=False
        ),
        SecretDefinition(
            name="R2_ACCESS_KEY_ID",
            description="R2 access key ID",
            required=False
        ),
        SecretDefinition(
            name="R2_SECRET_ACCESS_KEY",
            description="R2 secret access key", 
            required=False
        ),
        
        # Deployment secrets
        SecretDefinition(
            name="CLOUDFLARE_API_TOKEN",
            description="Cloudflare API token for deployment",
            environments=["staging", "production"]
        ),
        
        # Admin credentials
        SecretDefinition(
            name="GIMME_ADMIN_PASSWORD",
            description="Admin password for gimme_ai gateway"
        ),
        
        # Optional integrations
        SecretDefinition(
            name="RUNWAY_API_KEY",
            description="Runway ML API key for video effects",
            required=False
        ),
        SecretDefinition(
            name="ASSEMBLY_API_KEY", 
            description="Assembly AI API key for video processing",
            required=False
        ),
        
        # Monitoring and webhooks
        SecretDefinition(
            name="WEBHOOK_URL",
            description="Webhook URL for workflow notifications",
            required=False
        ),
        SecretDefinition(
            name="SENTRY_DSN",
            description="Sentry DSN for error tracking", 
            required=False
        )
    ]
    
    def __init__(self, 
                 backend: SecretBackend = SecretBackend.ENV_FILE,
                 environment: str = "development",
                 **backend_kwargs):
        """
        Initialize secrets manager.
        
        Args:
            backend: Secret backend to use
            environment: Current environment (development/staging/production)
            **backend_kwargs: Backend-specific configuration
        """
        self.environment = environment
        self.backend = backend
        
        # Initialize provider based on backend
        if backend == SecretBackend.ENV_FILE:
            self.provider = EnvFileSecretProvider(environment=environment, **backend_kwargs)
        elif backend == SecretBackend.ENVIRONMENT:
            self.provider = EnvironmentSecretProvider()
        elif backend == SecretBackend.AWS_SECRETS:
            self.provider = AWSSecretsProvider(**backend_kwargs)
        else:
            raise ValueError(f"Unsupported backend: {backend}")
        
        logger.info(f"Initialized secrets manager with {backend.value} backend for {environment}")
    
    def get_secret(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """Get a secret value."""
        value = self.provider.get_secret(key)
        if value is None:
            return default
        return value
    
    def get_required_secret(self, key: str) -> str:
        """Get a required secret, raising error if not found."""
        value = self.get_secret(key)
        if value is None:
            raise ValueError(f"Required secret '{key}' not found")
        return value
    
    def validate_secrets(self, required_only: bool = False) -> Dict[str, Any]:
        """
        Validate all defined secrets.
        
        Args:
            required_only: Only validate required secrets
            
        Returns:
            Validation report with status, missing secrets, and invalid values
        """
        report = {
            "valid": True,
            "missing_required": [],
            "missing_optional": [],
            "invalid_format": [],
            "available_secrets": []
        }
        
        secrets_to_check = [s for s in self.STANDARD_SECRETS if self.environment in s.environments]
        if required_only:
            secrets_to_check = [s for s in secrets_to_check if s.required]
        
        for secret_def in secrets_to_check:
            value = self.get_secret(secret_def.name)
            
            if value is None:
                if secret_def.required:
                    report["missing_required"].append({
                        "name": secret_def.name,
                        "description": secret_def.description
                    })
                    report["valid"] = False
                else:
                    report["missing_optional"].append({
                        "name": secret_def.name,
                        "description": secret_def.description
                    })
            else:
                # Validate format if regex provided
                if secret_def.validation_regex:
                    import re
                    if not re.match(secret_def.validation_regex, value):
                        report["invalid_format"].append({
                            "name": secret_def.name,
                            "description": secret_def.description,
                            "expected_format": secret_def.validation_regex
                        })
                        report["valid"] = False
                
                # Add to available (without exposing sensitive values)
                if secret_def.sensitive:
                    masked_value = f"{value[:4]}***{value[-4:]}" if len(value) > 8 else "***"
                else:
                    masked_value = value
                
                report["available_secrets"].append({
                    "name": secret_def.name,
                    "value": masked_value
                })
        
        return report
    
    def generate_env_template(self, environment: str = "development") -> str:
        """Generate .env template file for given environment."""
        template_lines = [
            f"# gimme_ai environment configuration for {environment}",
            f"# Generated automatically - customize as needed",
            "",
            "# ==== CORE API KEYS ===="
        ]
        
        secrets_for_env = [s for s in self.STANDARD_SECRETS if environment in s.environments]
        
        # Group secrets by category
        categories = {
            "CORE API KEYS": ["OPENAI_API_KEY", "REPLICATE_API_TOKEN", "ELEVENLABS_API_KEY"],
            "STORAGE & CDN": ["CLOUDFLARE_ACCOUNT_ID", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY"],
            "DEPLOYMENT": ["CLOUDFLARE_API_TOKEN", "GIMME_ADMIN_PASSWORD"],
            "OPTIONAL INTEGRATIONS": ["RUNWAY_API_KEY", "ASSEMBLY_API_KEY"],
            "MONITORING": ["WEBHOOK_URL", "SENTRY_DSN"]
        }
        
        for category, secret_names in categories.items():
            category_secrets = [s for s in secrets_for_env if s.name in secret_names]
            if category_secrets:
                template_lines.extend([
                    "",
                    f"# ==== {category} ===="
                ])
                
                for secret in category_secrets:
                    required_marker = "" if secret.required else "# [OPTIONAL] "
                    template_lines.append(f"{required_marker}{secret.name}=  # {secret.description}")
        
        template_lines.extend([
            "",
            "# ==== ENVIRONMENT SETTINGS ====",
            f"GIMME_ENVIRONMENT={environment}",
            "GIMME_LOG_LEVEL=INFO",
            ""
        ])
        
        return "\n".join(template_lines)
    
    def health_check(self) -> bool:
        """Check if secrets backend is healthy."""
        return self.provider.health_check()
    
    def export_for_workflow(self, workflow_secrets: List[str]) -> Dict[str, str]:
        """Export specific secrets for workflow execution."""
        exported = {}
        for secret_name in workflow_secrets:
            value = self.get_secret(secret_name)
            if value is not None:
                exported[secret_name] = value
        return exported


# Singleton instance for global access
_secrets_manager: Optional[SecretsManager] = None


def get_secrets_manager(
    backend: SecretBackend = SecretBackend.ENV_FILE,
    environment: Optional[str] = None,
    **kwargs
) -> SecretsManager:
    """Get or create global secrets manager instance."""
    global _secrets_manager
    
    if environment is None:
        environment = os.getenv("GIMME_ENVIRONMENT", "development")
    
    if _secrets_manager is None:
        _secrets_manager = SecretsManager(backend=backend, environment=environment, **kwargs)
    
    return _secrets_manager


def init_secrets_manager(**kwargs) -> SecretsManager:
    """Initialize secrets manager with custom configuration."""
    global _secrets_manager
    _secrets_manager = None  # Reset singleton
    return get_secrets_manager(**kwargs)