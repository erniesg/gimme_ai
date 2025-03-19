"""Deployment commands for the gimme_ai CLI."""

import os
import json
import sys
import click
import logging
from typing import Optional
from pathlib import Path

from ..config import (
    GimmeConfig,
    validate_config,
)
from ..utils.environment import load_env_file, validate_env_vars
from ..deploy.cloudflare import (
    generate_deployment_files,
    deploy_to_cloudflare,
    check_cloudflare_deps,
    DeploymentResult
)
from ..deploy.templates import (
    generate_worker_script,
    generate_durable_objects_script,
    generate_wrangler_toml
)

logger = logging.getLogger(__name__)

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
def deploy_command(
    config_file: str,
    env_file: str,
    dry_run: bool,
    output_dir: Optional[str] = None,
    verbose: bool = False
):
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

    # Read workflow type directly from config
    workflow_type = "disabled"
    if hasattr(config, 'workflow') and getattr(config.workflow, 'enabled', False):
        workflow_type = getattr(config.workflow, 'type', 'dual')
        logger.info(f"Using workflow type from config: {workflow_type}")

    # Pass the workflow type to generate_deployment_files
    deployment_files = generate_deployment_files(config, output_path)

    logger.info(f"Worker script: {deployment_files.worker_script}")
    logger.info(f"Durable Objects script: {deployment_files.durable_objects_script}")
    logger.info(f"Wrangler config: {deployment_files.wrangler_config}")

    if deployment_files.workflow_script:
        logger.info(f"Workflow script: {deployment_files.workflow_script}")

    if deployment_files.workflow_utils_script:
        logger.info(f"Workflow utils script: {deployment_files.workflow_utils_script}")

    # If dry run, exit here
    if dry_run:
        logger.info("\nDry run completed. Files generated but not deployed.")
        return

    # Deploy to Cloudflare
    logger.info("\nDeploying to Cloudflare...")
    try:
        # Call deploy_to_cloudflare with the config
        result = deploy_to_cloudflare(config)

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
