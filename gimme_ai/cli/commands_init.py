"""Initialization commands for the gimme_ai CLI."""

import os
import json
import sys
import click
import inquirer
from typing import Optional
from pathlib import Path

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

@click.command(name="init")
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

        # Create default configuration (defaulting to cloudflare for better DX)
        config = create_default_config(project_name, provider="cloudflare")

        # Required API keys for backend
        click.echo("\n📦 Required API keys for your backend:")

        # Get required keys from config
        required_keys = config.get("required_keys", [])

        for key in required_keys:
            if key not in env_vars:
                value = click.prompt(f"{key}")
                env_vars[key] = value

        # Add workflow configuration
        click.echo("\n🔄 Workflow Configuration:")

        try:
            use_workflow = click.confirm("Would you like to use Cloudflare Workers Workflows?", default=True)

            if use_workflow:
                # Ask for workflow template
                try:
                    inquirer = _safe_import_inquirer()
                    template_questions = [
                        inquirer.List(
                            "template",
                            message="Which workflow template would you like to use?",
                            choices=["Video Generation", "Simple API", "Custom"],
                            default="Video Generation"
                        )
                    ]
                    template_answers = inquirer.prompt(template_questions)
                    template_choice = template_answers["template"]
                except ImportError:
                    template_choice = click.prompt(
                        "Which workflow template? [1: Video Generation, 2: Simple API, 3: Custom]",
                        type=click.Choice(["1", "2", "3"]),
                        default="1"
                    )
                    template_map = {"1": "Video Generation", "2": "Simple API", "3": "Custom"}
                    template_choice = template_map[template_choice]

                # Map user-friendly choice to template name
                template_name = {
                    "Video Generation": "video",
                    "Simple API": "api",
                    "Custom": "custom"
                }.get(template_choice, "video")

                # Create workflow config
                workflow_config_file = "workflow-config.json"

                # Create workflow configuration in config
                config["workflow"] = {
                    "enabled": True,
                    "class_name": f"{project_name.replace('-', '_').title()}Workflow",
                    "config_file": workflow_config_file
                }

                # Create workflow defaults
                config["workflow_defaults"] = {
                    "polling_interval": "5s",
                    "timeout": "5m",
                    "retry_limit": 3,
                    "retry_delay": "5s"
                }

                # Generate workflow config file
                generate_workflow_config(workflow_config_file, template_name)

                click.echo(f"✅ Workflow enabled with {template_choice} template")
                click.echo(f"✅ Created {workflow_config_file}")
            else:
                config["workflow"] = {"enabled": False}
                click.echo("✅ Workflow support disabled")
        except Exception as e:
            click.echo(f"Error configuring workflow: {e}", err=True)
            config["workflow"] = {"enabled": False}

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
        if config["workflow"]["enabled"]:
            click.echo(f"   2. Review your workflow configuration in {workflow_config_file}")
            click.echo("   3. Run 'gimme-ai deploy' to deploy your gateway with workflow support")
        else:
            click.echo("   2. Run 'gimme-ai deploy' to deploy your gateway")

    except Exception as e:
        click.echo(f"Error during initialization: {e}", err=True)
        sys.exit(1)

# Add function to generate workflow config file
def generate_workflow_config(output_file: str, template: str):
    """Generate a workflow configuration file based on a template."""
    workflow_config = {
        "steps": [],
        "defaults": {
            "method": "POST",
            "timeout": "5m",
            "polling_interval": "5s",
            "retry_limit": 3,
            "retry_delay": "5s"
        }
    }

    if template == "video":
        # Video generation workflow template
        workflow_config["steps"] = [
            {
                "name": "initialize",
                "endpoint": "/workflow/init",
                "method": "POST"
            },
            {
                "name": "generate_script",
                "endpoint": "/workflow/generate_script/{job_id}",
                "method": "POST",
                "depends_on": ["initialize"],
                "poll": {
                    "endpoint": "/workflow/status/{job_id}?step=script",
                    "interval": "5s",
                    "max_attempts": 60
                }
            },
            {
                "name": "generate_audio",
                "endpoint": "/workflow/generate_audio/{job_id}",
                "method": "POST",
                "depends_on": ["generate_script"],
                "poll": {
                    "endpoint": "/workflow/status/{job_id}?step=audio",
                    "interval": "5s",
                    "max_attempts": 120
                }
            },
            {
                "name": "generate_base_video",
                "endpoint": "/workflow/generate_base_video/{job_id}",
                "method": "POST",
                "depends_on": ["generate_script"],
                "poll": {
                    "endpoint": "/workflow/status/{job_id}?step=base_video",
                    "interval": "10s",
                    "max_attempts": 180
                }
            },
            {
                "name": "generate_captions",
                "endpoint": "/workflow/generate_captions/{job_id}",
                "method": "POST",
                "depends_on": ["generate_audio"],
                "poll": {
                    "endpoint": "/workflow/status/{job_id}?step=captions",
                    "interval": "5s",
                    "max_attempts": 60
                }
            },
            {
                "name": "combine_final_video",
                "endpoint": "/workflow/combine_final_video/{job_id}",
                "method": "POST",
                "depends_on": ["generate_audio", "generate_base_video", "generate_captions"],
                "poll": {
                    "endpoint": "/workflow/status/{job_id}?step=final_video",
                    "interval": "10s",
                    "max_attempts": 120
                }
            }
        ]
    elif template == "api":
        # Simple API workflow template
        workflow_config["steps"] = [
            {
                "name": "initialize",
                "endpoint": "/api/init",
                "method": "POST"
            },
            {
                "name": "process",
                "endpoint": "/api/process/{job_id}",
                "method": "POST",
                "depends_on": ["initialize"],
                "poll": {
                    "endpoint": "/api/status/{job_id}",
                    "interval": "5s",
                    "max_attempts": 60
                }
            },
            {
                "name": "finalize",
                "endpoint": "/api/finalize/{job_id}",
                "method": "POST",
                "depends_on": ["process"]
            }
        ]
    else:
        # Custom template with minimal structure
        workflow_config["steps"] = [
            {
                "name": "step1",
                "endpoint": "/api/step1",
                "method": "POST"
            },
            {
                "name": "step2",
                "endpoint": "/api/step2/{step1_id}",
                "method": "POST",
                "depends_on": ["step1"],
                "poll": {
                    "endpoint": "/api/status/{step1_id}",
                    "interval": "5s",
                    "max_attempts": 60
                }
            }
        ]

    # Save workflow configuration
    with open(output_file, "w") as f:
        json.dump(workflow_config, f, indent=2)
