# debug_templates.py
import os
import sys
from pathlib import Path
from gimme_ai.config import GimmeConfig
from gimme_ai.deploy.templates import (
    load_template,
    generate_worker_script,
    generate_durable_objects_script,
    generate_workflow_script
)

# Load config
config_path = ".gimme-config.json"
if not os.path.exists(config_path):
    print(f"Config file not found: {config_path}")
    sys.exit(1)

# Create output directory
output_dir = Path("debug_output")
os.makedirs(output_dir, exist_ok=True)
print(f"Saving files to: {output_dir}")

try:
    # Load config
    config = GimmeConfig.from_file(config_path)
    print(f"Loaded config for project: {config.project_name}")

    # Generate worker.js
    worker_path = generate_worker_script(config, output_dir)
    print(f"Generated worker.js: {worker_path}")

    # Generate durable_objects.js
    do_path = generate_durable_objects_script(config, output_dir)
    print(f"Generated durable_objects.js: {do_path}")

    # Generate workflow.js
    workflow_path = generate_workflow_script(config, output_dir)
    print(f"Generated workflow.js: {workflow_path}")

    # Manually generate wrangler.toml
    template_path = Path("gimme_ai/templates/wrangler.toml")
    if not template_path.exists():
        template_path = Path("gimme_ai/gimme_ai/templates/wrangler.toml")

    if not template_path.exists():
        print(f"Template not found: {template_path}")
        sys.exit(1)

    print(f"Using template: {template_path}")

    # Load template content
    with open(template_path, "r") as f:
        template_content = f.read()

    # Save raw template for inspection
    with open(output_dir / "wrangler.toml.template", "w") as f:
        f.write(template_content)
    print(f"Saved raw template to: {output_dir / 'wrangler.toml.template'}")

    # Create context
    workflow_class_name = f"{config.project_name.title().replace('-', '')}Workflow"
    context = {
        "project_name": config.project_name,
        "required_keys": config.required_keys,
        "admin_password_env": config.admin_password_env,
        "has_project_files": False,
        "prod_endpoint": config.endpoints.prod,
        "has_workflow": True,
        "workflow_class_name": workflow_class_name,
    }

    # Add observability with string values
    if hasattr(config, 'observability'):
        obs = {}
        if isinstance(config.observability, dict):
            # Convert all values to strings
            obs["enabled"] = str(config.observability.get("enabled", True)).lower()
            obs["head_sampling_rate"] = str(config.observability.get("head_sampling_rate", 1.0))

            if "logs" in config.observability:
                obs["logs"] = {
                    "invocation_logs": str(config.observability["logs"].get("invocation_logs", True)).lower()
                }
        context["observability"] = obs
    else:
        context["observability"] = {
            "enabled": "true",
            "head_sampling_rate": "1.0",
            "logs": {
                "invocation_logs": "true"
            }
        }

    # Save context for inspection
    import json
    with open(output_dir / "wrangler_context.json", "w") as f:
        json.dump(context, f, indent=2)
    print(f"Saved context to: {output_dir / 'wrangler_context.json'}")

    # Create a minimal wrangler.toml file
    minimal_content = f"""
# Minimal wrangler.toml for {config.project_name}
name = "{config.project_name}"
main = "worker.js"
compatibility_date = "2024-12-27"

# Durable Objects bindings
[[durable_objects.bindings]]
name = "IP_LIMITER"
class_name = "IPRateLimiter"

[[durable_objects.bindings]]
name = "GLOBAL_LIMITER"
class_name = "GlobalRateLimiter"

# Migrations for Durable Objects
[[migrations]]
tag = "v1"
new_classes = ["IPRateLimiter", "GlobalRateLimiter"]

# Workflow binding
[[workflows]]
name = "{config.project_name}"
binding = "{config.project_name.upper()}_WORKFLOW"
class_name = "{workflow_class_name}"

# Add environment variables
[vars]
MODAL_ENDPOINT = "{config.endpoints.prod}"
"""
    # Add required keys
    for key in config.required_keys:
        minimal_content += f'{key} = "${{{{ {key} }}}}"\n'

    # Add admin password
    minimal_content += f'{config.admin_password_env} = "${{{{ {config.admin_password_env} }}}}"\n'

    with open(output_dir / "wrangler.toml", "w") as f:
        f.write(minimal_content)
    print(f"Created minimal wrangler.toml: {output_dir / 'wrangler.toml'}")

    print("\nAll files generated successfully!")

except Exception as e:
    import traceback
    print(f"Error: {e}")
    traceback.print_exc()
    print("\nSaving error details...")

    with open(output_dir / "error.log", "w") as f:
        f.write(f"Error: {e}\n\n")
        f.write(traceback.format_exc())

    print(f"Error details saved to: {output_dir / 'error.log'}")
