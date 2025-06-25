#!/usr/bin/env python3
"""
Simple validation test to debug issues.
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from gimme_ai.workflows.execution_engine import WorkflowExecutionEngine
from gimme_ai.http.workflow_client import WorkflowHTTPClient
from gimme_ai.config.workflow import WorkflowConfig, StepConfig

async def test_simple_workflow():
    """Test the most basic workflow."""
    print("🧪 Testing simple workflow...")
    
    # Test with httpbin.org which should be reliable
    client = WorkflowHTTPClient(base_url="https://httpbin.org")
    engine = WorkflowExecutionEngine(http_client=client)
    
    workflow = WorkflowConfig(
        name="simple_test",
        api_base="https://httpbin.org",
        steps=[
            StepConfig(
                name="get_data",
                endpoint="/json",
                method="GET"
            )
        ]
    )
    
    try:
        result = await engine.execute_workflow(workflow)
        
        if result.success:
            print("✅ Simple workflow passed")
            print(f"   Step result: {result.step_results['get_data'].response_data}")
            print(f"   Execution order: {result.step_results['get_data'].execution_order}")
            return True
        else:
            print(f"❌ Simple workflow failed: {result.error}")
            return False
    
    except Exception as e:
        print(f"❌ Simple workflow crashed: {e}")
        return False

async def test_parallel_workflow():
    """Test parallel execution."""
    print("🧪 Testing parallel workflow...")
    
    client = WorkflowHTTPClient(base_url="https://httpbin.org")
    engine = WorkflowExecutionEngine(http_client=client)
    
    workflow = WorkflowConfig(
        name="parallel_test",
        api_base="https://httpbin.org",
        steps=[
            StepConfig(
                name="parallel1",
                endpoint="/json",
                method="GET",
                parallel_group="group1"
            ),
            StepConfig(
                name="parallel2", 
                endpoint="/json",
                method="GET",
                parallel_group="group1"
            ),
            StepConfig(
                name="after_parallel",
                endpoint="/json",
                method="GET",
                depends_on=["group1"]
            )
        ]
    )
    
    try:
        result = await engine.execute_workflow(workflow)
        
        if result.success:
            parallel1 = result.step_results['parallel1']
            parallel2 = result.step_results['parallel2']
            after = result.step_results['after_parallel']
            
            print("✅ Parallel workflow passed")
            print(f"   Parallel1 order: {parallel1.execution_order}")
            print(f"   Parallel2 order: {parallel2.execution_order}")
            print(f"   After order: {after.execution_order}")
            
            # Verify parallel steps have same order, after step has higher order
            if parallel1.execution_order == parallel2.execution_order and after.execution_order > parallel1.execution_order:
                print("✅ Execution order is correct")
                return True
            else:
                print("❌ Execution order is incorrect")
                return False
        else:
            print(f"❌ Parallel workflow failed: {result.error}")
            return False
    
    except Exception as e:
        print(f"❌ Parallel workflow crashed: {e}")
        return False

async def main():
    """Run simple validation tests."""
    print("🚀 Running simple validation tests...\n")
    
    results = []
    
    # Test 1: Simple workflow
    results.append(await test_simple_workflow())
    print()
    
    # Test 2: Parallel workflow
    results.append(await test_parallel_workflow())
    print()
    
    # Summary
    passed = sum(results)
    total = len(results)
    
    print("=" * 50)
    print(f"📊 Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All simple validation tests passed!")
        return 0
    else:
        print("⚠️ Some tests failed.")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)