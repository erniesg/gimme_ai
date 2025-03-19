# gimme_ai/deploy/templates.py
import os
import shutil
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

def copy_project_files(config: GimmeConfig, output_dir: Path) -> bool:
    """
    Copy project-specific files if they exist.

    Args:
        config: The application configuration
        output_dir: Path to the output directory

    Returns:
        True if project files were found and copied, False otherwise
    """
    project_name = config.project_name
    project_dir = Path(__file__).parent.parent / "projects" / project_name

    if not project_dir.exists() or not project_dir.is_dir():
        print(f"No project directory found for {project_name}")
        return False

    # Create projects directory in output
    projects_output_dir = output_dir / "projects" / project_name
    os.makedirs(projects_output_dir, exist_ok=True)

    # Copy all files from the project directory
    for file_path in project_dir.glob('**/*'):
        if file_path.is_file():
            # Get relative path from project directory
            rel_path = file_path.relative_to(project_dir)
            # Create destination path
            dest_path = projects_output_dir / rel_path
            # Ensure parent directory exists
            os.makedirs(dest_path.parent, exist_ok=True)
            # Copy the file
            shutil.copy2(file_path, dest_path)
            print(f"Copied {file_path} to {dest_path}")

    return True

def generate_worker_script(config: GimmeConfig, output_dir: Path, has_project_files: bool = False) -> Path:
    """
    Generate the Cloudflare worker script from configuration.

    Args:
        config: The application configuration
        output_dir: Path to the output directory
        has_project_files: Whether project-specific files were found

    Returns:
        Path to the saved worker script
    """
    # Load the worker template from the package
    template_path = Path(__file__).parent.parent / "templates" / "worker.js"
    template = load_template(template_path)

    # Derive workflow class name consistently
    workflow_config = getattr(config, 'workflow', None)
    workflow_class_name = getattr(workflow_config, 'class_name', None)
    if not workflow_class_name and workflow_config and getattr(workflow_config, 'enabled', False):
        # Convert project name to PascalCase for class name
        project_parts = config.project_name.split('-')
        workflow_class_name = ''.join(part.title() for part in project_parts) + 'Workflow'
    elif not workflow_class_name:
        # Default to VideoGenerationWorkflow if workflow is not enabled
        workflow_class_name = "VideoGenerationWorkflow"

    # Print debug output
    print(f"Config workflow class name: {getattr(workflow_config, 'class_name', 'None')}")
    print(f"Using workflow class name: {workflow_class_name}")

    workflow_binding = config.project_name.upper().replace('-', '_') + '_WORKFLOW'

    context = {
        "project_name": config.project_name,
        "dev_endpoint": config.endpoints.dev,
        "prod_endpoint": config.endpoints.prod,
        "admin_password_env": config.admin_password_env,
        "required_keys": config.required_keys,
        "limits": config.limits,
        "has_project_files": has_project_files,
        "workflow_class_name": workflow_class_name,
        "workflow_binding": workflow_binding,
        "workflow": workflow_config
    }

    # Render the template
    output_path = output_dir / "worker.js"
    save_template(template, context, output_path)
    print(f"Worker script saved to: {output_path}")

    # Verify the worker script content
    with open(output_path, 'r') as f:
        worker_content = f.read()
        import_line = f"import {{ {workflow_class_name}, workflowHandler }} from './workflow.js';"
        if import_line in worker_content:
            print(f"✅ Worker correctly imports {workflow_class_name}")
        else:
            print(f"❌ Worker does not correctly import {workflow_class_name}")
            print(f"First 200 chars of worker.js: {worker_content[:200]}")

    return output_path

def generate_durable_objects_script(config: GimmeConfig, output_dir: Optional[Path] = None) -> Path:
    """
    Generate the Durable Objects script and save it to disk.

    Args:
        config: The application configuration
        output_dir: Path to the output directory

    Returns:
        Path to the saved durable objects script
    """
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

    # Save the rendered template to a file
    if output_dir:
        output_path = output_dir / "durable_objects.js"
        save_template(template, context, output_path)
        print(f"Durable Objects script saved to: {output_path}")
        return output_path

    # If no output_dir is provided, raise an error
    raise ValueError("output_dir must be provided to save the durable objects script")

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
        "vars": {
            "MODAL_ENDPOINT": config.endpoints.prod  # Add Modal endpoint as a variable
        }
    }

    # Add environment variables for API keys
    for key in config.required_keys:
        wrangler_config["vars"][key] = f"${{{key}}}"

    # Add admin password variable
    wrangler_config["vars"][config.admin_password_env] = f"${{{config.admin_password_env}}}"

    return wrangler_config

def generate_wrangler_toml(config: GimmeConfig, output_dir: Path, has_project_files: bool = False, has_workflow: bool = False) -> Path:
    """
    Generate the wrangler.toml file content from configuration.

    Args:
        config: The application configuration
        output_dir: Path to the output directory
        has_project_files: Whether project-specific files were found
        has_workflow: Whether to include workflow configuration

    Returns:
        Path to the saved wrangler.toml file
    """
    template_path = Path(__file__).parent.parent / "templates" / "wrangler.toml"
    output_file = output_dir / "wrangler.toml"

    # Check if workflow is enabled in the config
    workflow_config = getattr(config, 'workflow', None)
    has_workflow = has_workflow or (workflow_config and getattr(workflow_config, 'enabled', False))

    # Create context for template rendering
    # Derive workflow class name from project name consistently
    workflow_class_name = getattr(workflow_config, 'class_name', None)
    if not workflow_class_name:
        # Convert project name to PascalCase for class name
        project_parts = config.project_name.split('-')
        workflow_class_name = ''.join(part.title() for part in project_parts) + 'Workflow'

    context = {
        "project_name": config.project_name,
        "required_keys": config.required_keys,
        "admin_password_env": config.admin_password_env,
        "has_project_files": has_project_files,
        "prod_endpoint": config.endpoints.prod,
        "has_workflow": has_workflow,
        "workflow_class_name": workflow_class_name
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

def generate_workflow_utils_script(config: GimmeConfig, output_dir: Path) -> Optional[Path]:
    """
    Generate the Cloudflare workflow utilities script.

    Args:
        config: The application configuration
        output_dir: Path to the output directory

    Returns:
        Path to the saved workflow utils script or None if workflow is not enabled
    """
    # Check if workflow is enabled
    workflow_config = getattr(config, 'workflow', None)
    if not workflow_config or not getattr(workflow_config, 'enabled', False):
        print("Workflow is not enabled in configuration, skipping workflow utils script generation")
        return None

    # Load the workflow utils template from the package
    template_path = Path(__file__).parent.parent / "templates" / "workflow_utils.js"

    # Check if template exists
    if not template_path.exists():
        print(f"Workflow utils template not found at {template_path}")
        return None

    template = load_template(template_path)

    # Create context with project name to ensure it's properly templated
    context = {
        "project_name": config.project_name
    }

    # Render the template
    output_path = output_dir / "workflow_utils.js"
    save_template(template, context, output_path)
    print(f"Workflow utils script saved to: {output_path}")

    # Verify the file was created successfully
    if not output_path.exists():
        print(f"ERROR: Failed to create workflow_utils.js at {output_path}")
    else:
        print(f"Successfully created workflow_utils.js at {output_path}")
        # Print file size and first few lines for debugging
        print(f"File size: {output_path.stat().st_size} bytes")
        with open(output_path, 'r') as f:
            print(f"File content preview: {f.read(100)}...")

    return output_path

def generate_workflow_script(config: GimmeConfig, output_dir: Optional[Path] = None) -> Optional[Path]:
    """
    Generate the workflow.js script based on configuration.

    Args:
        config: The application configuration
        output_dir: Path to the output directory

    Returns:
        Path to the saved workflow script or None if workflow is not enabled
    """
    # Convert output_dir to Path if it's a string
    if isinstance(output_dir, str):
        output_dir = Path(output_dir)

    # Default to 'dist' if not provided
    output_dir = output_dir or Path('dist')

    # Make sure the output directory exists
    os.makedirs(output_dir, exist_ok=True)

    # First, check if workflow support is enabled
    workflow_config = getattr(config, 'workflow', None)
    if not workflow_config or not getattr(workflow_config, 'enabled', False):
        print("Workflow support is disabled, skipping workflow.js generation")
        return None

    # Define TEMPLATES_DIR
    TEMPLATES_DIR = Path(__file__).parent.parent / "templates"

    # Get workflow template path
    workflow_template_path = TEMPLATES_DIR / 'workflow.js'

    if not workflow_template_path.exists():
        print(f"Workflow template not found at {workflow_template_path}")
        return None

    # Get workflow type
    workflow_type = getattr(workflow_config, 'type', 'api')

    # Get workflow steps
    workflow_steps = getattr(workflow_config, 'steps', [])

    # Derive consistent class name from project name (PascalCase + "Workflow")
    project_parts = config.project_name.split('-')
    derived_class_name = ''.join(part.title() for part in project_parts) + 'Workflow'

    # Use the derived class name
    workflow_class_name = derived_class_name

    # Generate consistent workflow binding name (SCREAMING_SNAKE_CASE + "_WORKFLOW")
    workflow_binding = config.project_name.upper().replace('-', '_') + '_WORKFLOW'

    # Get endpoints from config
    dev_endpoint = config.endpoints.dev if hasattr(config, 'endpoints') and hasattr(config.endpoints, 'dev') else 'http://localhost:8000'
    prod_endpoint = config.endpoints.prod if hasattr(config, 'endpoints') and hasattr(config.endpoints, 'prod') else 'https://gimme-ai-test.modal.run'

    # Set up Jinja environment
    env = Environment(loader=FileSystemLoader(TEMPLATES_DIR))

    # Load the template
    try:
        template = env.get_template('workflow.js')
    except Exception as e:
        print(f"Error loading workflow template: {e}")
        template = Template(workflow_template_path.read_text())

    # Render the template
    context = {
        "project_name": config.project_name,
        "workflow": {
            "type": workflow_type,
            "steps": workflow_steps,
            "enabled": True
        },
        "workflow_class_name": workflow_class_name,
        "workflow_binding": workflow_binding,
        "endpoints": {
            "dev": dev_endpoint,
            "prod": prod_endpoint
        }
    }

    try:
        workflow_js = template.render(**context)
    except Exception as e:
        print(f"Error rendering workflow template: {e}")
        print(f"Context: {context}")
        raise

    # Write the rendered template to the output directory
    workflow_js_path = output_dir / 'workflow.js'
    workflow_js_path.write_text(workflow_js)

    # Create handlers directory if it doesn't exist
    handlers_dir = output_dir / 'handlers'
    handlers_dir.mkdir(exist_ok=True)

    # Add these debug statements right at the start
    print(f"DEBUG: Starting workflow script generation")
    print(f"DEBUG: Output directory is {output_dir}")
    print(f"DEBUG: Workflow type is {getattr(workflow_config, 'type', 'api')}")

    # Then, when handling video workflow:
    if workflow_type == 'video' or workflow_type == 'dual':
        video_handler_template_path = TEMPLATES_DIR / 'handlers' / 'video_workflow.js'
        print(f"DEBUG: Looking for video template at: {video_handler_template_path}")
        print(f"DEBUG: Template exists: {video_handler_template_path.exists()}")

        if video_handler_template_path.exists():
            # Check the file is readable and not empty
            try:
                content = video_handler_template_path.read_text()
                print(f"DEBUG: Template file size: {len(content)} bytes")
                print(f"DEBUG: First 100 chars: {content[:100]}")
            except Exception as e:
                print(f"DEBUG: Error reading template: {e}")

    if workflow_type == 'api' or workflow_type == 'dual':
        api_handler_template_path = TEMPLATES_DIR / 'handlers' / 'api_workflow.js'
        if api_handler_template_path.exists():
            api_handler_js = api_handler_template_path.read_text()
            api_handler_js_path = handlers_dir / 'api_workflow.js'
            api_handler_js_path.write_text(api_handler_js)
            print(f"Generated API workflow handler at {api_handler_js_path}")
        else:
            print(f"WARNING: API workflow template not found at {api_handler_template_path}")

    # Also generate the workflow utils
    generate_workflow_utils_script(config, output_dir)

    print(f"Generated workflow.js at {workflow_js_path}")
    return workflow_js_path

def ensure_workflow_files(config, output_dir):
    """
    Ensure all workflow files are properly generated and copied.
    This is a convenience function to call from deployment scripts.
    """
    # Ensure directories exist
    handlers_dir = output_dir / 'handlers'
    handlers_dir.mkdir(exist_ok=True)

    # Get workflow type
    workflow_config = getattr(config, 'workflow', None)
    if not workflow_config or not getattr(workflow_config, 'enabled', False):
        return False

    workflow_type = getattr(workflow_config, 'type', 'api')

    # Generate workflow utils
    workflow_utils_path = generate_workflow_utils_script(config, output_dir)

    # Generate workflow script
    workflow_js_path = generate_workflow_script(config, output_dir)

    # Explicitly handle the video workflow handler for dual or video types
    if workflow_type in ['dual', 'video']:
        # Try multiple potential locations for the template
        template_paths = [
            Path(__file__).parent.parent / "templates" / "handlers" / "video_workflow.js",
            Path("templates/handlers/video_workflow.js"),
            Path(__file__).parent.parent.parent / "templates" / "handlers" / "video_workflow.js"
        ]

        for template_path in template_paths:
            if template_path.exists():
                video_handler_path = handlers_dir / 'video_workflow.js'
                try:
                    shutil.copy(template_path, video_handler_path)
                    print(f"Successfully copied video handler from {template_path}")
                    break
                except Exception as e:
                    print(f"Error copying from {template_path}: {e}")

    return True
