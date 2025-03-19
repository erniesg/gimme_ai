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
    generate_wrangler_toml,
    render_template,
    load_template,
    save_template,
    copy_project_files,
    generate_workflow_script,
    generate_workflow_utils_script
)

class DeploymentResult(NamedTuple):
    """Result of generating deployment files."""
    worker_script: Path
    durable_objects_script: Path
    wrangler_config: Path
    workflow_script: Path = None
    workflow_utils_script: Path = None

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
        result = subprocess.run(['wrangler', '--version'], capture_output=True, text=True)
        if result.returncode == 0:
            return True
        else:
            return False
    except FileNotFoundError:
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

    # Check for project-specific files
    has_project_files = copy_project_files(config, output_dir)
    if has_project_files:
        print(f"Project-specific files for {config.project_name} were included in the deployment")

    # Generate Durable Objects script
    do_path = generate_durable_objects_script(config, output_dir)

    # If workflow is enabled, generate workflow-related files
    workflow_utils_path = None
    workflow_path = None

    workflow_config = getattr(config, 'workflow', None)
    if workflow_config and getattr(workflow_config, 'enabled', True):
        # Generate workflow utils script first so it can be imported by workflow.js
        workflow_utils_path = generate_workflow_utils_script(config, output_dir)
        print(f"Workflow utils script saved to: {workflow_utils_path}")

        # Verify the file was created
        if workflow_utils_path and workflow_utils_path.exists():
            print(f"Workflow utils file exists at: {workflow_utils_path}")
            # Print file size for debugging
            print(f"Workflow utils file size: {workflow_utils_path.stat().st_size} bytes")
        else:
            print("WARNING: workflow_utils.js was not created or does not exist")

        # Generate workflow script after utils so it can import it
        workflow_path = generate_workflow_script(config, output_dir)
        print(f"Workflow script saved to: {workflow_path}")

    # Generate worker script
    worker_path = generate_worker_script(config, output_dir, has_project_files)

    # Generate wrangler.toml
    wrangler_path = generate_wrangler_toml(config, output_dir, has_workflow=bool(workflow_path))

    # List all files in the output directory to verify
    print(f"Files in output directory: {[f.name for f in output_dir.iterdir()]}")

    return DeploymentResult(
        worker_script=worker_path,
        durable_objects_script=do_path,
        wrangler_config=wrangler_path,
        workflow_script=workflow_path,
        workflow_utils_script=workflow_utils_path
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
    import logging
    logger = logging.getLogger(__name__)

    # Check dependencies
    if not check_cloudflare_deps():
        return DeploymentStatus(
            success=False,
            message="Cloudflare dependencies not found. Please install wrangler: npm install -g wrangler"
        )

    # Determine output directory
    output_dir = None
    if hasattr(config, 'output_dir') and config.output_dir:
        output_dir = Path(config.output_dir)
    else:
        # Default to a directory based on project name
        output_dir = Path(f"output/{config.project_name}")

    # Ensure output directory exists
    os.makedirs(output_dir, exist_ok=True)
    logger.info(f"Using output directory: {output_dir}")

    # Generate deployment files if not provided
    if deployment_files is None:
        deployment_files = generate_deployment_files(config, output_dir)

    # Verify that required files exist - check for all necessary files
    required_files = [deployment_files.worker_script, deployment_files.durable_objects_script]

    for file_path in required_files:
        if not file_path or not file_path.exists():
            logger.error(f"Required file missing: {file_path}")
            return DeploymentStatus(
                success=False,
                message=f"Required file missing: {file_path}"
            )
        else:
            logger.info(f"Found required file: {file_path}")

    # Check if workflow files exist, and ensure both are generated if workflow is enabled
    workflow_config = getattr(config, 'workflow', None)
    if workflow_config and getattr(workflow_config, 'enabled', False):
        # Ensure both workflow.js and workflow_utils.js exist
        workflow_path = deployment_files.workflow_script
        workflow_utils_path = deployment_files.workflow_utils_script

        # Generate workflow.js if missing
        if not workflow_path or not workflow_path.exists():
            logger.info("Workflow is enabled but workflow.js is missing, generating it...")
            workflow_path = generate_workflow_script(config, output_dir)
            if not workflow_path or not workflow_path.exists():
                logger.warning("Failed to generate workflow.js, workflow may not function correctly")
        else:
            logger.info(f"Found workflow file: {workflow_path}")

        # Generate workflow_utils.js if missing
        if not workflow_utils_path or not workflow_utils_path.exists():
            logger.info("Workflow is enabled but workflow_utils.js is missing, generating it...")
            workflow_utils_path = generate_workflow_utils_script(config, output_dir)
            if not workflow_utils_path or not workflow_utils_path.exists():
                logger.warning("Failed to generate workflow_utils.js, workflow may not function correctly")
        else:
            logger.info(f"Found workflow utils file: {workflow_utils_path}")

        # Update deployment_files with the new paths
        if workflow_path and workflow_utils_path:
            deployment_files = DeploymentResult(
                worker_script=deployment_files.worker_script,
                durable_objects_script=deployment_files.durable_objects_script,
                wrangler_config=deployment_files.wrangler_config,
                workflow_script=workflow_path,
                workflow_utils_script=workflow_utils_path
            )

    # Change to the directory with the deployment files
    original_dir = os.getcwd()
    os.chdir(deployment_files.worker_script.parent)

    # List all files in the directory to verify
    logger.info(f"Files in deployment directory: {os.listdir('.')}")

    try:
        # Prepare environment variables for wrangler
        env_vars = os.environ.copy()

        # Load environment variables from .env file
        loaded_vars = {}
        try:
            from ..utils.environment import load_env_file
            env_file = os.path.join(original_dir, ".env")
            if os.path.exists(env_file):
                logger.info(f"Loading environment variables from {env_file}")
                loaded_vars = load_env_file(env_file)
                # Add loaded vars to environment
                for key, value in loaded_vars.items():
                    env_vars[key] = value
            else:
                logger.warning(f"Environment file {env_file} not found")
        except Exception as e:
            logger.warning(f"Error loading environment file: {e}")

        # Ensure admin password is available
        admin_password_env = config.admin_password_env
        if admin_password_env not in env_vars:
            logger.warning(f"Admin password environment variable {admin_password_env} not found")
        else:
            logger.info(f"Using admin password from environment: {admin_password_env}")

        # Check required keys
        missing_keys = []
        for key in config.required_keys:
            if key not in env_vars:
                missing_keys.append(key)

        if missing_keys:
            logger.warning(f"Missing required environment variables: {', '.join(missing_keys)}")

        # First, try to build the worker to check for errors
        build_cmd = ["npx", "wrangler", "build"]
        logger.info(f"Running build command: {' '.join(build_cmd)}")

        build_result = subprocess.run(
            build_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
            env=env_vars
        )

        # Save build output for inspection
        build_output_file = os.path.join(os.getcwd(), "build_output.txt")
        with open(build_output_file, "w") as f:
            f.write("STDOUT:\n")
            f.write(build_result.stdout)
            f.write("\n\nSTDERR:\n")
            f.write(build_result.stderr)

        logger.info(f"Build output saved to {build_output_file}")

        if build_result.returncode != 0:
            return DeploymentStatus(
                success=False,
                message=f"Error building worker: {build_result.stderr}"
            )

        # If build succeeds, proceed with deployment
        # Run wrangler deploy
        deploy_cmd = ["npx", "wrangler", "deploy"]
        logger.info(f"Running command: {' '.join(deploy_cmd)}")

        # First, deploy the worker
        result = subprocess.run(
            deploy_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
            env=env_vars
        )

        # Save deployment output for inspection
        output_file = os.path.join(os.getcwd(), "deployment_output.txt")
        with open(output_file, "w") as f:
            f.write("STDOUT:\n")
            f.write(result.stdout)
            f.write("\n\nSTDERR:\n")
            f.write(result.stderr)

        logger.info(f"Deployment output saved to {output_file}")

        if result.returncode != 0:
            return DeploymentStatus(
                success=False,
                message=f"Error deploying to Cloudflare: {result.stderr}"
            )

        # Extract worker URL from output
        worker_url = None
        for line in result.stdout.split('\n'):
            if "https://" in line and ".workers.dev" in line:
                worker_url = line.strip()
                break

        # Now set the secrets
        logger.info("Setting up secrets...")

        # Set admin password secret
        if admin_password_env in env_vars:
            secret_cmd = ["npx", "wrangler", "secret", "put", admin_password_env]
            logger.info(f"Setting secret: {admin_password_env}")
            secret_proc = subprocess.Popen(
                secret_cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            stdout, stderr = secret_proc.communicate(input=env_vars[admin_password_env])

            if secret_proc.returncode != 0:
                logger.warning(f"Failed to set {admin_password_env} secret: {stderr}")
            else:
                logger.info(f"Successfully set {admin_password_env} secret")

        # Set required keys as secrets
        for key in config.required_keys:
            if key in env_vars:
                secret_cmd = ["npx", "wrangler", "secret", "put", key]
                logger.info(f"Setting secret: {key}")
                secret_proc = subprocess.Popen(
                    secret_cmd,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )
                stdout, stderr = secret_proc.communicate(input=env_vars[key])

                if secret_proc.returncode != 0:
                    logger.warning(f"Failed to set {key} secret: {stderr}")
                else:
                    logger.info(f"Successfully set {key} secret")

        return DeploymentStatus(
            success=True,
            message=f"Deployment successful: {worker_url}",
            url=worker_url
        )
    except Exception as e:
        logger.error(f"Error during deployment: {e}")
        return DeploymentStatus(
            success=False,
            message=f"Error during deployment: {e}"
        )
    finally:
        # Change back to original directory
        os.chdir(original_dir)
