"""Tests for command-line interface."""

import os
import json
import tempfile
from pathlib import Path
import pytest
from click.testing import CliRunner
from unittest.mock import patch, MagicMock
from gimme_ai.cli.commands import cli, init_command, validate_command


@pytest.fixture
def runner():
    """Create a CLI runner for testing."""
    return CliRunner()


def test_init_command_creates_files(runner):
    """Test that init command creates expected files."""
    with runner.isolated_filesystem():
        # Instead of mocking, directly provide all possible inputs
        result = runner.invoke(
            init_command,
            ["--project-name", "test-project"],
            input="y\ntest-password\ny\ntest-token\ny\n"  # Provide generous input for any prompts
        )

        print(f"Exit code: {result.exit_code}")
        print(f"Output: {result.output}")

        assert result.exit_code == 0

        # Check files were created
        assert os.path.exists(".gimme-config.json")
        assert os.path.exists(".env")
        # Remove the .env.example assertion since it's not created anymore
        # assert os.path.exists(".env.example")

        # Check content of config file
        with open(".gimme-config.json", "r") as f:
            config = json.load(f)
            assert config["project_name"] == "test-project"
            assert "endpoints" in config
            assert "limits" in config
            assert "required_keys" in config

        # Check content of env file
        with open(".env", "r") as f:
            env_content = f.read()
            # Project name is now stored only in config, not in .env
            # Remove this assertion since it's no longer applicable:
            # assert "GIMME_PROJECT_NAME=test-project" in env_content
            # Instead, check for other expected env variables:
            assert "GIMME_ADMIN_PASSWORD" in env_content
            assert "MODAL_TOKEN_SECRET=test-token" in env_content


def test_init_command_with_existing_env(runner):
    """Test init command when .env already exists."""
    with runner.isolated_filesystem():
        # Create existing .env with some values
        with open(".env", "w") as f:
            f.write("EXISTING_KEY=existing_value\n")
            f.write("GIMME_PROJECT_NAME=existing_project\n")

        # Directly provide inputs instead of mocking
        result = runner.invoke(
            init_command,
            input="y\ntest-password\ny\ntest-token\ny\n"  # Provide generous input for any prompts
        )

        print(f"Exit code: {result.exit_code}")
        print(f"Output: {result.output}")

        assert result.exit_code == 0

        # Check that .env was updated but preserved existing values
        with open(".env", "r") as f:
            env_content = f.read()
            assert "EXISTING_KEY=existing_value" in env_content
            assert "GIMME_PROJECT_NAME=existing_project" in env_content


def test_validate_command_valid(runner):
    """Test validate command with valid configuration."""
    with runner.isolated_filesystem():
        # Create valid config
        config = {
            "project_name": "test-project",
            "endpoints": {
                "dev": "http://localhost:8000",
                "prod": "https://test-project.modal.run"
            },
            "limits": {
                "free_tier": {"per_ip": 5, "global": 100}
            },
            "required_keys": ["TEST_KEY"]
        }

        with open(".gimme-config.json", "w") as f:
            json.dump(config, f)

        # Create valid env
        with open(".env", "w") as f:
            f.write("GIMME_PROJECT_NAME=test-project\n")
            f.write("GIMME_ADMIN_PASSWORD=test-password\n")
            f.write("TEST_KEY=test-value\n")

        # Run validation
        with patch.dict(os.environ, {}, clear=True):
            result = runner.invoke(validate_command)
            assert result.exit_code == 0
            assert "Configuration validation passed" in result.output
            assert "Environment validation passed" in result.output


def test_validate_command_invalid_config(runner):
    """Test validate command with invalid configuration."""
    with runner.isolated_filesystem():
        # Create invalid config (missing required fields)
        config = {
            "project_name": "test-project",
            # Missing endpoints
        }

        with open(".gimme-config.json", "w") as f:
            json.dump(config, f)

        # Run validation
        result = runner.invoke(validate_command)
        assert result.exit_code == 1
        assert "Configuration validation failed" in result.output


def test_validate_command_missing_env(runner):
    """Test validate command with missing environment variables."""
    with runner.isolated_filesystem():
        # Create valid config
        config = {
            "project_name": "test-project",
            "endpoints": {
                "dev": "http://localhost:8000",
                "prod": "https://test-project.modal.run"
            },
            "limits": {
                "free_tier": {"per_ip": 5, "global": 100}
            },
            "required_keys": ["TEST_KEY", "MISSING_KEY"]
        }

        with open(".gimme-config.json", "w") as f:
            json.dump(config, f)

        # Create incomplete env (missing required keys)
        with open(".env", "w") as f:
            f.write("GIMME_PROJECT_NAME=test-project\n")
            f.write("GIMME_ADMIN_PASSWORD=test-password\n")
            f.write("TEST_KEY=test-value\n")
            # Missing MISSING_KEY

        # Run validation
        with patch.dict(os.environ, {}, clear=True):
            result = runner.invoke(validate_command)
            assert result.exit_code == 1
            assert "Environment validation failed" in result.output
            assert "Missing MISSING_KEY" in result.output


def test_validate_command_nonexistent_files(runner):
    """Test validate command with nonexistent files."""
    with runner.isolated_filesystem():
        # No files exist
        result = runner.invoke(validate_command)
        assert result.exit_code == 1
        assert "not found" in result.output


def test_cli_version(runner):
    """Test CLI version command."""
    result = runner.invoke(cli, ["--version"])
    assert result.exit_code == 0
    assert "version" in result.output.lower()


def test_init_with_config_path(runner):
    """Test init command with custom config path."""
    with runner.isolated_filesystem():
        result = runner.invoke(
            init_command,
            [
                "--project-name", "test-project",
                "--config-file", "custom-config.json",
                "--env-file", "custom.env"
            ],
            input="y\ntest-password\ny\ntest-token\ny\n"
        )

        print(f"Exit code: {result.exit_code}")
        print(f"Output: {result.output}")

        assert result.exit_code == 0

        # Check only the files that actually get created
        assert os.path.exists("custom-config.json")
        assert os.path.exists("custom.env")
        # Remove or comment out this assertion
        # assert os.path.exists("custom.env.example")


def test_init_with_existing_config_no_overwrite(runner):
    """Test init command with existing config and no overwrite."""
    with runner.isolated_filesystem():
        # Create existing config
        with open(".gimme-config.json", "w") as f:
            f.write("{}")

        # Run init without --force and respond "n" to overwrite prompt
        result = runner.invoke(init_command, input="n\n")
        assert result.exit_code == 0
        assert "Initialization cancelled" in result.output


def test_init_with_force_flag(runner):
    """Test init command with --force flag."""
    with runner.isolated_filesystem():
        # Create existing config
        with open(".gimme-config.json", "w") as f:
            f.write('{"project_name": "old-project"}')

        # Remove mocking and directly provide inputs
        result = runner.invoke(
            init_command,
            ["--force", "--project-name", "test-project"],
            input="y\ntest-password\ny\ntest-token\ny\n"  # Provide generous input
        )

        print(f"Exit code: {result.exit_code}")
        print(f"Output: {result.output}")

        assert result.exit_code == 0

        # Check config was overwritten
        with open(".gimme-config.json", "r") as f:
            config = json.load(f)
            assert config["project_name"] == "test-project"


def test_validate_with_custom_paths(runner):
    """Test validate command with custom file paths."""
    with runner.isolated_filesystem():
        # Create valid config with custom path
        config = {
            "project_name": "test-project",
            "endpoints": {
                "dev": "http://localhost:8000",
                "prod": "https://test-project.modal.run"
            },
            "required_keys": []
        }

        with open("custom-config.json", "w") as f:
            json.dump(config, f)

        # Create valid env with custom path
        with open("custom.env", "w") as f:
            f.write("GIMME_PROJECT_NAME=test-project\n")
            f.write("GIMME_ADMIN_PASSWORD=test-password\n")

        # Run validation with custom paths
        with patch.dict(os.environ, {}, clear=True):
            result = runner.invoke(validate_command, [
                "--config-file", "custom-config.json",
                "--env-file", "custom.env"
            ])
            assert result.exit_code == 0
            assert "All validations passed" in result.output


def test_init_missing_inquirer(runner):
    """Test init command when inquirer is missing."""
    with runner.isolated_filesystem():
        with patch("gimme_ai.utils.environment.get_env_or_prompt") as mock_prompt:
            # Simulate ImportError when importing inquirer
            mock_prompt.side_effect = ImportError("No module named 'inquirer'")

            result = runner.invoke(init_command)
            assert result.exit_code != 0
            # Updating assertion to match the actual error message
            assert "error during initialization" in result.output.lower()


def test_validate_config_syntax_error(runner):
    """Test validate command with syntax error in config file."""
    with runner.isolated_filesystem():
        # Create invalid JSON file
        with open(".gimme-config.json", "w") as f:
            f.write('{"project_name": "test-project", invalid json')

        result = runner.invoke(validate_command)

        # Check exit code
        assert result.exit_code != 0
        # Update the assertion to match our specific error message
        assert "Invalid JSON" in result.output


def test_validate_env_corruption(runner):
    """Test validate command with corrupted env file."""
    with runner.isolated_filesystem():
        # Create valid config
        config = {
            "project_name": "test-project",
            "endpoints": {
                "dev": "http://localhost:8000",
                "prod": "https://test-project.modal.run"
            },
            "required_keys": ["TEST_KEY"]
        }

        with open(".gimme-config.json", "w") as f:
            json.dump(config, f)

        # Create corrupt env file
        with open(".env", "w") as f:
            f.write("This is not a valid env file format\n")

        # Run validation
        result = runner.invoke(validate_command)

        # Should handle this gracefully
        assert result.exit_code != 0
        assert "Error" in result.output


def test_init_multiple_runs(runner):
    """Test running init command multiple times."""
    with runner.isolated_filesystem():
        # First initialization - direct input
        result1 = runner.invoke(
            init_command,
            ["--project-name", "project1"],
            input="y\npassword1\ny\ntest-token\ny\n"
        )

        print(f"First init exit code: {result1.exit_code}")
        print(f"First init output: {result1.output}")

        assert result1.exit_code == 0

        # Read config after first init
        with open(".gimme-config.json", "r") as f:
            config1 = json.load(f)

        # Second initialization with force flag - direct input
        result2 = runner.invoke(
            init_command,
            ["--force", "--project-name", "project2"],
            input="y\npassword2\ny\ntest-token\ny\n"
        )

        print(f"Second init exit code: {result2.exit_code}")
        print(f"Second init output: {result2.output}")

        assert result2.exit_code == 0

        # Read config after second init
        with open(".gimme-config.json", "r") as f:
            config2 = json.load(f)

        # Configs should be different
        assert config1["project_name"] == "project1"
        assert config2["project_name"] == "project2"


def test_validate_with_warnings(runner):
    """Test validate command with warnings but no errors."""
    with runner.isolated_filesystem():
        # Create config with non-standard but valid settings
        config = {
            "project_name": "test-project",
            "endpoints": {
                "dev": "http://localhost:8000",
                "prod": "https://test-project.modal.run"
            },
            "limits": {
                "free_tier": {"per_ip": 1000, "global": 10000}  # Very high limits
            },
            "required_keys": []  # No keys required (unusual)
        }

        with open(".gimme-config.json", "w") as f:
            json.dump(config, f)

        # Create minimal env
        with open(".env", "w") as f:
            f.write("GIMME_ADMIN_PASSWORD=test-password\n")

        # Run validation
        with patch.dict(os.environ, {}, clear=True):
            result = runner.invoke(validate_command)
            assert result.exit_code == 0
            assert "validation passed" in result.output
