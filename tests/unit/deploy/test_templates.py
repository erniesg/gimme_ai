# tests/unit/deploy/test_templates.py
import os
import tempfile
from pathlib import Path
import pytest
from unittest.mock import patch, MagicMock
from gimme_ai.deploy.templates import (
    render_template,
    load_template,
    save_template,
    generate_worker_script,
    generate_durable_objects_script,
    generate_wrangler_config
)
from gimme_ai.config import GimmeConfig

@pytest.fixture
def temp_template_dir():
    """Create a temporary directory with test templates."""
    with tempfile.TemporaryDirectory() as tmpdirname:
        # Create a test template file
        test_template = """
        const PROJECT_NAME = "{{ project_name }}";
        const ADMIN_PASSWORD_ENV = "{{ admin_password_env }}";
        const RATE_LIMIT_PER_IP = {{ limits.free_tier.per_ip }};
        """

        # Write the template to the temp directory
        template_path = Path(tmpdirname) / "test_template.js"
        with open(template_path, "w") as f:
            f.write(test_template)

        yield tmpdirname

def test_render_template_basic():
    """Test basic template rendering with placeholders."""
    template = "Hello {{ name }}!"
    context = {"name": "World"}

    result = render_template(template_string=template, context=context)
    assert result == "Hello World!"

def test_render_template_nested_values():
    """Test rendering templates with nested values."""
    template = "Rate limit: {{ limits.free_tier.per_ip }}"
    context = {"limits": {"free_tier": {"per_ip": 5}}}

    result = render_template(template_string=template, context=context)
    assert result == "Rate limit: 5"

def test_load_template(temp_template_dir):
    """Test loading a template from a file."""
    template_path = Path(temp_template_dir) / "test_template.js"

    template = load_template(template_path)
    assert "PROJECT_NAME" in template
    assert "{{ project_name }}" in template

def test_save_template(temp_template_dir):
    """Test saving a rendered template to a file."""
    output_path = Path(temp_template_dir) / "output.js"
    template = "const PROJECT_NAME = '{{ project_name }}'"
    context = {"project_name": "test-project"}

    save_template(template_string=template, context=context, output_path=output_path)

    # Check the saved file
    with open(output_path, "r") as f:
        content = f.read()

    assert "const PROJECT_NAME = 'test-project'" in content

def test_generate_worker_script():
    """Test generating the worker script from config."""
    config = GimmeConfig(
        project_name="test-project",
        endpoints={"dev": "http://localhost:8000", "prod": "https://example.com"},
        limits={"free_tier": {"per_ip": 5, "global": 100}},
        required_keys=["MODAL_TOKEN_ID", "MODAL_TOKEN_SECRET"]
    )

    # Create a temporary directory for output files
    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir)

        # Update the mock template to match the actual context structure
        mock_template = """
        const PROJECT_NAME = "{{ project_name }}";
        const DEV_ENDPOINT = "{{ dev_endpoint }}";
        const PROD_ENDPOINT = "{{ prod_endpoint }}";
        {% for key in required_keys %}
        // {{ key }}
        {% endfor %}
        """

        # Mock the template loading
        with patch("gimme_ai.deploy.templates.load_template", return_value=mock_template):
            script = generate_worker_script(config, output_dir)

            # Check that the script contains important parts
            with open(script, "r") as f:
                content = f.read()
                assert "test-project" in content
                assert "http://localhost:8000" in content
                assert "https://example.com" in content
                assert "// MODAL_TOKEN_ID" in content
                assert "// MODAL_TOKEN_SECRET" in content

def test_generate_durable_objects_script():
    """Test generating the Durable Objects script from config."""
    config = GimmeConfig(
        project_name="test-project",
        endpoints={"dev": "http://localhost:8000", "prod": "https://example.com"},
        limits={"free_tier": {"per_ip": 5, "global": 100}},
        required_keys=["MODAL_TOKEN_ID", "MODAL_TOKEN_SECRET"]
    )

    # Create a temporary directory for output files
    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir)

        # Test direct rendering first to diagnose the issue
        test_template = """
        export class IPRateLimiter {
          constructor(state, env) {
            this.limit = {{ limits.free_tier.per_ip }};
          }
        }

        export class GlobalRateLimiter {
          constructor(state, env) {
            this.limit = {{ limits.free_tier.global_limit }};
          }
        }
        """

        # Direct call to render_template to verify Jinja2 rendering
        context = {
            "project_name": "test-project",
            "limits": {"free_tier": {"per_ip": 5, "global_limit": 100}}
        }
        direct_result = render_template(test_template, context)

        # Check if both values got rendered
        assert "5" in direct_result
        assert "100" in direct_result

        # Now test with mocked load_template
        with patch("gimme_ai.deploy.templates.load_template", return_value=test_template):
            script = generate_durable_objects_script(config, output_dir)

            # Check the contents of the generated file
            with open(script, "r") as f:
                content = f.read()
                assert "IPRateLimiter" in content
                assert "GlobalRateLimiter" in content
                assert "5" in content
                assert "100" in content

def test_generate_wrangler_config():
    """Test generating the wrangler.toml configuration."""
    config = GimmeConfig(
        project_name="test-project",
        endpoints={"dev": "http://localhost:8000", "prod": "https://example.com"},
        limits={"free_tier": {"per_ip": 5, "global": 100}},
        required_keys=["MODAL_TOKEN_ID", "MODAL_TOKEN_SECRET"]
    )

    wrangler_config = generate_wrangler_config(config)

    # Check important parts of wrangler config
    assert wrangler_config["name"] == "test-project"
    assert len(wrangler_config["durable_objects"]["bindings"]) >= 2
    assert "IPRateLimiter" in str(wrangler_config["durable_objects"]["bindings"])
    assert "GlobalRateLimiter" in str(wrangler_config["durable_objects"]["bindings"])
