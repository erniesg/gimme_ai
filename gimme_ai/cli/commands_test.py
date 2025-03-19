"""Testing commands for the gimme_ai CLI."""

import os
import sys
import json
import time
import click
import requests
from typing import Optional, Dict, Any
from pathlib import Path
from tabulate import tabulate

from ..utils.environment import load_env_file
from ..config import GimmeConfig, load_config

@click.command(name="test")
@click.argument("url", required=False)
@click.option(
    "--admin-password",
    help="Admin password for testing admin access",
    required=False,
)
@click.option(
    "--env-file",
    default=".env",
    help="Path to environment file (to get admin password)",
    show_default=True,
)
@click.option(
    "--config-file",
    default=".gimme-config.json",
    help="Path to configuration file",
    show_default=True,
)
@click.option(
    "--verbose", "-v",
    is_flag=True,
    help="Show detailed test output",
)
def test_command(
    url: Optional[str],
    admin_password: Optional[str],
    env_file: str,
    config_file: str,
    verbose: bool,
):
    """Test your deployed API gateway.

    URL is the endpoint to test (e.g., https://your-project.workers.dev).
    If not provided, it will be automatically detected from config or prompted.
    """
    endpoint = get_endpoint_url(url, config_file)
    admin_pw = get_admin_password(admin_password, env_file)

    click.echo("🧪 Testing your API gateway...")
    click.echo(f"🔗 Target: {endpoint}")

    # Run basic tests
    test_status_endpoint(endpoint, verbose)
    test_authentication(endpoint, admin_pw, verbose)
    test_rate_limiting(endpoint, admin_pw, config_file, verbose)

    # Check if workflow is enabled and test it if so
    if is_workflow_enabled(config_file):
        test_workflow(endpoint, admin_pw, config_file, verbose)
    else:
        click.echo("\n🔄 Workflow: SKIPPED (not enabled in configuration)")

@click.command(name="test-auth")
@click.argument("url", required=False)
@click.option(
    "--admin-password",
    help="Admin password for testing admin access",
    required=False,
)
@click.option(
    "--env-file",
    default=".env",
    help="Path to environment file (to get admin password)",
    show_default=True,
)
def test_auth_command(
    url: Optional[str],
    admin_password: Optional[str],
    env_file: str,
):
    """Test authentication on your API gateway.

    URL is the endpoint to test (e.g., https://your-project.workers.dev).
    If not provided, it will be automatically detected from config or prompted.
    """
    endpoint = get_endpoint_url(url, ".gimme-config.json")
    admin_pw = get_admin_password(admin_password, env_file)

    test_authentication(endpoint, admin_pw, True)

@click.command(name="test-rate-limits")
@click.argument("url", required=False)
@click.option(
    "--admin-password",
    help="Admin password for testing admin access",
    required=False,
)
@click.option(
    "--env-file",
    default=".env",
    help="Path to environment file (to get admin password)",
    show_default=True,
)
@click.option(
    "--config-file",
    default=".gimme-config.json",
    help="Path to configuration file",
    show_default=True,
)
@click.option(
    "--requests",
    type=int,
    default=15,
    help="Number of requests to send for rate limit testing",
)
def test_rate_limits_command(
    url: Optional[str],
    admin_password: Optional[str],
    env_file: str,
    config_file: str,
    requests: int,
):
    """Test rate limiting on your API gateway.

    URL is the endpoint to test (e.g., https://your-project.workers.dev).
    If not provided, it will be automatically detected from config or prompted.
    """
    endpoint = get_endpoint_url(url, config_file)
    admin_pw = get_admin_password(admin_password, env_file)

    test_rate_limiting(endpoint, admin_pw, config_file, True, requests)

@click.command(name="test-workflow")
@click.argument("url", required=False)
@click.option(
    "--admin-password",
    help="Admin password for testing admin access",
    required=False,
)
@click.option(
    "--env-file",
    default=".env",
    help="Path to environment file (to get admin password)",
    show_default=True,
)
@click.option(
    "--config-file",
    default=".gimme-config.json",
    help="Path to configuration file",
    show_default=True,
)
@click.option(
    "--params",
    help="JSON string of parameters to pass to the workflow",
    default='{"requestId": "test-request", "content": "Test content"}',
)
@click.option(
    "--follow",
    is_flag=True,
    default=True,
    help="Follow workflow execution by polling for status updates",
)
def test_workflow_command(
    url: Optional[str],
    admin_password: Optional[str],
    env_file: str,
    config_file: str,
    params: str,
    follow: bool,
):
    """Test workflow functionality.

    URL is the endpoint to test (e.g., https://your-project.workers.dev).
    If not provided, it will be automatically detected from config or prompted.
    """
    endpoint = get_endpoint_url(url, config_file)
    admin_pw = get_admin_password(admin_password, env_file)

    if not is_workflow_enabled(config_file):
        click.echo("❌ Workflow is not enabled in configuration. Aborting test.")
        return

    test_workflow(endpoint, admin_pw, config_file, True, params, follow)

@click.command(name="test-all")
@click.argument("url", required=False)
@click.option(
    "--admin-password",
    help="Admin password for testing admin access",
    required=False,
)
@click.option(
    "--env-file",
    default=".env",
    help="Path to environment file (to get admin password)",
    show_default=True,
)
@click.option(
    "--config-file",
    default=".gimme-config.json",
    help="Path to configuration file",
    show_default=True,
)
@click.option(
    "--verbose", "-v",
    is_flag=True,
    help="Show detailed output",
)
@click.option(
    "--skip-reset-confirm",
    is_flag=True,
    help="Skip confirmation prompts when resetting rate limits",
)
def test_all_command(
    url: Optional[str],
    admin_password: Optional[str],
    env_file: str,
    config_file: str,
    verbose: bool,
    skip_reset_confirm: bool,
):
    """Run all tests on your API gateway.

    URL is the endpoint to test (e.g., https://your-project.workers.dev).
    If not provided, it will be automatically detected from config or prompted.
    """
    endpoint = get_endpoint_url(url, config_file)
    admin_pw = get_admin_password(admin_password, env_file)

    click.echo("🧪 Running all tests on your API gateway...")
    click.echo(f"🔗 Target: {endpoint}")

    # Warning about rate limit resets
    if admin_pw:
        click.echo("\n⚠️  Note: These tests will reset your API gateway's rate limits.")
        click.echo("⚠️  This ensures tests start with a clean slate but could affect ongoing API usage.")
        if not skip_reset_confirm and not click.confirm("   Continue with tests?", default=True):
            click.echo("   Testing cancelled.")
            return

    all_passed = True

    # Test 1: Status endpoint
    click.echo("\n📋 TEST 1: BASIC STATUS =====================================")
    if not test_status_endpoint(endpoint, verbose):
        all_passed = False

    # Test 2: Authentication
    click.echo("\n🔐 TEST 2: AUTHENTICATION ==================================")
    if not test_authentication(endpoint, admin_pw, verbose):
        all_passed = False

    # Test 3: Rate Limiting
    click.echo("\n🚦 TEST 3: RATE LIMITING ===================================")
    if not test_rate_limiting(endpoint, admin_pw, config_file, verbose, 15, True):  # Skip intermediate confirmations
        all_passed = False

    # Test 4: Workflow (if enabled)
    if is_workflow_enabled(config_file):
        click.echo("\n🔄 TEST 4: WORKFLOW ========================================")
        if not test_workflow(endpoint, admin_pw, config_file, verbose):
            all_passed = False
    else:
        click.echo("\n🔄 TEST 4: WORKFLOW ========================================")
        click.echo("ℹ️ Workflow tests skipped (workflow not enabled in configuration).")

    # Summary
    click.echo("\n📊 ALL TESTS COMPLETED ======================================")

    if all_passed:
        click.echo("🎉 All tests passed successfully!")
    else:
        click.echo("⚠️ Some tests failed. See details above.")

    # Reset rate limits as a cleanup step
    if admin_pw:
        click.echo("\n🔄 Final cleanup:")
        reset_rate_limits(endpoint, admin_pw, skip_reset_confirm)

# ========== Helper Functions ==========

def get_endpoint_url(url: Optional[str], config_file: str) -> str:
    """Get the endpoint URL from the provided argument, config, or user prompt."""
    if url:
        # Use the provided URL
        return normalize_url(url)

    # Try to get the URL from the project name in config
    try:
        if os.path.exists(config_file):
            with open(config_file, "r") as f:
                config_data = json.load(f)

            project_name = config_data.get("project_name")
            if project_name:
                # Format URL based on Cloudflare Workers naming convention
                possible_url = f"https://{project_name}.workers.dev"
                click.echo(f"Using URL derived from project name: {possible_url}")
                return possible_url
    except Exception as e:
        click.echo(f"Warning: Could not extract URL from config: {e}", err=True)

    # Prompt the user for a URL
    return click.prompt("Please enter your API gateway URL (e.g., https://your-project.workers.dev)")

def normalize_url(url: str) -> str:
    """Normalize the endpoint URL by removing trailing slashes."""
    return url.rstrip('/')

def get_admin_password(admin_password: Optional[str], env_file: str) -> Optional[str]:
    """Get the admin password from the provided argument or env file."""
    if admin_password:
        return admin_password

    if os.path.exists(env_file):
        try:
            env_vars = load_env_file(env_file)
            admin_pw = env_vars.get("GIMME_ADMIN_PASSWORD")
            if admin_pw:
                click.echo(f"Using admin password from {env_file}")
                return admin_pw
        except Exception as e:
            click.echo(f"Warning: Could not load admin password from env file: {e}", err=True)

    click.echo("No admin password provided or found in env file.")
    return None

def is_workflow_enabled(config_file: str) -> bool:
    """Check if workflow is enabled in the configuration."""
    try:
        if os.path.exists(config_file):
            with open(config_file, "r") as f:
                config_data = json.load(f)

            return config_data.get("workflow", {}).get("enabled", False)
    except Exception:
        # If there's any error, assume workflow is not enabled
        return False

    return False

def reset_rate_limits(endpoint: str, admin_password: str, skip_confirm: bool = False) -> bool:
    """Reset rate limits using admin API."""
    click.echo("\n🔄 Resetting rate limits...")

    # Warn users about the implications of resetting
    if not skip_confirm:
        click.echo("⚠️  This will reset all rate limit counters on your API gateway.")
        click.echo("⚠️  Any ongoing API usage from other clients may be affected.")
        if not click.confirm("   Continue with reset?", default=True):
            click.echo("   Rate limit reset cancelled.")
            return False

    try:
        headers = {"Authorization": f"Bearer {admin_password}"}
        response = requests.get(f"{endpoint}/admin/reset-limits", headers=headers)

        if response.status_code == 200:
            click.echo("✅ Rate limits reset successfully")
            return True
        else:
            click.echo(f"⚠️ Failed to reset rate limits: {response.status_code}")
            return False
    except Exception as e:
        click.echo(f"⚠️ Error resetting rate limits: {e}")
        return False

def get_rate_limits(config_file: str) -> tuple:
    """Get rate limits from the configuration file."""
    per_ip_limit = 10  # Default
    global_limit = 100  # Default

    try:
        if os.path.exists(config_file):
            with open(config_file, "r") as f:
                config_data = json.load(f)

            # Extract rate limits from config
            if "limits" in config_data and "free_tier" in config_data["limits"]:
                free_tier = config_data["limits"]["free_tier"]
                if isinstance(free_tier, dict):
                    if "per_ip" in free_tier:
                        per_ip_limit = free_tier["per_ip"]

                    if "global" in free_tier:
                        global_limit = free_tier["global"]
    except Exception:
        # Use defaults if there's any error
        pass

    return per_ip_limit, global_limit

# ========== Test Functions ==========

def test_status_endpoint(endpoint: str, verbose: bool) -> bool:
    """Test the status endpoint."""
    click.echo("🔍 Testing status endpoint...")
    try:
        response = requests.get(f"{endpoint}/status")
        if response.status_code == 200:
            data = response.json()
            click.echo(f"✅ Status: {data.get('status', 'unknown')}")
            click.echo(f"✅ Project: {data.get('project', 'unknown')}")
            click.echo(f"✅ Mode: {data.get('mode', 'unknown')}")
            return True
        else:
            click.echo(f"❌ Status endpoint failed: {response.status_code}")
            if verbose:
                click.echo(response.text)
            return False
    except Exception as e:
        click.echo(f"❌ Error testing status endpoint: {e}")
        return False

def test_authentication(endpoint: str, admin_password: Optional[str], verbose: bool) -> bool:
    """Test authentication on the API gateway."""
    click.echo("🔐 Testing API gateway authentication...")
    results = []
    success = True

    # Test 1: Free tier access (no auth)
    click.echo("\n  Testing free tier access (no auth)...")
    try:
        response = requests.get(f"{endpoint}/api/test")
        if response.status_code in [200, 404]:  # 404 is ok if endpoint doesn't exist
            click.echo(f"  ✅ Free tier access: {response.status_code}")
            results.append(["Free Tier Access", "✅ PASS", response.status_code])
        elif response.status_code == 429:
            click.echo("  ⚠️ Free tier rate limited")
            results.append(["Free Tier Access", "⚠️ RATE LIMITED", response.status_code])
        else:
            click.echo(f"  ❌ Free tier access failed: {response.status_code}")
            results.append(["Free Tier Access", "❌ FAIL", response.status_code])
            success = False
            if verbose:
                click.echo(response.text)
    except Exception as e:
        click.echo(f"  ❌ Error testing free tier access: {e}")
        results.append(["Free Tier Access", "❌ ERROR", str(e)])
        success = False

    # Test 2: Invalid auth
    click.echo("\n  Testing invalid authentication...")
    try:
        headers = {"Authorization": "Bearer invalid-password"}
        response = requests.get(f"{endpoint}/api/test", headers=headers)
        if response.status_code == 401:
            click.echo("  ✅ Invalid authentication correctly rejected")
            results.append(["Invalid Auth", "✅ PASS", response.status_code])
        else:
            click.echo(f"  ❌ Invalid authentication not rejected: {response.status_code}")
            results.append(["Invalid Auth", "❌ FAIL", response.status_code])
            success = False
            if verbose:
                click.echo(response.text)
    except Exception as e:
        click.echo(f"  ❌ Error testing invalid authentication: {e}")
        results.append(["Invalid Auth", "❌ ERROR", str(e)])
        success = False

    # Test 3: Valid auth (if admin password is provided)
    if admin_password:
        click.echo("\n  Testing valid authentication...")
        try:
            headers = {"Authorization": f"Bearer {admin_password}"}
            response = requests.get(f"{endpoint}/api/test", headers=headers)
            if response.status_code in [200, 404]:  # 404 is ok if endpoint doesn't exist
                click.echo("  ✅ Admin authentication successful")
                results.append(["Admin Auth", "✅ PASS", response.status_code])
            else:
                click.echo(f"  ❌ Admin authentication failed: {response.status_code}")
                results.append(["Admin Auth", "❌ FAIL", response.status_code])
                success = False
                if verbose:
                    click.echo(response.text)
        except Exception as e:
            click.echo(f"  ❌ Error testing admin authentication: {e}")
            results.append(["Admin Auth", "❌ ERROR", str(e)])
            success = False
    else:
        click.echo("\n  ⚠️ Skipping admin authentication test (no password provided)")
        results.append(["Admin Auth", "⚠️ SKIPPED", "N/A"])

    # Summary
    click.echo("\n📊 Authentication Test Summary:")
    try:
        table = tabulate(results, headers=["Test", "Result", "Status Code"], tablefmt="grid")
        click.echo(table)
    except ImportError:
        # Fallback if tabulate is not installed
        for test, result, status in results:
            click.echo(f"{test}: {result} ({status})")

    return success

def test_rate_limiting(
    endpoint: str,
    admin_password: Optional[str],
    config_file: str,
    verbose: bool,
    requests_count: int = 15,
    skip_reset_confirm: bool = False
) -> bool:
    """Test rate limiting on the API gateway."""
    click.echo("🚦 Testing API gateway rate limiting...")

    # Add a clear warning about rate limits being reset
    if admin_password:
        click.echo("⚠️  Note: Rate limit tests will reset your API gateway's rate limits.")
        click.echo("⚠️  This ensures tests start with a clean slate but could affect ongoing API usage.")

    results = []
    success = True

    # Get rate limits from config
    per_ip_limit, global_limit = get_rate_limits(config_file)
    click.echo(f"  Using limits - per IP: {per_ip_limit}, global: {global_limit}")

    # Reset rate limits if admin password is available
    if admin_password:
        reset_rate_limits(endpoint, admin_password, skip_reset_confirm)

    # Test 1: Per-IP Rate limiting
    click.echo(f"\n  Testing per-IP rate limiting (limit: {per_ip_limit})...")
    try:
        rate_limit_hit = False
        # Use min(requests_count, per_ip_limit*2) to avoid excessive requests
        test_requests = min(requests_count, per_ip_limit * 2)

        for i in range(test_requests):
            response = requests.get(f"{endpoint}/api/test?test_type=ip_only&req={i}")
            status = response.status_code

            if verbose or i % 5 == 0 or i == test_requests - 1:
                click.echo(f"    Request {i+1}: Status {status}")

            if status == 429:
                rate_limit_hit = True
                click.echo(f"  ✅ Per-IP rate limit triggered after {i+1} requests")
                break
            time.sleep(0.1)  # Small delay to avoid overwhelming the server

        if rate_limit_hit:
            results.append(["Per-IP Rate Limiting", "✅ PASS", f"Triggered after {i+1} requests"])
        else:
            click.echo(f"  ⚠️ Per-IP rate limit not triggered after {test_requests} requests")
            results.append(["Per-IP Rate Limiting", "⚠️ WARNING", f"Not triggered after {test_requests} requests"])
            success = False
    except Exception as e:
        click.echo(f"  ❌ Error testing per-IP rate limiting: {e}")
        results.append(["Per-IP Rate Limiting", "❌ ERROR", str(e)])
        success = False

    # Reset rate limits before global test if admin password available
    if admin_password:
        reset_rate_limits(endpoint, admin_password, True)  # Skip confirmation for intermediate reset

    # Test 2: Global Rate limiting
    click.echo(f"\n  Testing global rate limiting (limit: {global_limit})...")
    try:
        global_limit_hit = False
        # Use min(requests_count, global_limit*1.5) to avoid excessive requests
        test_requests = min(requests_count, int(global_limit * 1.5))

        for i in range(test_requests):
            # Use a unique query parameter to avoid caching
            response = requests.get(f"{endpoint}/api/test?test_type=global_only&unique={i}")
            status = response.status_code

            if verbose or i % 10 == 0 or i == test_requests - 1:
                click.echo(f"    Request {i+1}: Status {status}")

            if status == 429:
                global_limit_hit = True
                click.echo(f"  ✅ Global rate limit triggered after {i+1} requests")
                break

            time.sleep(0.1)  # Small delay to avoid overwhelming the server

        if global_limit_hit:
            results.append(["Global Rate Limiting", "✅ PASS", f"Triggered after {i+1} requests"])
        else:
            click.echo(f"  ⚠️ Global rate limit not triggered after {test_requests} requests")
            results.append(["Global Rate Limiting", "⚠️ WARNING", f"Not triggered after {test_requests} requests"])
            success = False
    except Exception as e:
        click.echo(f"  ❌ Error testing global rate limiting: {e}")
        results.append(["Global Rate Limiting", "❌ ERROR", str(e)])
        success = False

    # Summary
    click.echo("\n📊 Rate Limiting Test Summary:")
    try:
        table = tabulate(results, headers=["Test", "Result", "Details"], tablefmt="grid")
        click.echo(table)
    except ImportError:
        # Fallback if tabulate is not installed
        for test, result, details in results:
            click.echo(f"{test}: {result} ({details})")

    # Reset rate limits after testing if admin password available
    if admin_password:
        click.echo("\n🔄 Final cleanup:")
        reset_rate_limits(endpoint, admin_password, skip_reset_confirm)

    return success

def test_workflow(
    endpoint: str,
    admin_password: Optional[str],
    config_file: str,
    verbose: bool,
    params_str: str = '{"requestId": "test-request", "content": "Test content"}',
    follow: bool = True,
    interval: int = 2,
    timeout: int = 60
) -> bool:
    """Test workflow functionality."""
    click.echo("🔄 Testing workflow functionality...")

    # Prepare workflow endpoint
    workflow_endpoint = f"{endpoint}/workflow"

    # Prepare headers
    headers = {
        "Content-Type": "application/json"
    }

    if admin_password:
        headers["Authorization"] = f"Bearer {admin_password}"
        click.echo("  ✅ Using admin authentication for workflow test")

    # Parse and validate parameters
    try:
        workflow_params = json.loads(params_str)
        if verbose:
            click.echo(f"  ✅ Using parameters: {json.dumps(workflow_params, indent=2)}")
    except json.JSONDecodeError:
        click.echo(f"  ❌ Invalid JSON in params: {params_str}")
        return False

    # Start workflow test
    click.echo("\n  🚀 Triggering workflow...")
    try:
        response = requests.post(workflow_endpoint, json=workflow_params, headers=headers)

        if response.status_code != 200:
            click.echo(f"  ❌ Workflow trigger failed with status {response.status_code}:")
            if verbose:
                click.echo(response.text)
            return False

        result = response.json()
        click.echo(f"  ✅ Workflow triggered successfully!")
        if verbose:
            click.echo(json.dumps(result, indent=2))

        # Follow workflow execution if requested
        if follow and "instanceId" in result:
            instance_id = result["instanceId"]
            click.echo(f"\n  🔍 Following workflow execution for instanceId: {instance_id}")

            start_time = time.time()
            completed = False

            while time.time() - start_time < timeout:
                status_url = f"{workflow_endpoint}?instanceId={instance_id}"
                status_response = requests.get(status_url, headers=headers)

                if status_response.status_code != 200:
                    click.echo(f"  ❌ Failed to get workflow status: {status_response.status_code}")
                    if verbose:
                        click.echo(status_response.text)
                    return False

                status_data = status_response.json()
                status = status_data.get("status", {})

                # Format the status nicely
                click.echo(f"\n  ℹ️ Workflow status at {time.strftime('%H:%M:%S')}:")
                if verbose:
                    click.echo(json.dumps(status, indent=2))
                else:
                    # Simplified status
                    current_status = status.get("status", "running")
                    current_step = status.get("currentStep", "unknown")
                    completed_steps = status.get("completedSteps", [])
                    click.echo(f"  Status: {current_status}, Current step: {current_step}")
                    if completed_steps:
                        click.echo(f"  Completed steps: {', '.join(completed_steps)}")

                # Check if workflow is completed
                if status.get("status") == "completed":
                    click.echo("\n  ✅ Workflow completed successfully!")
                    completed = True
                    break
                elif "error" in status:
                    click.echo(f"\n  ❌ Workflow failed with error: {status.get('error')}")
                    return False

                # Wait before polling again
                if verbose:
                    click.echo(f"  ⏳ Waiting {interval} seconds before checking again...")
                time.sleep(interval)

            if not completed and time.time() - start_time >= timeout:
                click.echo(f"\n  ⚠️ Workflow execution follow timed out after {timeout} seconds")
                click.echo(f"  You can check the status manually with:")
                click.echo(f"  gimme-ai workflow --endpoint {endpoint} --check-status --instance-id {instance_id}")
                return False

            return completed

        elif "instanceId" in result:
            click.echo("\n  ℹ️ To check status later, run:")
            click.echo(f"  gimme-ai workflow --endpoint {endpoint} --check-status --instance-id {result['instanceId']}")
            return True
        else:
            return True

    except Exception as e:
        click.echo(f"  ❌ Error testing workflow: {e}")
        if verbose:
            import traceback
            click.echo(traceback.format_exc())
        return False
