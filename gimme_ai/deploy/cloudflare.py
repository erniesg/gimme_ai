# gimme_ai/deploy/cloudflare.py
import os
import subprocess
import tempfile
import json
from pathlib import Path
from typing import Dict, Any, NamedTuple, Optional
from ..config import GimmeConfig
from .templates import (
    generate_worker_script,
    generate_durable_objects_script,
    generate_wrangler_config,
    render_template,
    load_template,
    save_template
)

class DeploymentResult(NamedTuple):
    """Result of generating deployment files."""
    worker_script: Path
    durable_objects_script: Path
    wrangler_config: Path

class DeploymentStatus(NamedTuple):
    """Result of a deployment operation."""
    success: bool
    message: str
    url: Optional[str] = None

def check_cloudflare_deps() -> bool:
    """
    Check if required Cloudflare dependencies are installed.

    Returns:
        True if dependencies are available, False otherwise
    """
    try:
        # Check if wrangler is installed
        result = subprocess.run(
            ["npx", "wrangler", "--version"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False
        )
        return result.returncode == 0
    except Exception:
        return False

def generate_deployment_files(config: GimmeConfig, output_dir: Optional[Path] = None) -> DeploymentResult:
    """
    Generate all files needed for deployment.

    Args:
        config: Application configuration
        output_dir: Directory where to save files (default: temporary directory)

    Returns:
        DeploymentResult with paths to generated files
    """
    # Create a temporary directory if no output directory provided
    if output_dir is None:
        output_dir = Path(tempfile.mkdtemp())

    # Ensure directory exists
    os.makedirs(output_dir, exist_ok=True)

    # Generate worker script
    worker_script = generate_worker_script(config)
    worker_path = output_dir / "worker.js"
    with open(worker_path, "w") as f:
        f.write(worker_script)

    # Generate Durable Objects script
    do_script = generate_durable_objects_script(config)
    do_path = output_dir / "durable_objects.js"
    with open(do_path, "w") as f:
        f.write(do_script)

    # Generate wrangler.toml
    wrangler_config = generate_wrangler_config(config)

    # Load wrangler template
    template_path = Path(__file__).parent.parent / "templates" / "wrangler.toml"
    wrangler_template = load_template(template_path)

    # Convert dict to TOML format
    wrangler_path = output_dir / "wrangler.toml"

    # We'll use a simple approach since the template is already in TOML format
    wrangler_content = render_template(wrangler_template, {
        "project_name": config.project_name
    })

    with open(wrangler_path, "w") as f:
        f.write(wrangler_content)

    return DeploymentResult(
        worker_script=worker_path,
        durable_objects_script=do_path,
        wrangler_config=wrangler_path
    )

def deploy_to_cloudflare(config: GimmeConfig, deployment_files: Optional[DeploymentResult] = None) -> DeploymentStatus:
    """
    Deploy the Cloudflare worker and Durable Objects.

    Args:
        config: Application configuration
        deployment_files: Result from generate_deployment_files (optional)

    Returns:
        Deployment status
    """
    # Check dependencies
    if not check_cloudflare_deps():
        return DeploymentStatus(
            success=False,
            message="Cloudflare dependencies not found. Please install wrangler: npm install -g wrangler"
        )

    # Generate deployment files if not provided
    if deployment_files is None:
        deployment_files = generate_deployment_files(config)

    # Change to the directory with the deployment files
    original_dir = os.getcwd()
    os.chdir(deployment_files.worker_script.parent)

    try:
        # Run wrangler deploy
        result = subprocess.run(
            ["npx", "wrangler", "deploy"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False
        )

        if result.returncode == 0:
            # Extract worker URL from output
            worker_url = None
            for line in result.stdout.split('\n'):
                if "https://" in line and ".workers.dev" in line:
                    worker_url = line.strip()
                    break

            return DeploymentStatus(
                success=True,
                message=f"Deployment successful: {worker_url}",
                url=worker_url
            )
        else:
            return DeploymentStatus(
                success=False,
                message=f"Error deploying to Cloudflare: {result.stderr}"
            )

    finally:
        # Change back to original directory
        os.chdir(original_dir)
