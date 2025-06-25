#!/usr/bin/env python3
"""
Setup script for multi-API R2 testing.
Guides user through environment setup and runs the complete pipeline.
"""

import os
import sys
import asyncio
import yaml
from pathlib import Path

# Add project to path
sys.path.insert(0, str(Path(__file__).parent))

from gimme_ai.config.workflow import WorkflowConfig
from gimme_ai.http.workflow_client import WorkflowHTTPClient
from gimme_ai.workflows.execution_engine import WorkflowExecutionEngine

def check_environment(minimal=False):
    """Check if required environment variables are set."""
    print("🔍 Checking environment setup...")
    
    if minimal:
        required_vars = {
            "OPENAI_API_KEY": "OpenAI API key for content generation",
        }
        optional_vars = {
            "REPLICATE_API_TOKEN": "Replicate token for image generation", 
            "ELEVENLABS_API_KEY": "ElevenLabs key for voice synthesis",
            "CLOUDFLARE_ACCOUNT_ID": "Cloudflare account ID for R2 storage",
            "R2_ACCESS_KEY_ID": "R2 access key for file storage",
            "R2_SECRET_ACCESS_KEY": "R2 secret key for file storage"
        }
    else:
        required_vars = {
            "OPENAI_API_KEY": "OpenAI API key for content generation",
            "REPLICATE_API_TOKEN": "Replicate token for image generation", 
            "ELEVENLABS_API_KEY": "ElevenLabs key for voice synthesis",
        }
        optional_vars = {
            "CLOUDFLARE_ACCOUNT_ID": "Cloudflare account ID for R2 storage",
            "R2_ACCESS_KEY_ID": "R2 access key for file storage",
            "R2_SECRET_ACCESS_KEY": "R2 secret key for file storage"
        }
    
    missing_required = []
    missing_optional = []
    
    for var, description in required_vars.items():
        if not os.getenv(var):
            missing_required.append(f"  ❌ {var}: {description}")
        else:
            print(f"  ✅ {var}: Found")
    
    for var, description in optional_vars.items():
        if not os.getenv(var):
            missing_optional.append(f"  ⚠️  {var}: {description}")
        else:
            print(f"  ✅ {var}: Found")
    
    if missing_required:
        print("\n❌ Missing required environment variables:")
        for var in missing_required:
            print(var)
        print("\nPlease set these variables and try again.")
        return False
    
    if missing_optional:
        print("\n⚠️ Missing optional R2 storage variables:")
        for var in missing_optional:
            print(var)
        print("\nR2 storage will use mock URLs. Set these for real file storage.")
    
    print("\n✅ Environment check complete!")
    return True

def show_setup_instructions():
    """Show setup instructions for missing environment variables."""
    print("""
🚀 Multi-API R2 Workflow Test Setup

To run the complete test with all features, you'll need API keys from:

1. OpenAI (Required)
   - Get API key: https://platform.openai.com/api-keys
   - Set: export OPENAI_API_KEY="sk-..."

2. Replicate (Required for image generation)
   - Get token: https://replicate.com/account/api-tokens
   - Set: export REPLICATE_API_TOKEN="r8_..."

3. ElevenLabs (Required for voice synthesis)
   - Get API key: https://elevenlabs.io/speech-synthesis
   - Set: export ELEVENLABS_API_KEY="..."

4. Cloudflare R2 (Optional - for real file storage)
   - Create R2 bucket in Cloudflare dashboard
   - Generate API tokens with R2 permissions
   - Set: export CLOUDFLARE_ACCOUNT_ID="..."
   - Set: export R2_ACCESS_KEY_ID="..."  
   - Set: export R2_SECRET_ACCESS_KEY="..."

Without R2 credentials, files will use mock URLs but the workflow will still run.

To test with just OpenAI (minimal setup):
  export OPENAI_API_KEY="sk-..."
  python setup_r2_test.py --minimal

To test the full pipeline:
  # Set all environment variables above
  python setup_r2_test.py --full
""")

async def run_minimal_test():
    """Run a minimal test with just OpenAI API."""
    print("🧪 Running minimal test (OpenAI only)...")
    
    minimal_config = {
        "name": "minimal_test",
        "api_base": "https://api.openai.com",
        "variables": {"topic": "sustainable living"},
        "steps": [
            {
                "name": "generate_content",
                "endpoint": "/v1/chat/completions",
                "method": "POST",
                "auth": {"type": "bearer", "token": "${OPENAI_API_KEY}"},
                "headers": {"Content-Type": "application/json"},
                "payload_template": """{
                    "model": "gpt-3.5-turbo",
                    "messages": [{"role": "user", "content": "Write a 50-word summary about {{ topic }}."}],
                    "max_tokens": 100
                }""",
                "extract_fields": {
                    "content": "choices.0.message.content",
                    "tokens": "usage.total_tokens"
                }
            }
        ]
    }
    
    try:
        workflow = WorkflowConfig.from_dict(minimal_config)
        resolved_workflow = workflow.resolve_env_vars()
        
        client = WorkflowHTTPClient(base_url=workflow.api_base)
        engine = WorkflowExecutionEngine(http_client=client)
        
        result = await engine.execute_workflow(resolved_workflow)
        
        if result.success:
            content = result.step_results["generate_content"].response_data
            print(f"✅ Minimal test successful!")
            print(f"📝 Generated content: {content.get('content', 'N/A')}")
            print(f"🔢 Tokens used: {content.get('tokens', 'N/A')}")
            return True
        else:
            print(f"❌ Minimal test failed: {result.error}")
            return False
            
    except Exception as e:
        print(f"❌ Minimal test error: {e}")
        return False

async def run_full_test():
    """Run the complete multi-API R2 workflow test."""
    print("🚀 Running full multi-API R2 test...")
    
    # Load the complete workflow
    workflow_file = "test_multi_api_r2.yaml"
    if not os.path.exists(workflow_file):
        print(f"❌ Workflow file not found: {workflow_file}")
        return False
    
    try:
        with open(workflow_file) as f:
            workflow_data = yaml.safe_load(f)
        
        workflow = WorkflowConfig.from_dict(workflow_data)
        resolved_workflow = workflow.resolve_env_vars()
        
        client = WorkflowHTTPClient(base_url=workflow.api_base)
        engine = WorkflowExecutionEngine(http_client=client)
        
        print("📋 Workflow execution plan:")
        phases = engine._resolve_dependencies(workflow.steps)
        for i, phase in enumerate(phases, 1):
            print(f"  Phase {i}: {[step.name for step in phase]}")
        
        print(f"\n🚀 Starting execution...")
        result = await engine.execute_workflow(resolved_workflow)
        
        print("\n" + "="*60)
        if result.success:
            print("🎉 Full workflow test completed successfully!")
            print(f"⏱️  Total execution time: {result.total_execution_time:.1f}s")
            print(f"📊 Steps completed: {len(result.step_results)}")
            
            # Show key results
            if "create_content_package" in result.step_results:
                final_result = result.step_results["create_content_package"].response_data
                if isinstance(final_result, dict) and "assets" in final_result:
                    print(f"\n📁 Generated assets:")
                    for asset_name, asset_url in final_result["assets"].items():
                        print(f"  • {asset_name}: {asset_url}")
                        
            return True
        else:
            print(f"❌ Full workflow test failed: {result.error}")
            print(f"\n📋 Step results:")
            for step_name, step_result in result.step_results.items():
                status = "✅" if step_result.success else "❌"
                print(f"  {status} {step_name}")
                if not step_result.success:
                    print(f"    Error: {step_result.error}")
            return False
            
    except Exception as e:
        print(f"❌ Full test error: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    """Main test runner."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Multi-API R2 Workflow Test")
    parser.add_argument("--minimal", action="store_true", help="Run minimal OpenAI-only test")
    parser.add_argument("--full", action="store_true", help="Run full multi-API R2 test")
    parser.add_argument("--setup", action="store_true", help="Show setup instructions")
    
    args = parser.parse_args()
    
    if args.setup or (not args.minimal and not args.full):
        show_setup_instructions()
        return 0
    
    if args.minimal:
        if not check_environment(minimal=True):
            return 1
        success = await run_minimal_test()
    elif args.full:
        if not check_environment(minimal=False):
            return 1
        success = await run_full_test()
    else:
        print("Please specify --minimal or --full")
        return 1
        
    return 0 if success else 1

if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n⚠️ Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        sys.exit(1)