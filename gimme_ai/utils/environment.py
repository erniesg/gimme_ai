# gimme_ai/utils/environment.py
"""Environment variable utilities for gimme_ai."""

import os
import re
import sys
from typing import Dict, List, Optional, Set
import click

# Define a safe import for inquirer to handle the case where it's not installed
def _safe_import_inquirer():
    """Safely import inquirer, raising a clear error if not installed."""
    try:
        import inquirer
        return inquirer
    except ImportError:
        raise ImportError(
            "The 'inquirer' package is required for interactive prompts. "
            "Please install it with 'pip install inquirer'."
        )


def load_env_file(file_path: str) -> Dict[str, str]:
    """Load environment variables from a .env file.

    Args:
        file_path: Path to the .env file

    Returns:
        Dictionary of environment variables
    """
    if not os.path.exists(file_path):
        return {}

    env_vars = {}

    try:
        with open(file_path, "r") as f:
            for line in f:
                line = line.strip()

                # Skip empty lines and comments
                if not line or line.startswith("#"):
                    continue

                # Handle key=value format (including = in values)
                if "=" in line:
                    key, value = line.split("=", 1)
                    env_vars[key.strip()] = value.strip()
                else:
                    # Invalid format - line doesn't contain equals sign
                    raise ValueError(f"Invalid environment file format: {line}")
    except Exception as e:
        raise ValueError(f"Error parsing environment file: {e}")

    return env_vars


def save_env_file(file_path: str, env_vars: Dict[str, str], sort_keys: bool = True) -> None:
    """Save environment variables to a .env file.

    Args:
        file_path: Path to the .env file
        env_vars: Dictionary of environment variables
        sort_keys: Whether to sort keys alphabetically
    """
    # Read existing file if it exists to preserve comments and order
    existing_lines = []
    existing_keys = set()

    if os.path.exists(file_path):
        with open(file_path, "r") as f:
            for line in f:
                line = line.strip()
                if line and "=" in line and not line.startswith("#"):
                    key = line.split("=", 1)[0].strip()
                    existing_keys.add(key)
                existing_lines.append(line)

    # Update or append variables
    with open(file_path, "w") as f:
        # First write existing lines, updating values for existing keys
        for line in existing_lines:
            if line and "=" in line and not line.startswith("#"):
                key = line.split("=", 1)[0].strip()
                if key in env_vars:
                    f.write(f"{key}={env_vars[key]}\n")
                    continue
            f.write(f"{line}\n")

        # Then write new keys
        new_keys = set(env_vars.keys()) - existing_keys
        if sort_keys:
            new_keys = sorted(new_keys)

        if new_keys and existing_lines:
            f.write("\n")  # Add a blank line before new variables

        for key in new_keys:
            f.write(f"{key}={env_vars[key]}\n")


def validate_env_vars(required_vars: List[str]) -> List[str]:
    """Check if required environment variables are set.

    Args:
        required_vars: List of required variable names

    Returns:
        List of missing variable names
    """
    missing = []

    for var in required_vars:
        if not os.environ.get(var):
            missing.append(var)

    return missing


def get_env_or_prompt(var_name: str, prompt: Optional[str] = None,
                     default: Optional[str] = None) -> str:
    """Get environment variable or prompt user for it.

    Args:
        var_name: Environment variable name
        prompt: Prompt message (defaults to "Enter {var_name}")
        default: Default value

    Returns:
        Variable value
    """
    value = os.environ.get(var_name)

    if value is None or value == "":
        # Import inquirer only when needed
        inquirer = _safe_import_inquirer()

        if prompt is None:
            prompt = f"Enter {var_name}"

        questions = [
            inquirer.Text(
                "value",
                message=prompt,
                default=default or ""
            )
        ]

        answers = inquirer.prompt(questions)
        value = answers["value"] if answers else ""

        # Set in environment for subsequent calls
        os.environ[var_name] = value

    return value
