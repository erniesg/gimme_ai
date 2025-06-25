"""
Cloudflare Workers secrets synchronization for gimme_ai.
Handles syncing local secrets to Cloudflare Workers environment.
"""

import os
import subprocess
import logging
from typing import Dict, List, Optional, Tuple
from pathlib import Path

from ..config.secrets import get_secrets_manager, SecretBackend

logger = logging.getLogger(__name__)


class CloudflareSecretsManager:
    """Manages secrets synchronization with Cloudflare Workers."""
    
    def __init__(self, project_name: str, environment: str = "production"):
        self.project_name = project_name
        self.environment = environment
        self.secrets_manager = get_secrets_manager(
            backend=SecretBackend.ENV_FILE,
            environment=environment
        )
    
    def check_wrangler_available(self) -> bool:
        """Check if wrangler CLI is available."""
        try:
            result = subprocess.run(
                ["wrangler", "--version"], 
                capture_output=True, 
                text=True
            )
            return result.returncode == 0
        except FileNotFoundError:
            return False
    
    def list_worker_secrets(self) -> List[str]:
        """List secrets currently set in Cloudflare Worker."""
        if not self.check_wrangler_available():
            raise RuntimeError("wrangler CLI not available")
        
        try:
            result = subprocess.run(
                ["wrangler", "secret", "list"],
                capture_output=True,
                text=True,
                check=True
            )
            
            # Parse wrangler output to extract secret names
            secrets = []
            for line in result.stdout.split('\n'):
                line = line.strip()
                # Skip headers and empty lines
                if line and not line.startswith('Name') and not line.startswith('---'):
                    # Extract secret name (first column)
                    secret_name = line.split()[0]
                    secrets.append(secret_name)
            
            return secrets
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to list worker secrets: {e}")
            return []
    
    def set_worker_secret(self, secret_name: str, secret_value: str) -> bool:
        """Set a secret in Cloudflare Worker."""
        if not self.check_wrangler_available():
            raise RuntimeError("wrangler CLI not available")
        
        try:
            # Use echo to pipe the secret value to wrangler
            echo_proc = subprocess.Popen(
                ["echo", secret_value],
                stdout=subprocess.PIPE
            )
            
            wrangler_proc = subprocess.Popen(
                ["wrangler", "secret", "put", secret_name],
                stdin=echo_proc.stdout,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            echo_proc.stdout.close()
            stdout, stderr = wrangler_proc.communicate()
            
            if wrangler_proc.returncode == 0:
                logger.info(f"Successfully set secret: {secret_name}")
                return True
            else:
                logger.error(f"Failed to set secret {secret_name}: {stderr}")
                return False
                
        except Exception as e:
            logger.error(f"Error setting secret {secret_name}: {e}")
            return False
    
    def delete_worker_secret(self, secret_name: str) -> bool:
        """Delete a secret from Cloudflare Worker."""
        if not self.check_wrangler_available():
            raise RuntimeError("wrangler CLI not available")
        
        try:
            result = subprocess.run(
                ["wrangler", "secret", "delete", secret_name, "--force"],
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                logger.info(f"Successfully deleted secret: {secret_name}")
                return True
            else:
                logger.error(f"Failed to delete secret {secret_name}: {result.stderr}")
                return False
                
        except Exception as e:
            logger.error(f"Error deleting secret {secret_name}: {e}")
            return False
    
    def sync_secrets(self, 
                    secrets_to_sync: Optional[List[str]] = None,
                    dry_run: bool = False) -> Tuple[Dict[str, bool], List[str]]:
        """
        Sync local secrets to Cloudflare Worker.
        
        Args:
            secrets_to_sync: List of secret names to sync (None = sync all required)
            dry_run: If True, show what would be synced without doing it
            
        Returns:
            Tuple of (sync_results, errors)
        """
        results = {}
        errors = []
        
        # Determine which secrets to sync
        if secrets_to_sync is None:
            # Get required secrets for this environment
            report = self.secrets_manager.validate_secrets(required_only=True)
            secrets_to_sync = [s["name"] for s in report["available_secrets"]]
        
        # Get current worker secrets
        if not dry_run:
            try:
                current_worker_secrets = self.list_worker_secrets()
            except Exception as e:
                errors.append(f"Failed to list current worker secrets: {e}")
                return results, errors
        else:
            current_worker_secrets = []
        
        # Sync each secret
        for secret_name in secrets_to_sync:
            try:
                secret_value = self.secrets_manager.get_secret(secret_name)
                
                if secret_value is None:
                    errors.append(f"Secret {secret_name} not found in local environment")
                    results[secret_name] = False
                    continue
                
                if dry_run:
                    print(f"Would sync: {secret_name}")
                    results[secret_name] = True
                else:
                    success = self.set_worker_secret(secret_name, secret_value)
                    results[secret_name] = success
                    
                    if not success:
                        errors.append(f"Failed to sync secret: {secret_name}")
            
            except Exception as e:
                errors.append(f"Error syncing {secret_name}: {e}")
                results[secret_name] = False
        
        return results, errors
    
    def validate_worker_secrets(self) -> Dict[str, any]:
        """Validate that all required secrets are set in the worker."""
        report = {
            "valid": True,
            "missing_secrets": [],
            "extra_secrets": [],
            "total_worker_secrets": 0
        }
        
        try:
            # Get required secrets from local validation
            local_report = self.secrets_manager.validate_secrets(required_only=True)
            required_secrets = {s["name"] for s in local_report["available_secrets"]}
            
            # Get current worker secrets
            worker_secrets = set(self.list_worker_secrets())
            report["total_worker_secrets"] = len(worker_secrets)
            
            # Check for missing required secrets
            missing = required_secrets - worker_secrets
            if missing:
                report["missing_secrets"] = list(missing)
                report["valid"] = False
            
            # Check for extra secrets (informational)
            extra = worker_secrets - required_secrets
            if extra:
                report["extra_secrets"] = list(extra)
            
        except Exception as e:
            report["valid"] = False
            report["error"] = str(e)
        
        return report


def sync_secrets_to_cloudflare(
    project_name: str,
    environment: str = "production",
    secrets_filter: Optional[List[str]] = None,
    dry_run: bool = False
) -> bool:
    """
    Convenience function to sync secrets to Cloudflare Workers.
    
    Args:
        project_name: Name of the project/worker
        environment: Environment to sync from (staging/production)
        secrets_filter: Optional list of specific secrets to sync
        dry_run: If True, show what would be synced
        
    Returns:
        True if successful, False otherwise
    """
    try:
        manager = CloudflareSecretsManager(project_name, environment)
        
        if not manager.check_wrangler_available():
            logger.error("wrangler CLI not available. Install with: npm install -g wrangler")
            return False
        
        logger.info(f"Syncing secrets from {environment} environment to Cloudflare Worker")
        
        results, errors = manager.sync_secrets(secrets_filter, dry_run)
        
        if errors:
            for error in errors:
                logger.error(error)
        
        success_count = sum(1 for success in results.values() if success)
        total_count = len(results)
        
        if dry_run:
            logger.info(f"Dry run: Would sync {total_count} secrets")
        else:
            logger.info(f"Synced {success_count}/{total_count} secrets successfully")
        
        return len(errors) == 0 and success_count == total_count
        
    except Exception as e:
        logger.error(f"Error syncing secrets: {e}")
        return False