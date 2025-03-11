# tests/unit/deploy/test_cloudflare.py
import os
import tempfile
import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path
from gimme_ai.config import GimmeConfig
from gimme_ai.deploy.cloudflare import (
    check_cloudflare_deps,
    generate_deployment_files,
    deploy_to_cloudflare,
    DeploymentResult
)

@pytest.fixture
def test_config():
    """Create a test configuration."""
    return GimmeConfig(
        project_name="test-project",
        endpoints={"dev": "http://localhost:8000", "prod": "https://example.com"},
        limits={"free_tier": {"per_ip": 5, "global": 100}},
        required_keys=["MODAL_TOKEN_ID", "MODAL_TOKEN_SECRET"]
    )

@pytest.fixture
def temp_dir():
    """Create a temporary directory."""
    with tempfile.TemporaryDirectory() as tmpdirname:
        yield tmpdirname

def test_check_cloudflare_deps_success():
    """Test successful Cloudflare dependency check."""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        result = check_cloudflare_deps()
        assert result is True

def test_check_cloudflare_deps_failure():
    """Test failed Cloudflare dependency check."""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 1
        result = check_cloudflare_deps()
        assert result is False

def test_generate_deployment_files(test_config, temp_dir):
    """Test generating deployment files."""
    output_dir = Path(temp_dir)

    with patch.dict(os.environ, {"MODAL_TOKEN_ID": "test-id", "MODAL_TOKEN_SECRET": "test-secret", "GIMME_ADMIN_PASSWORD": "test-password"}):
        result = generate_deployment_files(test_config, output_dir)

        # Check that files were generated
        assert result.worker_script.exists()
        assert result.durable_objects_script.exists()
        assert result.wrangler_config.exists()

        # Check file contents
        with open(result.worker_script, "r") as f:
            worker_content = f.read()
            assert "test-project" in worker_content
            assert "http://localhost:8000" in worker_content

        with open(result.durable_objects_script, "r") as f:
            do_content = f.read()
            assert "5" in do_content  # per_ip limit

        with open(result.wrangler_config, "r") as f:
            config_content = f.read()
            assert "test-project" in config_content
            assert "IPRateLimiter" in config_content

@patch("subprocess.run")
def test_deploy_to_cloudflare_success(mock_run, test_config, temp_dir):
    """Test successful deployment to Cloudflare."""
    output_dir = Path(temp_dir)

    # Create dummy files
    (output_dir / "worker.js").write_text("// Worker script")
    (output_dir / "durable_objects.js").write_text("// DO script")
    (output_dir / "wrangler.toml").write_text("name = 'test-project'")

    mock_run.return_value.returncode = 0
    mock_run.return_value.stdout = "Published to https://test-project.workers.dev"

    with patch.dict(os.environ, {"MODAL_TOKEN_ID": "test-id", "MODAL_TOKEN_SECRET": "test-secret", "GIMME_ADMIN_PASSWORD": "test-password"}):
        deployment_files = DeploymentResult(
            worker_script=output_dir / "worker.js",
            durable_objects_script=output_dir / "durable_objects.js",
            wrangler_config=output_dir / "wrangler.toml"
        )

        result = deploy_to_cloudflare(test_config, deployment_files)

        assert result.success is True
        assert "https://test-project.workers.dev" in result.message
        assert mock_run.called

@patch("subprocess.run")
def test_deploy_to_cloudflare_failure(mock_run, test_config, temp_dir):
    """Test failed deployment to Cloudflare due to missing dependencies."""
    output_dir = Path(temp_dir)

    # Create dummy files
    (output_dir / "worker.js").write_text("// Worker script")
    (output_dir / "durable_objects.js").write_text("// DO script")
    (output_dir / "wrangler.toml").write_text("name = 'test-project'")

    mock_run.return_value.returncode = 1
    mock_run.return_value.stderr = "Cloudflare dependencies not found. Please install wrangler: npm install -g wrangler"

    with patch.dict(os.environ, {"MODAL_TOKEN_ID": "test-id", "MODAL_TOKEN_SECRET": "test-secret", "GIMME_ADMIN_PASSWORD": "test-password"}):
        deployment_files = DeploymentResult(
            worker_script=output_dir / "worker.js",
            durable_objects_script=output_dir / "durable_objects.js",
            wrangler_config=output_dir / "wrangler.toml"
        )

        result = deploy_to_cloudflare(test_config, deployment_files)

        assert result.success is False
        assert "Cloudflare dependencies not found" in result.message
