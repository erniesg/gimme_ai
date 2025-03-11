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
)


@click.group()
@click.version_option()
def cli():
    """Manage secure API gateways for AI services."""
    pass


@cli.command(name="init")
@click.option(
    "--project-name",
    help="Name for your project",
    required=False,
)
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
@click.option(
    "--force",
    is_flag=True,
    help="Overwrite existing configuration",
)
def init_command(
    project_name: Optional[str],
    config_file: str,
    env_file: str,
    force: bool,
):
    """Initialize a new gimme_ai configuration."""
    try:
        # Check if configuration already exists
        if os.path.exists(config_file) and not force:
            if not click.confirm(
                f"Configuration file {config_file} already exists. Overwrite?"
            ):
                click.echo("Initialization cancelled.")
                return

        # Load existing environment if available
        env_exists = os.path.exists(env_file)
        try:
            env_vars = load_env_file(env_file) if env_exists else {}
        except ValueError as e:
            click.echo(f"Error reading environment file: {e}", err=True)
            if not click.confirm("Continue with empty environment?"):
                sys.exit(1)
            env_vars = {}

        # Get or prompt for project name
        if not project_name:
            if "GIMME_PROJECT_NAME" in env_vars:
                project_name = env_vars["GIMME_PROJECT_NAME"]
                click.echo(f"Using project name from environment: {project_name}")
            else:
                try:
                    project_name = get_env_or_prompt(
                        "GIMME_PROJECT_NAME",
                        prompt="Enter a name for your project",
                        default="my-ai-gateway"
                    )
                except ImportError as e:
                    click.echo(f"Error: {e}", err=True)
                    click.echo("Please install inquirer: pip install inquirer", err=True)
                    sys.exit(1)

        # Create default configuration
        config = create_default_config(project_name)

        # Save configuration
        with open(config_file, "w") as f:
            json.dump(config, f, indent=2)

        click.echo(f"Configuration saved to {config_file}")

        # Update environment variables
        env_vars["GIMME_PROJECT_NAME"] = project_name

        # Ensure admin password is set
        if "GIMME_ADMIN_PASSWORD" not in env_vars:
            try:
                admin_password = get_env_or_prompt(
                    "GIMME_ADMIN_PASSWORD",
                    prompt="Enter admin password for your gateway",
                    default="generate-secure-password"
                )
                env_vars["GIMME_ADMIN_PASSWORD"] = admin_password
            except ImportError as e:
                click.echo(f"Error: {e}", err=True)
                click.echo("Please install inquirer: pip install inquirer", err=True)
                sys.exit(1)

        # Create or update .env file
        save_env_file(env_file, env_vars)

        # Create .env.example with required fields
        example_env = {
            "GIMME_PROJECT_NAME": project_name,
            "GIMME_ADMIN_PASSWORD": "your-secure-admin-password"
        }

        # Add required API keys to example
        for key in config["required_keys"]:
            example_env[key] = "your-api-key-here"

        save_env_file(f"{env_file}.example", example_env)

        click.echo(f"Environment file saved to {env_file}")
        click.echo(f"Example environment saved to {env_file}.example")

        click.echo("\nInitialization complete!")
        click.echo("Next steps:")
        click.echo(f"1. Edit {config_file} to customize your configuration")
        click.echo(f"2. Ensure all required API keys are in {env_file}")
        click.echo("3. Run 'gimme-ai deploy' to deploy your gateway")

    except Exception as e:
        click.echo(f"Error during initialization: {e}", err=True)
        sys.exit(1)


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
