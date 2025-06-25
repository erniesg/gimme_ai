# gimme_ai/cli/commands.py
"""Command-line interface for gimme_ai."""

import os
import json
import sys
import click
from typing import Optional
from ..config import (
    GimmeConfig,
    create_default_config,
    validate_config,
)
from ..utils.environment import (
    load_env_file,
    save_env_file,
    validate_env_vars,
    get_env_or_prompt,
    _safe_import_inquirer,
)
import logging
from pathlib import Path
from ..deploy.cloudflare import generate_deployment_files, deploy_to_cloudflare, check_cloudflare_deps, DeploymentResult
from ..deploy.templates import (
    generate_worker_script,
    generate_durable_objects_script,
    generate_wrangler_toml
)
import requests
import time
from tabulate import tabulate
import inquirer

# Import commands from other modules
from .commands_init import init_command
from .commands_deploy import deploy_command
from .commands_workflow import workflow_command
from .commands_workflow_new import workflow_group
from .commands_secrets import secrets_group
from .commands_test import (
    test_command,
    test_auth_command,
    test_rate_limits_command,
    test_workflow_command,
    test_all_command,
    test_workflow_type_command,
)

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

print("Loading commands.py")

@click.group()
@click.version_option()
def cli():
    """Manage secure API gateways for AI services."""
    pass

@cli.command(name="validate")
@click.option(
    "--config-file",
    default=".gimme-config.json",
    help="Path to configuration file",
    show_default=True,
)
@click.option(
    "--env-file",
    default=".env",
    help="Path to environment file",
    show_default=True,
)
def validate_command(config_file: str, env_file: str):
    """Validate configuration and environment."""
    # Check if configuration exists
    if not os.path.exists(config_file):
        click.echo(f"Error: Configuration file {config_file} not found", err=True)
        sys.exit(1)

    # Load and validate configuration
    try:
        with open(config_file, "r") as f:
            config_data = json.load(f)

        issues = validate_config(config_data)
        if issues:
            click.echo("Configuration validation failed:", err=True)
            for issue in issues:
                click.echo(f"- {issue}", err=True)
            sys.exit(1)

        config = GimmeConfig.from_dict(config_data)
        click.echo("Configuration validation passed!")

    except json.JSONDecodeError as e:
        click.echo(f"Error: Invalid JSON in configuration file: {e}", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"Error loading configuration: {e}", err=True)
        sys.exit(1)

    # Load and validate environment
    if not os.path.exists(env_file):
        click.echo(f"Warning: Environment file {env_file} not found", err=True)
    else:
        try:
            env_vars = load_env_file(env_file)

            # Set environment variables temporarily for validation
            original_env = {}
            try:
                for key, value in env_vars.items():
                    original_env[key] = os.environ.get(key)
                    os.environ[key] = value

                # Validate required keys
                missing = validate_env_vars([config.admin_password_env] + config.required_keys)

                if missing:
                    click.echo("Environment validation failed:", err=True)
                    for var in missing:
                        click.echo(f"- Missing {var}", err=True)
                    sys.exit(1)

                click.echo("Environment validation passed!")

            finally:
                # Restore original environment
                for key, value in original_env.items():
                    if value is None:
                        os.environ.pop(key, None)
                    else:
                        os.environ[key] = value

        except ValueError as e:
            click.echo(f"Error: {e}", err=True)
            sys.exit(1)

    click.echo("All validations passed successfully!")

@click.command()
@click.argument('workflow_type', type=click.Choice(['api', 'video']))
@click.argument('url', required=False)
@click.option('--verbose', is_flag=True, help='Print verbose output')
@click.option('--admin-password', help='Admin password for authentication')
@click.option('--env-file', default='.env', help='Path to environment file')
def test_workflow_type_command_click(workflow_type, url, verbose, admin_password=None, env_file='.env'):
    """Test a specific workflow type."""
    print("Command executed: test-workflow-type", workflow_type, url)

    # Call the function directly, not the Click command
    from .commands_test import test_workflow_type  # Import the function

    try:
        # Get admin password from env file if not provided
        from .commands_test import get_admin_password
        admin_pw = get_admin_password(admin_password, env_file)

        success = test_workflow_type(workflow_type, url, verbose, admin_pw)
        if not success:
            sys.exit(1)
    except Exception as e:
        print(f"Error testing workflow type: {e}")
        import traceback
        print(traceback.format_exc())
        sys.exit(1)

# Register all commands
cli.add_command(init_command)
cli.add_command(deploy_command)
cli.add_command(workflow_command)
cli.add_command(workflow_group, name='wf')  # New workflow engine commands
cli.add_command(secrets_group)  # Secrets management commands
cli.add_command(test_command)
cli.add_command(test_auth_command)
cli.add_command(test_rate_limits_command)
cli.add_command(test_workflow_command)
cli.add_command(test_all_command)
cli.add_command(test_workflow_type_command_click, name='test-workflow-type')
