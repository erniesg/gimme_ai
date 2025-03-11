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
import logging
from pathlib import Path
from ..deploy.cloudflare import generate_deployment_files, deploy_to_cloudflare, check_cloudflare_deps, DeploymentResult
from ..deploy.templates import (
    generate_worker_script,
    generate_durable_objects_script,
    generate_wrangler_toml
)
# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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

        # Required environment variables
        required_env_vars = [
            "GIMME_ADMIN_PASSWORD",
            "CLOUDFLARE_API_TOKEN",
            "MODAL_TOKEN_ID",
            "MODAL_TOKEN_SECRET"
        ]

        # Ensure all required environment variables are set
        for var in required_env_vars:
            if var not in env_vars:
                try:
                    env_vars[var] = get_env_or_prompt(
                        var,
                        prompt=f"Enter value for {var}",
                        default=f"your-{var.lower().replace('_', '-')}-here"
                    )
                except ImportError as e:
                    click.echo(f"Error: {e}", err=True)
                    click.echo("Please install inquirer: pip install inquirer", err=True)
                    sys.exit(1)

        # Create or update .env file
        save_env_file(env_file, env_vars)

        # Create .env.example with required fields
        example_env = {var: f"your-{var.lower().replace('_', '-')}-here" for var in required_env_vars}
        example_env["GIMME_PROJECT_NAME"] = project_name

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

@click.command(name="deploy")
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
    "--dry-run",
    is_flag=True,
    help="Generate deployment files without deploying",
)
@click.option(
    "--output-dir",
    help="Directory for deployment files (overrides config file setting)",
)
@click.option(
    "--verbose",
    is_flag=True,
    help="Enable verbose output",
)
def deploy_command(config_file: str, env_file: str, dry_run: bool, output_dir: Optional[str] = None, verbose: bool = False):
    """Deploy your API gateway to Cloudflare."""
    if verbose:
        logger.setLevel(logging.DEBUG)

    logger.info("Starting deployment process...")

    # Check if configuration exists
    if not os.path.exists(config_file):
        logger.error(f"Error: Configuration file {config_file} not found")
        sys.exit(1)

    # Load configuration
    try:
        with open(config_file, "r") as f:
            config_data = json.load(f)

        config = GimmeConfig.from_dict(config_data)
        logger.debug(f"Loaded configuration: {config}")

    except Exception as e:
        logger.error(f"Error loading configuration: {e}")
        sys.exit(1)

    # Determine output directory
    if output_dir:
        output_path = Path(output_dir)
    else:
        output_path = Path(config_data.get("output_dir", f"output/{config.project_name}"))

    os.makedirs(output_path, exist_ok=True)
    logger.info(f"Using output directory: {output_path}")

    # Load environment variables
    if os.path.exists(env_file):
        try:
            env_vars = load_env_file(env_file)
            logger.debug(f"Loaded environment variables: {env_vars}")

            # Add to environment
            for key, value in env_vars.items():
                os.environ[key] = value

        except Exception as e:
            logger.error(f"Error loading environment: {e}")
            sys.exit(1)

    # Validate environment variables
    missing = validate_env_vars([config.admin_password_env] + config.required_keys)
    if missing:
        logger.error("Error: Missing required environment variables:")
        for var in missing:
            logger.error(f"- {var}")
        sys.exit(1)

    # Check Cloudflare dependencies if not dry run
    if not dry_run:
        logger.info("Checking Cloudflare dependencies...")
        if not check_cloudflare_deps():
            logger.error("Cloudflare dependencies not found. Please install wrangler:")
            logger.error("npm install -g wrangler")
            sys.exit(1)

    # Generate deployment files
    logger.info("Generating deployment files...")
    try:
        # Pass the output_path to the generation functions
        worker_script_path = generate_worker_script(config, output_path)
        durable_objects_script_path = generate_durable_objects_script(config, output_path)
        wrangler_config_path = generate_wrangler_toml(config, output_path)

        logger.info(f"Worker script generated: {worker_script_path}")
        logger.info(f"Durable Objects script generated: {durable_objects_script_path}")
        logger.info(f"Wrangler config generated: {wrangler_config_path}")

        # If dry run, exit here
        if dry_run:
            logger.info("\nDry run completed. Files generated but not deployed.")
            return

        # Deploy to Cloudflare
        logger.info("\nDeploying to Cloudflare...")
        try:
            # Create a DeploymentResult object with the paths to the generated files
            deployment_files = DeploymentResult(
                worker_script=worker_script_path,
                durable_objects_script=durable_objects_script_path,
                wrangler_config=wrangler_config_path
            )

            # Call deploy_to_cloudflare with the config and deployment_files
            result = deploy_to_cloudflare(config, deployment_files)

            if result.success:
                logger.info(f"\n✅ {result.message}")
                if result.url:
                    logger.info(f"\nYour API gateway is available at: {result.url}")
                    logger.info("\nYou can now use this URL in your frontend applications.")

                # Output usage examples
                logger.info("\nUsage examples:")
                logger.info("  Free tier access:")
                logger.info(f"  fetch('{result.url or 'https://your-gateway.workers.dev'}/your-endpoint')")

                logger.info("\n  Admin access:")
                logger.info(f"  fetch('{result.url or 'https://your-gateway.workers.dev'}/your-endpoint', {{")
                logger.info("    headers: {")
                logger.info("      'Authorization': 'Bearer your-admin-password'")
                logger.info("    }")
                logger.info("  })")
            else:
                logger.error(f"\n❌ {result.message}")
                sys.exit(1)

        except Exception as e:
            logger.error(f"Error during deployment: {e}")
            sys.exit(1)

    except Exception as e:
        logger.error(f"Error during deployment: {e}")
        sys.exit(1)

# Register the deploy command
cli.add_command(deploy_command)

# Register other commands
cli.add_command(init_command)
cli.add_command(validate_command)
