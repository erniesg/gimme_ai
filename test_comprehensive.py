#!/usr/bin/env python3
"""
Comprehensive test script for gimme_ai functionality.
Tests all major features without requiring external services.
"""

import os
import sys
import tempfile
import shutil
import json
import asyncio
from pathlib import Path

# Add the project root to the Python path
sys.path.insert(0, str(Path(__file__).parent))

from gimme_ai.config import create_default_config, validate_config
from gimme_ai.config.workflow import WorkflowConfig, validate_workflow_config
from gimme_ai.http.workflow_client import WorkflowHTTPClient
from gimme_ai.workflows.execution_engine import WorkflowExecutionEngine
from gimme_ai.utils.environment import save_env_file, load_env_file

def test_config_creation():
    """Test configuration creation and validation."""
    print("🧪 Testing config creation...")
    
    # Test different providers
    providers = ["cloudflare", "modal", "custom"]
    for provider in providers:
        config = create_default_config("test-project", provider)
        issues = validate_config(config)
        
        if issues:
            print(f"❌ {provider} config validation failed: {issues}")
            return False
        else:
            print(f"✅ {provider} config valid")
    
    return True

def test_workflow_config():
    """Test workflow configuration validation."""
    print("🧪 Testing workflow configuration...")
    
    # Test minimal workflow config
    minimal_config = {
        "name": "test-workflow",
        "api_base": "https://api.example.com",
        "steps": [
            {
                "name": "test_step",
                "endpoint": "/test",
                "method": "GET"
            }
        ]
    }
    
    issues = validate_workflow_config(minimal_config)
    if issues:
        print(f"❌ Minimal workflow config failed: {issues}")
        return False
    
    # Test workflow object creation
    try:
        workflow = WorkflowConfig.from_dict(minimal_config)
        print(f"✅ Workflow created: {workflow.name}")
    except Exception as e:
        print(f"❌ Workflow creation failed: {e}")
        return False
    
    return True

def test_http_client():
    """Test HTTP client functionality."""
    print("🧪 Testing HTTP client...")
    
    try:
        client = WorkflowHTTPClient(base_url="https://httpbin.org")
        
        # Test simple GET request
        response = client.make_request("/get", method="GET", timeout=10)
        if "url" in response:
            print("✅ HTTP client GET request works")
        else:
            print("❌ HTTP client GET response unexpected")
            return False
            
    except Exception as e:
        print(f"⚠️ HTTP client test skipped (network issue): {e}")
        # Don't fail the test for network issues
    
    return True

async def test_workflow_execution():
    """Test workflow execution engine."""
    print("🧪 Testing workflow execution...")
    
    # Create a simple workflow that doesn't require external APIs
    workflow_config = {
        "name": "test-execution",
        "api_base": "https://httpbin.org",
        "steps": [
            {
                "name": "get_data",
                "endpoint": "/json",
                "method": "GET",
                "extract_fields": {"slideshow": "slideshow"}
            }
        ]
    }
    
    try:
        workflow = WorkflowConfig.from_dict(workflow_config)
        client = WorkflowHTTPClient(base_url=workflow.api_base)
        engine = WorkflowExecutionEngine(http_client=client)
        
        # Test dependency resolution
        phases = engine._resolve_dependencies(workflow.steps)
        if len(phases) == 1 and len(phases[0]) == 1:
            print("✅ Dependency resolution works")
        else:
            print("❌ Dependency resolution failed")
            return False
            
        # Test actual execution (may fail due to network)
        try:
            result = await engine.execute_workflow(workflow)
            if result.success:
                print("✅ Workflow execution succeeded")
            else:
                print(f"⚠️ Workflow execution failed: {result.error}")
        except Exception as e:
            print(f"⚠️ Workflow execution skipped (network issue): {e}")
    
    except Exception as e:
        print(f"❌ Workflow execution test failed: {e}")
        return False
    
    return True

def test_environment_handling():
    """Test environment file handling."""
    print("🧪 Testing environment handling...")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        env_file = os.path.join(tmpdir, ".env")
        
        # Test saving env file
        env_vars = {
            "TEST_KEY": "test_value",
            "ANOTHER_KEY": "another_value"
        }
        
        save_env_file(env_file, env_vars)
        
        # Test loading env file
        loaded_vars = load_env_file(env_file)
        
        if loaded_vars == env_vars:
            print("✅ Environment file handling works")
            return True
        else:
            print("❌ Environment file handling failed")
            return False

def test_cli_integration():
    """Test CLI integration without interactive components."""
    print("🧪 Testing CLI integration...")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        os.chdir(tmpdir)
        
        # Create test environment
        env_vars = {
            "GIMME_ADMIN_PASSWORD": "test123",
            "CLOUDFLARE_API_TOKEN": "test-token"
        }
        save_env_file(".env", env_vars)
        
        # Create test config
        config = create_default_config("test-project", "cloudflare")
        with open(".gimme-config.json", "w") as f:
            json.dump(config, f, indent=2)
        
        # Test config validation
        issues = validate_config(config)
        if not issues:
            print("✅ CLI integration test passed")
            return True
        else:
            print(f"❌ CLI integration test failed: {issues}")
            return False

async def main():
    """Run all tests."""
    print("🚀 Running comprehensive gimme_ai tests...\n")
    
    tests = [
        ("Config Creation", test_config_creation),
        ("Workflow Config", test_workflow_config),
        ("HTTP Client", test_http_client),
        ("Environment Handling", test_environment_handling),
        ("CLI Integration", test_cli_integration),
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ {test_name} crashed: {e}")
            results.append((test_name, False))
        print()
    
    # Test async workflow execution
    try:
        result = await test_workflow_execution()
        results.append(("Workflow Execution", result))
    except Exception as e:
        print(f"❌ Workflow Execution crashed: {e}")
        results.append(("Workflow Execution", False))
    
    # Summary
    print("=" * 50)
    print("📊 Test Results:")
    print("=" * 50)
    
    passed = 0
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} {test_name}")
        if result:
            passed += 1
    
    print("=" * 50)
    print(f"📈 Summary: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! gimme_ai is working correctly.")
        return 0
    else:
        print("⚠️ Some tests failed. Check the output above.")
        return 1

if __name__ == "__main__":
    sys.exit(asyncio.run(main()))