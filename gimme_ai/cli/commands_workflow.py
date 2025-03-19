"""Workflow commands for the gimme_ai CLI."""

import os
import json
import sys
import click
import requests
from typing import Optional

from ..config import load_config
from ..utils.environment import load_env_file

# Helper functions (copied from commands_test to avoid circular imports)
def normalize_url(url: str) -> str:
    """Normalize the endpoint URL by removing trailing slashes."""
    return url.rstrip('/')

def get_endpoint_url(url: Optional[str], config_file: str) -> str:
    """Get the endpoint URL from the provided argument, config, or user prompt."""
    if url:
        # Use the provided URL
        return normalize_url(url)

    # Try to get the URL from the project name in config
    try:
        if os.path.exists(config_file):
            with open(config_file, "r") as f:
                config_data = json.load(f)

            project_name = config_data.get("project_name")
            if project_name:
                # Format URL based on Cloudflare Workers naming convention
                possible_url = f"https://{project_name}.workers.dev"
                click.echo(f"Using URL derived from project name: {possible_url}")
                return possible_url
    except Exception as e:
        click.echo(f"Warning: Could not extract URL from config: {e}", err=True)

    # Prompt the user for a URL
    return click.prompt("Please enter your API gateway URL (e.g., https://your-project.workers.dev)")

def get_admin_password(admin_password: Optional[str], env_file: str) -> Optional[str]:
    """Get the admin password from the provided argument or env file."""
    if admin_password:
        return admin_password

    if os.path.exists(env_file):
        try:
            env_vars = load_env_file(env_file)
            admin_pw = env_vars.get("GIMME_ADMIN_PASSWORD")
            if admin_pw:
                click.echo(f"Using admin password from {env_file}")
                return admin_pw
        except Exception as e:
            click.echo(f"Warning: Could not load admin password from env file: {e}", err=True)

    click.echo("No admin password provided or found in env file.")
    return None

@click.command(name="workflow")
@click.argument("url", required=False)
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
    url: Optional[str],
    config_file: str,
    env_file: str,
    params: str,
    check_status: bool,
    instance_id: Optional[str] = None,
    verbose: bool = False,
):
    """Test or interact with a Cloudflare Workflow deployment.

    URL is the endpoint to test (e.g., https://your-project.workers.dev).
    If not provided, it will be automatically detected from config or prompted.
    """
    try:
        # Get endpoint URL
        endpoint = get_endpoint_url(url, config_file)

        # Load configuration
        config = load_config(config_file)
        env_vars = load_env_file(env_file) if os.path.exists(env_file) else {}

        # Get admin password
        admin_password = get_admin_password(None, env_file)

        # Prepare admin auth if available
        headers = {
            "Content-Type": "application/json"
        }

        if admin_password:
            headers["Authorization"] = f"Bearer {admin_password}"
            if verbose:
                click.echo("Using admin authentication")

        # Normalize workflow endpoint
        workflow_endpoint = f"{endpoint}/workflow"

        if check_status:
            if not instance_id:
                click.echo("Error: --instance-id is required when using --check-status", err=True)
                return

            # Check workflow status
            status_url = f"{workflow_endpoint}?instanceId={instance_id}"
            if verbose:
                click.echo(f"Checking status at: {status_url}")

            response = requests.get(status_url, headers=headers)

            if response.status_code == 200:
                click.echo(f"Status response ({response.status_code}):")
                click.echo(json.dumps(response.json(), indent=2))
            else:
                click.echo(f"Error getting status: {response.status_code}")
                click.echo(response.text)

        else:
            # Parse parameters
            try:
                workflow_params = json.loads(params)
            except json.JSONDecodeError:
                click.echo(f"Error: Invalid JSON in params: {params}", err=True)
                return

            if verbose:
                click.echo(f"Triggering workflow at: {workflow_endpoint}")
                click.echo(f"Parameters: {json.dumps(workflow_params, indent=2)}")

            # Trigger workflow
            response = requests.post(workflow_endpoint, json=workflow_params, headers=headers)

            if response.status_code == 200:
                result = response.json()
                click.echo(f"Workflow triggered ({response.status_code}):")
                click.echo(json.dumps(result, indent=2))

                if "instanceId" in result:
                    click.echo("\nTo check status later, run:")
                    click.echo(f"gimme-ai workflow {endpoint} --check-status --instance-id {result['instanceId']}")
            else:
                click.echo(f"Error triggering workflow: {response.status_code}")
                click.echo(response.text)

    except Exception as e:
        click.echo(f"Error: {str(e)}", err=True)
        if verbose:
            import traceback
            click.echo(traceback.format_exc())
