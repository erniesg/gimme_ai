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
        click.echo("🚀 Welcome to Gimme-AI setup!")

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
            # Use current directory name as default
            current_dir = os.path.basename(os.getcwd())
            default_name = current_dir.lower().replace('_', '-').replace(' ', '-')

            if "GIMME_PROJECT_NAME" in env_vars:
                project_name = env_vars["GIMME_PROJECT_NAME"]
                click.echo(f"Using project name from environment: {project_name}")
            else:
                try:
                    inquirer = _safe_import_inquirer()
                    questions = [
                        inquirer.Text(
                            "project_name",
                            message="Project name",
                            default=default_name
                        )
                    ]
                    answers = inquirer.prompt(questions)
                    project_name = answers["project_name"]
                except ImportError as e:
                    click.echo(f"Error: {e}", err=True)
                    project_name = click.prompt("Project name", default=default_name)

        click.echo(f"\n📋 Required credentials:")

        # Handle admin password
        admin_password_env = "GIMME_ADMIN_PASSWORD"
        if admin_password_env not in env_vars:
            try:
                generate_password = click.confirm(f"{admin_password_env} [generate secure password?]", default=True)
                if generate_password:
                    # Generate a secure password
                    import secrets
                    import string
                    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
                    password = ''.join(secrets.choice(alphabet) for _ in range(12))
                    env_vars[admin_password_env] = password
                    click.echo(f"✅ Generated password: {password} (saved to {env_file})")
                else:
                    password = click.prompt(f"{admin_password_env}", hide_input=True, confirmation_prompt=True)
                    env_vars[admin_password_env] = password
                    click.echo(f"✅ Password saved to {env_file}")
            except ImportError as e:
                click.echo(f"Error: {e}", err=True)
                password = click.prompt(f"{admin_password_env}", hide_input=True, confirmation_prompt=True)
                env_vars[admin_password_env] = password

        # Handle Cloudflare API token
        cf_token_env = "CLOUDFLARE_API_TOKEN"
        if cf_token_env not in env_vars:
            click.echo(f"\n{cf_token_env}:")
            click.echo("ℹ️ Don't have a token? Create one at https://dash.cloudflare.com/profile/api-tokens")
            token = click.prompt(f"{cf_token_env}", hide_input=True)
            env_vars[cf_token_env] = token

        # Create default configuration
        config = create_default_config(project_name)

        # Required API keys for backend
        click.echo("\n📦 Required API keys for your backend:")

        # Get required keys from config
        required_keys = config.get("required_keys", [])

        for key in required_keys:
            if key not in env_vars:
                value = click.prompt(f"{key}")
                env_vars[key] = value

        # Save configuration
        with open(config_file, "w") as f:
            json.dump(config, f, indent=2)

        # Create or update .env file
        save_env_file(env_file, env_vars)

        click.echo("\n✅ Configuration complete!")
        click.echo(f"✅ Created {env_file}")
        click.echo(f"✅ Created {config_file}")

        click.echo("\n🔍 Next steps:")
        click.echo(f"   1. Review your configuration in {config_file}")
        click.echo("   2. Run 'gimme-ai deploy' to deploy your gateway")

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

@cli.command(name="test")
@click.option(
    "--endpoint",
    help="Endpoint URL to test (e.g., https://your-project.workers.dev)",
    required=True,
)
@click.option(
    "--admin-password",
    help="Admin password for testing admin access",
    required=False,
)
@click.option(
    "--env-file",
    default=".env",
    help="Path to environment file (to get admin password)",
    show_default=True,
)
@click.option(
    "--config-file",
    default=".gimme-config.json",
    help="Path to configuration file",
    show_default=True,
)
@click.option(
    "--verbose",
    is_flag=True,
    help="Show detailed test output",
)
@click.option(
    "--skip-reset-confirm",
    is_flag=True,
    help="Skip confirmation for rate limit resets",
)
@click.option(
    "--retry-reset",
    is_flag=True,
    help="Retry reset operation if it fails",
    default=True,
)
def test_command(endpoint: str, admin_password: Optional[str], env_file: str, config_file: str,
                verbose: bool, skip_reset_confirm: bool, retry_reset: bool):
    """Test your deployed API gateway."""
    click.echo("🧪 Testing your API gateway...")

    # Load configuration if available
    config = None
    per_ip_limit = 10  # Default if config not available
    global_limit = 100  # Default if config not available
    try:
        if os.path.exists(config_file):
            with open(config_file, "r") as f:
                config_data = json.load(f)

            # Extract rate limits from config
            if "limits" in config_data and "free_tier" in config_data["limits"]:
                free_tier = config_data["limits"]["free_tier"]
                if isinstance(free_tier, dict):
                    if "per_ip" in free_tier:
                        per_ip_limit = free_tier["per_ip"]
                        click.echo(f"Using per-IP rate limit from config: {per_ip_limit}")

                    if "global" in free_tier:
                        global_limit = free_tier["global"]
                        click.echo(f"Using global rate limit from config: {global_limit}")
    except Exception as e:
        click.echo(f"Warning: Could not load configuration: {e}", err=True)
        click.echo("Using default rate limits: 10 per IP, 100 global")

    # Load admin password from env file if not provided
    if not admin_password and os.path.exists(env_file):
        try:
            env_vars = load_env_file(env_file)
            admin_password = env_vars.get("GIMME_ADMIN_PASSWORD")
            if admin_password:
                click.echo(f"Using admin password from {env_file}")
        except Exception as e:
            click.echo(f"Error loading environment: {e}", err=True)

    # Normalize endpoint URL
    if endpoint.endswith('/'):
        endpoint = endpoint[:-1]

    # Reset rate limits if admin password is available
    if admin_password:
        click.echo("\n🔄 Rate limits reset:")
        click.echo("ℹ️ Testing will reset rate limits on your API gateway.")
        click.echo("ℹ️ This will clear any existing rate limit counters.")

        # Ask for confirmation unless skip flag is set
        if skip_reset_confirm or click.confirm("Do you want to proceed with resetting rate limits?", default=True):
            reset_success = False
            max_retries = 3 if retry_reset else 1

            for attempt in range(max_retries):
                try:
                    headers = {"Authorization": f"Bearer {admin_password}"}
                    response = requests.get(f"{endpoint}/admin/reset-limits", headers=headers)

                    if response.status_code == 200:
                        click.echo("✅ Rate limits reset successfully")
                        reset_success = True
                        break
                    else:
                        click.echo(f"⚠️ Failed to reset rate limits: {response.status_code}")
                        if verbose:
                            click.echo(response.text)

                        if attempt < max_retries - 1:
                            click.echo(f"Retrying reset ({attempt+2}/{max_retries})...")
                            time.sleep(1)  # Wait a bit before retrying
                except Exception as e:
                    click.echo(f"⚠️ Error resetting rate limits: {e}")
                    if attempt < max_retries - 1:
                        click.echo(f"Retrying reset ({attempt+2}/{max_retries})...")
                        time.sleep(1)  # Wait a bit before retrying

            if not reset_success and not click.confirm("Continue testing without reset?", default=False):
                click.echo("Testing cancelled.")
                return
        else:
            click.echo("Reset cancelled. Testing will continue with existing rate limit state.")
    else:
        click.echo("\n⚠️ No admin password provided. Rate limits will not be reset.")
        click.echo("⚠️ Tests may fail if rate limits have been reached previously.")
        if not click.confirm("Continue testing without reset?", default=True):
            click.echo("Testing cancelled.")
            return

    # Run tests
    results = []

    # Test 1: Status endpoint
    click.echo("\n🔍 Testing status endpoint...")
    try:
        response = requests.get(f"{endpoint}/status")
        if response.status_code == 200:
            data = response.json()
            click.echo(f"✅ Status: {data.get('status', 'unknown')}")
            click.echo(f"✅ Project: {data.get('project', 'unknown')}")
            click.echo(f"✅ Mode: {data.get('mode', 'unknown')}")
            results.append(["Status Endpoint", "✅ PASS", response.status_code])
        else:
            click.echo(f"❌ Status endpoint failed: {response.status_code}")
            results.append(["Status Endpoint", "❌ FAIL", response.status_code])
            if verbose:
                click.echo(response.text)
    except Exception as e:
        click.echo(f"❌ Error testing status endpoint: {e}")
        results.append(["Status Endpoint", "❌ ERROR", str(e)])

    # Test 2: Free tier access
    click.echo("\n🔍 Testing free tier access...")
    try:
        response = requests.get(f"{endpoint}/api/test")
        if response.status_code in [200, 404]:  # 404 is ok if endpoint doesn't exist
            click.echo(f"✅ Free tier access: {response.status_code}")
            results.append(["Free Tier Access", "✅ PASS", response.status_code])
        elif response.status_code == 429:
            # Rate limit already reached - this is expected with lifetime limits
            click.echo("⚠️ Free tier already rate limited (expected with lifetime limits)")
            results.append(["Free Tier Access", "⚠️ EXPECTED", response.status_code])
        else:
            click.echo(f"❌ Free tier access failed: {response.status_code}")
            results.append(["Free Tier Access", "❌ FAIL", response.status_code])
            if verbose:
                click.echo(response.text)
    except Exception as e:
        click.echo(f"❌ Error testing free tier access: {e}")
        results.append(["Free Tier Access", "❌ ERROR", str(e)])

    # Test 3: Invalid admin password
    click.echo("\n🔍 Testing invalid admin password...")
    try:
        headers = {"Authorization": "Bearer invalid-password"}
        response = requests.get(f"{endpoint}/api/test", headers=headers)
        if response.status_code == 401:
            click.echo("✅ Invalid admin password correctly rejected")
            results.append(["Invalid Admin Auth", "✅ PASS", response.status_code])
        else:
            click.echo(f"❌ Invalid admin password not rejected: {response.status_code}")
            results.append(["Invalid Admin Auth", "❌ FAIL", response.status_code])
            if verbose:
                click.echo(response.text)
    except Exception as e:
        click.echo(f"❌ Error testing invalid admin password: {e}")
        results.append(["Invalid Admin Auth", "❌ ERROR", str(e)])

    # Test 4: Valid admin password (if provided)
    if admin_password:
        click.echo("\n🔍 Testing valid admin password...")
        try:
            headers = {"Authorization": f"Bearer {admin_password}"}
            response = requests.get(f"{endpoint}/api/test", headers=headers)
            if response.status_code in [200, 404]:  # 404 is ok if endpoint doesn't exist
                click.echo("✅ Admin access successful")
                results.append(["Admin Auth", "✅ PASS", response.status_code])
            else:
                click.echo(f"❌ Admin access failed: {response.status_code}")
                results.append(["Admin Auth", "❌ FAIL", response.status_code])
                if verbose:
                    click.echo(response.text)
        except Exception as e:
            click.echo(f"❌ Error testing admin access: {e}")
            results.append(["Admin Auth", "❌ ERROR", str(e)])
    else:
        click.echo("\n⚠️ Skipping admin password test (no password provided)")
        results.append(["Admin Auth", "⚠️ SKIPPED", "N/A"])

    # Test 5: Per-IP Rate limiting
    click.echo("\n🔍 Testing per-IP rate limiting...")
    try:
        # Reset limits if admin password is available
        if admin_password:
            headers = {"Authorization": f"Bearer {admin_password}"}
            requests.get(f"{endpoint}/admin/reset-limits", headers=headers)

        # Make multiple requests to trigger rate limiting
        rate_limit_hit = False
        # Use per_ip_limit + 2 to ensure we exceed the limit
        for i in range(per_ip_limit + 2):
            response = requests.get(f"{endpoint}/api/test?test_type=ip_only")
            if response.status_code == 429:
                rate_limit_hit = True
                click.echo(f"✅ Per-IP rate limit triggered after {i+1} requests")
                break
            time.sleep(0.1)  # Small delay to avoid overwhelming the server

        if rate_limit_hit:
            results.append(["Per-IP Rate Limiting", "✅ PASS", 429])
        else:
            click.echo("⚠️ Per-IP rate limit not triggered (might be higher than expected)")
            results.append(["Per-IP Rate Limiting", "⚠️ WARNING", "Not triggered"])
    except Exception as e:
        click.echo(f"❌ Error testing per-IP rate limiting: {e}")
        results.append(["Per-IP Rate Limiting", "❌ ERROR", str(e)])

    # Reset rate limits again before testing global limit
    if admin_password:
        try:
            headers = {"Authorization": f"Bearer {admin_password}"}
            response = requests.get(f"{endpoint}/admin/reset-limits", headers=headers)
            if response.status_code == 200 and verbose:
                click.echo("✅ Rate limits reset before global limit test")
        except Exception as e:
            if verbose:
                click.echo(f"⚠️ Error resetting rate limits: {e}")

    # Test 6: Global Rate limiting
    click.echo("\n🔍 Testing global rate limiting...")
    try:
        # Make enough requests to hit the global limit
        global_limit_hit = False

        for i in range(global_limit + 2):
            # Use a unique query parameter to avoid caching
            response = requests.get(f"{endpoint}/api/test?test_type=global_only&unique={i}")

            if verbose:
                click.echo(f"   Request {i+1}: Status {response.status_code}")

            if response.status_code == 429:
                global_limit_hit = True
                click.echo(f"✅ Global rate limit triggered after {i+1} requests")
                break

            time.sleep(0.1)  # Small delay to avoid overwhelming the server

        if global_limit_hit:
            results.append(["Global Rate Limiting", "✅ PASS", 429])
        else:
            click.echo("⚠️ Could not trigger global rate limit")
            results.append(["Global Rate Limiting", "⚠️ WARNING", "Not triggered"])
    except Exception as e:
        click.echo(f"❌ Error testing global rate limiting: {e}")
        results.append(["Global Rate Limiting", "❌ ERROR", str(e)])

    # Summary
    click.echo("\n📊 Test Summary:")
    try:
        table = tabulate(results, headers=["Test", "Result", "Status Code"], tablefmt="grid")
        click.echo(table)
    except ImportError:
        # Fallback if tabulate is not installed
        for test, result, status in results:
            click.echo(f"{test}: {result} ({status})")

    # Overall result
    failures = sum(1 for _, result, _ in results if "❌" in result)
    if failures == 0:
        click.echo("\n🎉 All tests passed successfully!")
    else:
        click.echo(f"\n⚠️ {failures} test(s) failed. See details above.")

    # Reset rate limits after testing is complete
    if admin_password:
        click.echo("\n🔄 Cleaning up after tests...")
        if skip_reset_confirm or click.confirm("Reset rate limits to clean up after testing?", default=True):
            try:
                headers = {"Authorization": f"Bearer {admin_password}"}
                response = requests.get(f"{endpoint}/admin/reset-limits", headers=headers)
                if response.status_code == 200:
                    click.echo("✅ Rate limits reset successfully")
                else:
                    click.echo(f"⚠️ Failed to reset rate limits: {response.status_code}")
            except Exception as e:
                click.echo(f"⚠️ Error resetting rate limits: {e}")

@cli.command(name="workflow")
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
    "--endpoint",
    help="Endpoint URL to test (e.g., https://your-project.workers.dev)",
    required=True,
)
@click.option(
    "--params",
    help="JSON string of parameters to pass to the workflow",
    default='{"requestId": "test-request"}',
)
@click.option(
    "--check-status",
    is_flag=True,
    help="Check the status of a workflow instance",
)
@click.option(
    "--instance-id",
    help="Instance ID to check status for (when using --check-status)",
)
@click.option(
    "--verbose",
    is_flag=True,
    help="Show detailed output",
)
def workflow_command(
    config_file: str,
    env_file: str,
    endpoint: str,
    params: str,
    check_status: bool,
    instance_id: Optional[str] = None,
    verbose: bool = False,
):
    """Test a Cloudflare Workflow deployment."""
    import json
    import requests
    from ..config import load_config
    from ..utils.environment import load_env_file

    try:
        # Load configuration
        config = load_config(config_file)
        env_vars = load_env_file(env_file) if os.path.exists(env_file) else {}

        # Prepare admin auth if available
        headers = {
            "Content-Type": "application/json"
        }

        if config.admin_password_env in env_vars:
            headers["Authorization"] = f"Bearer {env_vars[config.admin_password_env]}"
            if verbose:
                click.echo("Using admin authentication")

        if check_status:
            if not instance_id:
                click.echo("Error: --instance-id is required when using --check-status", err=True)
                return

            # Check workflow status
            status_url = f"{endpoint}?instanceId={instance_id}"
            if verbose:
                click.echo(f"Checking status at: {status_url}")

            response = requests.get(status_url, headers=headers)
            click.echo(f"Status response ({response.status_code}):")
            click.echo(json.dumps(response.json(), indent=2))

        else:
            # Parse parameters
            try:
                workflow_params = json.loads(params)
            except json.JSONDecodeError:
                click.echo(f"Error: Invalid JSON in params: {params}", err=True)
                return

            if verbose:
                click.echo(f"Triggering workflow at: {endpoint}")
                click.echo(f"Parameters: {json.dumps(workflow_params, indent=2)}")

            # Trigger workflow
            response = requests.post(endpoint, json=workflow_params, headers=headers)
            result = response.json()

            click.echo(f"Workflow triggered ({response.status_code}):")
            click.echo(json.dumps(result, indent=2))

            if response.status_code == 200 and "instanceId" in result:
                click.echo("\nTo check status later, run:")
                click.echo(f"gimme workflow --endpoint {endpoint} --check-status --instance-id {result['instanceId']}")

    except Exception as e:
        click.echo(f"Error: {str(e)}", err=True)
        if verbose:
            import traceback
            click.echo(traceback.format_exc())

# Register the deploy command
cli.add_command(deploy_command)

# Register other commands
cli.add_command(init_command)
cli.add_command(validate_command)
cli.add_command(test_command)
cli.add_command(workflow_command)
