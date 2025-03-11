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

def generate_worker_script(config: GimmeConfig) -> str:
    """
    Generate the Cloudflare worker script from configuration.

    Args:
        config: The application configuration

    Returns:
        The rendered worker script
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
    return render_template(template_string=template, context=context)

def generate_durable_objects_script(config: GimmeConfig) -> str:
    """
    Generate the Durable Objects script from configuration.

    Args:
        config: The application configuration

    Returns:
        The rendered Durable Objects script
    """
    # Load the Durable Objects template from the package
    template_path = Path(__file__).parent.parent / "templates" / "durable_objects.js"
    template = load_template(template_path)

    # Create the context for rendering
    context = {
        "project_name": config.project_name,
        "limits": {
            "free_tier": {
                "per_ip": config.limits["free_tier"].per_ip,
                "global": config.limits["free_tier"].global_limit
            }
        }
    }

    # Print debug info
    print(f"DO template path: {template_path}")
    print(f"DO template exists: {template_path.exists()}")
    print(f"DO context: {context}")

    # Render the template
    return render_template(template_string=template, context=context)

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

def generate_wrangler_toml(config: GimmeConfig) -> str:
    """
    Generate the wrangler.toml file content from configuration.

    Args:
        config: The application configuration

    Returns:
        The rendered wrangler.toml content
    """
    # Load the wrangler template from the package
    template_path = Path(__file__).parent.parent / "templates" / "wrangler.toml"

    # Check if template exists, if not create a basic one
    if not template_path.exists():
        template = """
name = "{{ project_name }}"
main = "worker.js"
compatibility_date = "2023-05-15"

[[durable_objects.bindings]]
name = "IP_LIMITER"
class_name = "IPRateLimiter"

[[durable_objects.bindings]]
name = "GLOBAL_LIMITER"
class_name = "GlobalRateLimiter"

[[migrations]]
tag = "v1"
new_classes = ["IPRateLimiter", "GlobalRateLimiter"]

{% for key in required_keys %}
# {{ key }}
{% endfor %}
"""
    else:
        template = load_template(template_path)

    # Create the context for rendering
    context = {
        "project_name": config.project_name,
        "required_keys": config.required_keys,
        "admin_password_env": config.admin_password_env
    }

    # Render the template
    return render_template(template_string=template, context=context)
