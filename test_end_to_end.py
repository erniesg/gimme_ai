#!/usr/bin/env python3
"""
End-to-end testing script for gimme_ai with proper secrets management.
Tests the complete workflow from secrets → configuration → execution.
"""

import os
import sys
import asyncio
from pathlib import Path

# Add project to path
sys.path.insert(0, str(Path(__file__).parent))

from gimme_ai.config.secrets import get_secrets_manager, SecretBackend
from gimme_ai.testing.fixtures import WorkflowTestFixture


async def test_secrets_integration():
    """Test secrets management integration."""
    print("🔐 Testing secrets management...")
    
    # Test with development environment
    secrets_manager = get_secrets_manager(
        backend=SecretBackend.ENV_FILE,
        environment="development"
    )
    
    # Validate secrets
    report = secrets_manager.validate_secrets()
    if not report["valid"]:
        print("❌ Secrets validation failed!")
        for secret in report["missing_required"]:
            print(f"  Missing: {secret['name']}")
        return False
    
    print(f"✅ Secrets validated: {len(report['available_secrets'])} available")
    
    # Test secret retrieval
    openai_key = secrets_manager.get_secret("OPENAI_API_KEY")
    if openai_key and openai_key.startswith("sk-"):
        print("✅ OpenAI key format correct")
    else:
        print("❌ OpenAI key format incorrect")
        return False
    
    return True


async def test_workflow_with_secrets():
    """Test workflow execution with secrets."""
    print("\n🔄 Testing workflow execution with secrets...")
    
    try:
        # Set environment for secrets
        os.environ["GIMME_ENVIRONMENT"] = "development"
        
        # Create test fixture that uses real secrets but mock APIs
        fixture = WorkflowTestFixture(
            environment="development",
            use_mock_apis=True,  # Use mocks for API calls
            use_real_secrets=True  # Use real secrets from .env.development
        )
        
        async with fixture.setup():
            print("✅ Test environment set up successfully")
            
            # Create and execute a test workflow
            workflow = fixture.create_test_workflow("minimal")
            print(f"✅ Test workflow created: {workflow.name}")
            
            # Execute workflow
            result = await fixture.execute_workflow(workflow)
            
            if result.success:
                print("✅ Workflow executed successfully")
                
                # Check mock requests were made
                requests = fixture.get_mock_requests()
                if requests:
                    print(f"✅ Mock API calls: {len(requests)} requests logged")
                    for req in requests:
                        print(f"  • {req['method']} {req['endpoint']}")
                else:
                    print("⚠️  No mock requests logged")
                
                return True
            else:
                print(f"❌ Workflow failed: {result.error}")
                return False
    
    except Exception as e:
        print(f"❌ Workflow test error: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_cli_integration():
    """Test CLI commands integration."""
    print("\n🖥️  Testing CLI integration...")
    
    # Test secrets validation via CLI
    import subprocess
    import sys
    
    try:
        result = subprocess.run([
            sys.executable, "-m", "gimme_ai.cli.commands", 
            "secrets", "validate", "--environment", "development", "--quiet"
        ], capture_output=True, text=True, env={**os.environ, "PYTHONPATH": str(Path(__file__).parent)})
        
        if result.returncode == 0:
            print("✅ CLI secrets validation successful")
        else:
            print(f"❌ CLI secrets validation failed: {result.stderr}")
            return False
    
    except Exception as e:
        print(f"❌ CLI test error: {e}")
        return False
    
    return True


async def test_workflow_validation():
    """Test workflow configuration validation."""
    print("\n📋 Testing workflow validation...")
    
    try:
        # Test existing workflow file
        workflow_file = "test_multi_api_r2.yaml"
        if os.path.exists(workflow_file):
            import subprocess
            
            result = subprocess.run([
                sys.executable, "-m", "gimme_ai.cli.commands",
                "wf", "validate", workflow_file
            ], capture_output=True, text=True, env={**os.environ, "PYTHONPATH": str(Path(__file__).parent)})
            
            if result.returncode == 0:
                print("✅ Workflow validation successful")
                print(f"   Output: {result.stdout.strip()}")
            else:
                print(f"❌ Workflow validation failed: {result.stderr}")
                return False
        else:
            print("⚠️  Workflow file not found, skipping validation test")
    
    except Exception as e:
        print(f"❌ Workflow validation error: {e}")
        return False
    
    return True


async def main():
    """Run all end-to-end tests."""
    print("🚀 Running gimme_ai end-to-end tests...")
    print("=" * 60)
    
    tests = [
        ("Secrets Integration", test_secrets_integration),
        ("Workflow with Secrets", test_workflow_with_secrets),
        ("CLI Integration", test_cli_integration),
        ("Workflow Validation", test_workflow_validation)
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            success = await test_func()
            results.append((test_name, success))
        except Exception as e:
            print(f"❌ {test_name} crashed: {e}")
            results.append((test_name, False))
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 End-to-End Test Results:")
    print("=" * 60)
    
    passed = 0
    total = len(results)
    
    for test_name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} {test_name}")
        if success:
            passed += 1
    
    print("=" * 60)
    print(f"📈 Summary: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All end-to-end tests passed!")
        print("\n✅ gimme_ai is working correctly with:")
        print("   • Secrets management (.env files)")
        print("   • Workflow configuration and validation") 
        print("   • CLI command integration")
        print("   • Mock API testing infrastructure")
        return 0
    else:
        print("⚠️ Some tests failed. Check the output above.")
        return 1


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n⚠️ Tests interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)