# tests/unit/test_utils.py
"""Tests for utility functions."""

import os
import tempfile
from pathlib import Path
import pytest
from unittest.mock import patch
from gimme_ai.utils.environment import (
    load_env_file,
    save_env_file,
    validate_env_vars,
    get_env_or_prompt,
)


def test_load_env_file():
    """Test loading environment variables from file."""
    env_content = """
# Comment
KEY1=value1
KEY2=value2

# Another comment
KEY3=value with spaces
KEY4=value=with=equals
"""

    with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
        f.write(env_content)
        env_path = f.name

    try:
        env_vars = load_env_file(env_path)

        assert env_vars["KEY1"] == "value1"
        assert env_vars["KEY2"] == "value2"
        assert env_vars["KEY3"] == "value with spaces"
        assert env_vars["KEY4"] == "value=with=equals"
        assert "Comment" not in env_vars
    finally:
        os.unlink(env_path)


def test_load_env_file_nonexistent():
    """Test loading environment from nonexistent file."""
    env_vars = load_env_file("/nonexistent/file")
    assert env_vars == {}


def test_save_env_file():
    """Test saving environment variables to file."""
    env_vars = {
        "KEY1": "value1",
        "KEY2": "value2",
        "KEY3": "value with spaces",
    }

    with tempfile.NamedTemporaryFile(delete=False) as f:
        env_path = f.name

    try:
        save_env_file(env_path, env_vars)
        loaded_vars = load_env_file(env_path)

        assert loaded_vars == env_vars
    finally:
        os.unlink(env_path)


def test_save_env_file_with_existing():
    """Test saving environment variables to existing file."""
    original_content = """
# Comment
KEY1=original1
KEY2=original2

# Another comment
"""

    with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
        f.write(original_content)
        env_path = f.name

    try:
        # Update some keys and add new ones
        env_vars = {
            "KEY1": "updated1",
            "KEY3": "new3",
        }

        save_env_file(env_path, env_vars)
        loaded_vars = load_env_file(env_path)

        assert loaded_vars["KEY1"] == "updated1"  # Updated
        assert loaded_vars["KEY2"] == "original2"  # Preserved
        assert loaded_vars["KEY3"] == "new3"  # Added
    finally:
        os.unlink(env_path)


def test_validate_env_vars():
    """Test validating environment variables."""
    with patch.dict(os.environ, {"KEY1": "value1", "KEY3": "value3"}, clear=True):
        # Test with all variables present
        missing = validate_env_vars(["KEY1", "KEY3"])
        assert not missing

        # Test with some variables missing
        missing = validate_env_vars(["KEY1", "KEY2", "KEY3"])
        assert missing == ["KEY2"]

        # Test with all variables missing
        missing = validate_env_vars(["KEY4", "KEY5"])
        assert missing == ["KEY4", "KEY5"]


def test_get_env_or_prompt():
    """Test getting environment variable or prompting."""
    # Test with variable already set
    with patch.dict(os.environ, {"TEST_VAR": "test_value"}, clear=True):
        value = get_env_or_prompt("TEST_VAR")
        assert value == "test_value"

    # Test with prompt
    with patch.dict(os.environ, {}, clear=True):
        with patch("inquirer.prompt") as mock_prompt:
            mock_prompt.return_value = {"value": "prompted_value"}
            value = get_env_or_prompt("TEST_VAR", prompt="Enter test var")
            assert value == "prompted_value"
            mock_prompt.assert_called_once()


def test_get_env_or_prompt_with_default():
    """Test getting environment variable with default."""
    with patch.dict(os.environ, {}, clear=True):
        with patch("inquirer.prompt") as mock_prompt:
            mock_prompt.return_value = {"value": "default_value"}
            value = get_env_or_prompt("TEST_VAR", default="default_value")
            assert value == "default_value"
