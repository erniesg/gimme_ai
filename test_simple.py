#!/usr/bin/env python3
"""
Simple end-to-end test to verify everything works.
"""

import os
import sys
import asyncio
from pathlib import Path
from unittest.mock import Mock, patch

# Add project to path
sys.path.insert(0, str(Path(__file__).parent))

from gimme_ai.config.secrets import get_secrets_manager, SecretBackend
from gimme_ai.config.workflow import WorkflowConfig
from gimme_ai.http.workflow_client import WorkflowHTTPClient
from gimme_ai.workflows.execution_engine import WorkflowExecutionEngine


def create_mock_response(content="Mock response", tokens=10):
    """Create a mock HTTP response."""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.headers = {"Content-Type": "application/json"}
    mock_response.json.return_value = {
        "choices": [{"message": {"content": content}}],
        "usage": {"total_tokens": tokens}
    }
    mock_response.content = b'{"status": "success"}'
    mock_response.raise_for_status.return_value = None
    return mock_response


async def test_complete_workflow():
    """Test complete workflow with mocked APIs."""
    print("🧪 Testing complete workflow...")
    
    # Set environment
    os.environ["GIMME_ENVIRONMENT"] = "development"
    
    # Get secrets manager
    secrets_manager = get_secrets_manager(
        backend=SecretBackend.ENV_FILE,
        environment="development"
    )
    
    # Validate secrets
    report = secrets_manager.validate_secrets()
    if not report["valid"]:
        print("❌ Secrets validation failed!")
        return False
    
    print("✅ Secrets validated")
    
    # Create a simple test workflow
    workflow_config = {
        "name": "test_workflow",
        "api_base": "https://api.openai.com",
        "variables": {"topic": "testing"},
        "steps": [
            {
                "name": "generate_content",
                "endpoint": "/v1/chat/completions",
                "method": "POST",
                "auth": {"type": "bearer", "token": "${OPENAI_API_KEY}"},
                "headers": {"Content-Type": "application/json"},
                "payload_template": """{
                    "model": "gpt-3.5-turbo",
                    "messages": [{"role": "user", "content": "Write about {{ topic }}"}],
                    "max_tokens": 100
                }""",
                "extract_fields": {
                    "content": "choices.0.message.content",
                    "tokens": "usage.total_tokens"
                }
            }
        ]
    }
    
    # Create workflow
    workflow = WorkflowConfig.from_dict(workflow_config)
    resolved_workflow = workflow.resolve_env_vars()
    
    print("✅ Workflow configuration created")
    
    # Mock the HTTP requests
    with patch('requests.Session.request', return_value=create_mock_response("Test content generated", 25)):
        # Create HTTP client and engine
        client = WorkflowHTTPClient(base_url=workflow.api_base)
        engine = WorkflowExecutionEngine(http_client=client)
        
        # Execute workflow
        result = await engine.execute_workflow(resolved_workflow)
        
        if result.success:
            print("✅ Workflow executed successfully")
            
            # Check results
            step_result = result.step_results["generate_content"]
            if step_result.success:
                print(f"✅ Content generated: {step_result.response_data.get('content', 'N/A')}")
                print(f"✅ Tokens used: {step_result.response_data.get('tokens', 'N/A')}")
                return True
            else:
                print(f"❌ Step failed: {step_result.error}")
                return False
        else:
            print(f"❌ Workflow failed: {result.error}")
            return False


async def main():
    """Run the simple test."""
    print("🚀 Running simple end-to-end test...")
    print("=" * 50)
    
    try:
        success = await test_complete_workflow()
        
        print("=" * 50)
        if success:
            print("🎉 All tests passed!")
            print("\n✅ System verified:")
            print("   • Secrets management working")
            print("   • Workflow configuration working")
            print("   • HTTP client working")
            print("   • Execution engine working")
            print("   • Mock testing infrastructure working")
            return 0
        else:
            print("❌ Tests failed!")
            return 1
    
    except Exception as e:
        print(f"❌ Test error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)