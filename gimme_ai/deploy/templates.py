# gimme_ai/deploy/templates.py
import os
from pathlib import Path
from typing import Dict, Any, Union, Optional
from jinja2 import Template, Environment, FileSystemLoader
from ..config import GimmeConfig

def render_template(template_string: str, context: Dict[str, Any]) -> str:
    """
    Render a template string with the provided context using Jinja2.

    Args:
        template_string: The template string with placeholders
        context: Dictionary of values to substitute into the template

    Returns:
        The rendered template
    """
    # Create a Jinja2 Template object from the template string
    template = Template(template_string)

    # Render the template with the given context
    try:
        return template.render(**context)
    except Exception as e:
        print(f"Error rendering template: {e}")
        print(f"Template: {template_string[:100]}...")
        print(f"Context: {context}")
        raise

def load_template(template_path: Union[str, Path]) -> str:
    """
    Load a template from a file.

    Args:
        template_path: Path to the template file

    Returns:
        The template content as a string
    """
    with open(template_path, "r") as f:
        return f.read()

def save_template(template_string: str, context: Dict[str, Any], output_path: Union[str, Path]) -> Path:
    """
    Render a template and save it to a file.

    Args:
        template_string: The template string with placeholders
        context: Dictionary of values to substitute into the template
        output_path: Path where to save the rendered template

    Returns:
        Path to the saved file
    """
    rendered = render_template(template_string, context)

    # Ensure the directory exists
    os.makedirs(os.path.dirname(str(output_path)), exist_ok=True)

    with open(output_path, "w") as f:
        f.write(rendered)

    return Path(output_path)

def generate_worker_script(config: GimmeConfig, output_dir: Path) -> Path:
    """
    Generate the Cloudflare worker script from configuration.

    Args:
        config: The application configuration
        output_dir: Path to the output directory

    Returns:
        Path to the saved worker script
    """
    # Load the worker template from the package
    template_path = Path(__file__).parent.parent / "templates" / "worker.js"
    template = load_template(template_path)

    # Create the context for rendering
    context = {
        "project_name": config.project_name,
        "dev_endpoint": config.endpoints.dev,
        "prod_endpoint": config.endpoints.prod,
        "admin_password_env": config.admin_password_env,
        "required_keys": config.required_keys,
        "limits": config.limits
    }

    # Print debug info
    print(f"Worker template path: {template_path}")
    print(f"Worker template exists: {template_path.exists()}")

    # Render the template
    output_path = output_dir / "worker.js"
    save_template(template, context, output_path)
    print(f"Worker script saved to: {output_path}")
    return output_path

def generate_durable_objects_script(config: GimmeConfig, output_dir: Optional[Path] = None) -> Path:
    """Generate the Durable Objects script."""
    # Load template
    template_path = Path(__file__).parent.parent / "templates" / "durable_objects.js"
    template = load_template(template_path)

    # Extract limits from config
    limits = {}
    if hasattr(config, 'limits') and config.limits:
        limits = config.limits

        # Debug the actual values to ensure they're correct
        if 'free_tier' in limits:
            free_tier = limits['free_tier']
            if hasattr(free_tier, 'global_limit'):
                print(f"Global limit value: {free_tier.global_limit}")

    # Ensure we have the complete limits structure
    context = {
        "project_name": config.project_name,
        "limits": limits
    }

    # Debug output to verify the context
    print(f"Durable Objects template context: {context}")

    # Render template
    script = render_template(template, context)

    # Save to file if output_dir provided
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        script_path = output_dir / "durable_objects.js"
        with open(script_path, "w") as f:
            f.write(script)
        return script_path

    return script

def generate_wrangler_config(config: GimmeConfig) -> Dict[str, Any]:
    """
    Generate the wrangler.toml configuration.

    Args:
        config: The application configuration

    Returns:
        Dictionary representing the wrangler config
    """
    wrangler_config = {
        "name": config.project_name,
        "main": "worker.js",
        "compatibility_date": "2023-05-15",
        "durable_objects": {
            "bindings": [
                {
                    "name": "IP_LIMITER",
                    "class_name": "IPRateLimiter"
                },
                {
                    "name": "GLOBAL_LIMITER",
                    "class_name": "GlobalRateLimiter"
                }
            ]
        },
        "migrations": [
            {
                "tag": "v1",
                "new_classes": ["IPRateLimiter", "GlobalRateLimiter"]
            }
        ],
        "vars": {}
    }

    # Add environment variables for API keys
    for key in config.required_keys:
        wrangler_config["vars"][key] = f"${{{key}}}"

    # Add admin password variable
    wrangler_config["vars"][config.admin_password_env] = f"${{{config.admin_password_env}}}"

    return wrangler_config

def generate_wrangler_toml(config: GimmeConfig, output_dir: Path) -> Path:
    """
    Generate the wrangler.toml file content from configuration.

    Args:
        config: The application configuration
        output_dir: Path to the output directory

    Returns:
        Path to the saved wrangler.toml file
    """
    template_path = Path(__file__).parent.parent / "templates" / "wrangler.toml"
    output_file = output_dir / "wrangler.toml"

    # Create context for template rendering
    context = {
        "project_name": config.project_name,
        "required_keys": config.required_keys,
        "admin_password_env": config.admin_password_env,
    }

    # Add observability settings if they exist in the config
    if hasattr(config, 'observability'):
        # Convert Python booleans to lowercase strings for TOML compatibility
        obs = config.observability.copy() if isinstance(config.observability, dict) else {}
        if 'enabled' in obs:
            obs['enabled'] = 'true' if obs['enabled'] else 'false'
        if 'logs' in obs and 'invocation_logs' in obs['logs']:
            obs['logs']['invocation_logs'] = 'true' if obs['logs']['invocation_logs'] else 'false'
        context["observability"] = obs
    else:
        # Add default observability settings with proper TOML syntax
        context["observability"] = {
            "enabled": 'true',
            "head_sampling_rate": 1.0,
            "logs": {
                "invocation_logs": 'true'
            }
        }

    try:
        with open(template_path, "r") as f:
            template_content = f.read()

        # Render template
        template = Template(template_content)
        rendered = template.render(**context)

        # Write to output file
        with open(output_file, "w") as f:
            f.write(rendered)

        return output_file
    except Exception as e:
        print(f"Error rendering template: {e}")
        print(f"Template: {template_content[:100]}...")
        print(f"Context: {context}")
        raise
