#!/usr/bin/env python3
"""
Live API validation test.
Tests gimme_ai workflow patterns with real OpenAI API.
"""

import asyncio
import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from gimme_ai.workflows.execution_engine import WorkflowExecutionEngine
from gimme_ai.http.workflow_client import WorkflowHTTPClient
from gimme_ai.config.workflow import WorkflowConfig, StepConfig, AuthConfig, RetryConfig

async def test_openai_simple_completion():
    """Test simple OpenAI completion."""
    openai_key = os.getenv("OPENAI_API_KEY")
    if not openai_key:
        print("⏭️ Skipping OpenAI test - no API key found")
        return True  # Skip, don't fail
    
    print("🧪 Testing OpenAI simple completion...")
    
    client = WorkflowHTTPClient(base_url="https://api.openai.com")
    engine = WorkflowExecutionEngine(http_client=client)
    
    workflow = WorkflowConfig(
        name="openai_simple_test",
        api_base="https://api.openai.com",
        auth=AuthConfig(type="bearer", token=openai_key),
        steps=[
            StepConfig(
                name="simple_completion",
                endpoint="/v1/chat/completions",
                method="POST",
                headers={"Content-Type": "application/json"},
                payload={
                    "model": "gpt-3.5-turbo",
                    "messages": [
                        {"role": "user", "content": "Say 'Hello from gimme_ai!' and nothing else."}
                    ],
                    "max_tokens": 10
                },
                timeout="30s"
            )
        ]
    )
    
    try:
        result = await engine.execute_workflow(workflow)
        
        if result.success:
            response_content = result.step_results["simple_completion"].response_data.get("choices", [{}])[0].get("message", {}).get("content", "")
            print(f"✅ OpenAI simple completion passed")
            print(f"   Response: '{response_content.strip()}'")
            return True
        else:
            print(f"❌ OpenAI simple completion failed: {result.error}")
            return False
    
    except Exception as e:
        print(f"❌ OpenAI simple completion crashed: {e}")
        return False

async def test_openai_multi_step_workflow():
    """Test multi-step workflow with OpenAI."""
    openai_key = os.getenv("OPENAI_API_KEY")
    if not openai_key:
        print("⏭️ Skipping OpenAI multi-step test - no API key found")
        return True  # Skip, don't fail
    
    print("🧪 Testing OpenAI multi-step workflow...")
    
    client = WorkflowHTTPClient(base_url="https://api.openai.com")
    engine = WorkflowExecutionEngine(http_client=client)
    
    workflow = WorkflowConfig(
        name="openai_multi_step_test",
        api_base="https://api.openai.com",
        auth=AuthConfig(type="bearer", token=openai_key),
        variables={
            "subject": "basic arithmetic",
            "grade": "elementary school"
        },
        steps=[
            # Step 1: Generate a question
            StepConfig(
                name="generate_question",
                endpoint="/v1/chat/completions",
                method="POST",
                headers={"Content-Type": "application/json"},
                payload_template='''
                {
                    "model": "gpt-3.5-turbo",
                    "messages": [
                        {"role": "user", "content": "Create one simple {{ subject }} question for {{ grade }} students. Just the question, no answer."}
                    ],
                    "max_tokens": 50
                }
                ''',
                timeout="30s"
            ),
            # Step 2: Generate answer (depends on question)
            StepConfig(
                name="generate_answer",
                endpoint="/v1/chat/completions",
                method="POST",
                headers={"Content-Type": "application/json"},
                payload_template='''
                {
                    "model": "gpt-3.5-turbo",
                    "messages": [
                        {"role": "user", "content": "Answer this question: {{ generate_question.choices[0].message.content }}"}
                    ],
                    "max_tokens": 30
                }
                ''',
                depends_on=["generate_question"],
                timeout="30s"
            )
        ]
    )
    
    try:
        result = await engine.execute_workflow(workflow)
        
        if result.success:
            question_content = result.step_results["generate_question"].response_data.get("choices", [{}])[0].get("message", {}).get("content", "")
            answer_content = result.step_results["generate_answer"].response_data.get("choices", [{}])[0].get("message", {}).get("content", "")
            
            print(f"✅ OpenAI multi-step workflow passed")
            print(f"   Question: '{question_content.strip()[:50]}...'")
            print(f"   Answer: '{answer_content.strip()[:50]}...'")
            
            # Verify execution order
            question_order = result.step_results["generate_question"].execution_order
            answer_order = result.step_results["generate_answer"].execution_order
            
            if answer_order > question_order:
                print("✅ Execution order correct (answer after question)")
                return True
            else:
                print("❌ Execution order incorrect")
                return False
        else:
            print(f"❌ OpenAI multi-step workflow failed: {result.error}")
            return False
    
    except Exception as e:
        print(f"❌ OpenAI multi-step workflow crashed: {e}")
        return False

async def test_openai_parallel_generation():
    """Test parallel question generation with OpenAI."""
    openai_key = os.getenv("OPENAI_API_KEY")
    if not openai_key:
        print("⏭️ Skipping OpenAI parallel test - no API key found")
        return True  # Skip, don't fail
    
    print("🧪 Testing OpenAI parallel generation...")
    
    client = WorkflowHTTPClient(base_url="https://api.openai.com")
    engine = WorkflowExecutionEngine(http_client=client)
    
    workflow = WorkflowConfig(
        name="openai_parallel_test",
        api_base="https://api.openai.com",
        auth=AuthConfig(type="bearer", token=openai_key),
        steps=[
            # Parallel generation for different topics
            StepConfig(
                name="generate_math_question",
                endpoint="/v1/chat/completions",
                method="POST",
                headers={"Content-Type": "application/json"},
                payload={
                    "model": "gpt-3.5-turbo",
                    "messages": [
                        {"role": "user", "content": "Create a simple math question. Just the question."}
                    ],
                    "max_tokens": 30
                },
                parallel_group="question_generation",
                timeout="30s"
            ),
            StepConfig(
                name="generate_science_question",
                endpoint="/v1/chat/completions",
                method="POST",
                headers={"Content-Type": "application/json"},
                payload={
                    "model": "gpt-3.5-turbo",
                    "messages": [
                        {"role": "user", "content": "Create a simple science question. Just the question."}
                    ],
                    "max_tokens": 30
                },
                parallel_group="question_generation",
                timeout="30s"
            ),
            # Summary step that depends on both
            StepConfig(
                name="create_summary",
                endpoint="/v1/chat/completions",
                method="POST",
                headers={"Content-Type": "application/json"},
                payload_template='''
                {
                    "model": "gpt-3.5-turbo",
                    "messages": [
                        {"role": "user", "content": "List these two questions:\\n1. {{ generate_math_question.choices[0].message.content }}\\n2. {{ generate_science_question.choices[0].message.content }}"}
                    ],
                    "max_tokens": 100
                }
                ''',
                depends_on=["question_generation"],
                timeout="30s"
            )
        ]
    )
    
    try:
        result = await engine.execute_workflow(workflow)
        
        if result.success:
            math_result = result.step_results["generate_math_question"]
            science_result = result.step_results["generate_science_question"]
            summary_result = result.step_results["create_summary"]
            
            print(f"✅ OpenAI parallel generation passed")
            
            # Verify parallel execution order
            if (math_result.execution_order == science_result.execution_order and
                summary_result.execution_order > math_result.execution_order):
                print("✅ Parallel execution order correct")
                return True
            else:
                print("❌ Parallel execution order incorrect")
                return False
        else:
            print(f"❌ OpenAI parallel generation failed: {result.error}")
            return False
    
    except Exception as e:
        print(f"❌ OpenAI parallel generation crashed: {e}")
        return False

async def test_error_handling_with_retry():
    """Test error handling with retry using invalid model."""
    openai_key = os.getenv("OPENAI_API_KEY")
    if not openai_key:
        print("⏭️ Skipping error handling test - no API key found")
        return True  # Skip, don't fail
    
    print("🧪 Testing error handling with retry...")
    
    client = WorkflowHTTPClient(base_url="https://api.openai.com")
    engine = WorkflowExecutionEngine(http_client=client)
    
    workflow = WorkflowConfig(
        name="openai_retry_test",
        api_base="https://api.openai.com",
        auth=AuthConfig(type="bearer", token=openai_key),
        steps=[
            # This should succeed
            StepConfig(
                name="valid_request",
                endpoint="/v1/chat/completions",
                method="POST",
                headers={"Content-Type": "application/json"},
                payload={
                    "model": "gpt-3.5-turbo",
                    "messages": [
                        {"role": "user", "content": "Say 'test' and nothing else."}
                    ],
                    "max_tokens": 5
                },
                timeout="30s"
            ),
            # This should fail but continue
            StepConfig(
                name="invalid_request",
                endpoint="/v1/chat/completions",
                method="POST",
                headers={"Content-Type": "application/json"},
                payload={
                    "model": "nonexistent-model",
                    "messages": [
                        {"role": "user", "content": "This should fail"}
                    ]
                },
                retry=RetryConfig(limit=2, delay="1s", backoff="constant"),
                timeout="30s",
                continue_on_error=True
            )
        ]
    )
    
    try:
        result = await engine.execute_workflow(workflow)
        
        # Workflow should succeed overall due to continue_on_error
        if result.success:
            valid_result = result.step_results["valid_request"]
            invalid_result = result.step_results["invalid_request"]
            
            if valid_result.success and not invalid_result.success:
                print("✅ Error handling with retry passed")
                print(f"   Valid request succeeded, invalid failed as expected")
                print(f"   Invalid request retry count: {invalid_result.retry_count}")
                return True
            else:
                print("❌ Error handling unexpected results")
                return False
        else:
            print(f"❌ Error handling workflow should have succeeded: {result.error}")
            return False
    
    except Exception as e:
        print(f"❌ Error handling test crashed: {e}")
        return False

async def main():
    """Run live API validation tests."""
    print("🚀 Running live API validation tests...\n")
    
    # Check if OpenAI key is available
    has_openai = bool(os.getenv("OPENAI_API_KEY"))
    print(f"🔑 OpenAI API Key: {'✅ Found' if has_openai else '❌ Not found'}")
    
    if not has_openai:
        print("💡 To run live API tests, set OPENAI_API_KEY environment variable")
    
    print()
    
    results = []
    
    # Test 1: Simple completion
    results.append(await test_openai_simple_completion())
    print()
    
    # Test 2: Multi-step workflow
    results.append(await test_openai_multi_step_workflow())
    print()
    
    # Test 3: Parallel generation
    results.append(await test_openai_parallel_generation())
    print()
    
    # Test 4: Error handling
    results.append(await test_error_handling_with_retry())
    print()
    
    # Summary
    passed = sum(results)
    total = len(results)
    
    print("=" * 60)
    print(f"📊 Live API Validation Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All live API validation tests passed!")
        if has_openai:
            print("✅ gimme_ai workflow patterns work correctly with OpenAI API")
            print("✅ Template substitution and data flow verified")
            print("✅ Parallel execution and error handling validated")
        else:
            print("✅ Tests were skipped due to missing API key (not a failure)")
        return 0
    else:
        print("⚠️ Some tests failed.")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)