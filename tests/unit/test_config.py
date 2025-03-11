# tests/unit/test_config.py
"""Tests for configuration management."""

import os
import json
import tempfile
from pathlib import Path
import pytest
from gimme_ai.config import (
    GimmeConfig,
    create_default_config,
    validate_config,
)


def test_create_default_config():
    """Test creating default configuration."""
    config = create_default_config("test-project")

    assert config["project_name"] == "test-project"
    assert config["endpoints"]["dev"] == "http://localhost:8000"
    assert config["endpoints"]["prod"] == "https://test-project.modal.run"
    assert config["limits"]["free_tier"]["per_ip"] == 5
    assert config["limits"]["free_tier"]["global"] == 100
    assert "MODAL_TOKEN_ID" in config["required_keys"]
    assert "MODAL_TOKEN_SECRET" in config["required_keys"]


def test_validate_config_valid():
    """Test validating a valid configuration."""
    config = create_default_config("test-project")
    issues = validate_config(config)
    assert not issues


def test_validate_config_invalid():
    """Test validating an invalid configuration."""
    # Missing project_name
    config = {
        "endpoints": {
            "dev": "http://localhost:8000",
            "prod": "https://test-project.modal.run"
        }
    }
    issues = validate_config(config)
    assert issues
    assert any("project_name" in issue.lower() for issue in issues)


def test_load_config_from_file():
    """Test loading configuration from file."""
    config_data = {
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

    with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
        json.dump(config_data, f)
        config_path = f.name

    try:
        config = GimmeConfig.from_file(config_path)
        assert config.project_name == "test-project"
        assert config.endpoints.dev == "http://localhost:8000"
        assert config.endpoints.prod == "https://test-project.modal.run"
        assert config.limits["free_tier"].per_ip == 5
        assert config.limits["free_tier"].global_limit == 100
        assert config.required_keys == ["TEST_KEY"]
    finally:
        os.unlink(config_path)


def test_project_name_validation():
    """Test project name validation."""
    # Valid names
    GimmeConfig(
        project_name="test-project",
        endpoints={"dev": "http://localhost:8000", "prod": "https://example.com"}
    )

    GimmeConfig(
        project_name="test123",
        endpoints={"dev": "http://localhost:8000", "prod": "https://example.com"}
    )

    # Invalid names
    with pytest.raises(ValueError):
        GimmeConfig(
            project_name="",  # Empty
            endpoints={"dev": "http://localhost:8000", "prod": "https://example.com"}
        )

    with pytest.raises(ValueError):
        GimmeConfig(
            project_name="-test",  # Starts with hyphen
            endpoints={"dev": "http://localhost:8000", "prod": "https://example.com"}
        )

    with pytest.raises(ValueError):
        GimmeConfig(
            project_name="test_project",  # Invalid character
            endpoints={"dev": "http://localhost:8000", "prod": "https://example.com"}
        )
