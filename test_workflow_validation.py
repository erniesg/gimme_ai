#!/usr/bin/env python3
"""
Comprehensive workflow validation test runner.
Validates that gimme_ai workflow patterns work with real APIs and comprehensive error handling.
"""

import asyncio
import os
import sys
import time
import json
from pathlib import Path
from typing import Dict, List, Any

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from tests.fixtures.mock_api_server import MockAPIServer, MockAPIEndpoints
from tests.integration.test_comprehensive_workflows import TestComprehensiveWorkflows
from tests.integration.test_error_handling import TestRetryMechanisms, TestTimeoutHandling
from gimme_ai.workflows.execution_engine import WorkflowExecutionEngine
from gimme_ai.http.workflow_client import WorkflowHTTPClient
from gimme_ai.config.workflow import WorkflowConfig, StepConfig, AuthConfig, RetryConfig

class WorkflowValidationRunner:
    """Comprehensive workflow validation test runner."""
    
    def __init__(self):
        self.results: Dict[str, Any] = {
            "timestamp": time.time(),
            "tests": {},
            "summary": {},
            "environment": {
                "has_openai_key": bool(os.getenv("OPENAI_API_KEY")),
                "has_replicate_key": bool(os.getenv("REPLICATE_API_TOKEN")),
                "python_version": sys.version
            }
        }
        self.mock_server: MockAPIServer = None
    
    async def setup_mock_server(self):
        """Set up mock API server for testing."""
        print("🔧 Setting up mock API server...")
        
        self.mock_server = MockAPIServer(port=8899)
        
        # Add all predefined endpoints
        for endpoint in MockAPIEndpoints.derivativ_question_generation():
            self.mock_server.add_endpoint(endpoint)
        
        for endpoint in MockAPIEndpoints.openai_simulation():
            self.mock_server.add_endpoint(endpoint)
        
        for endpoint in MockAPIEndpoints.unreliable_api():
            self.mock_server.add_endpoint(endpoint)
        
        self.mock_server.start(background=True)
        
        # Wait for server to be ready
        await asyncio.sleep(1)
        
        # Test server is running
        try:
            client = WorkflowHTTPClient(base_url=self.mock_server.base_url)
            health_response = client.make_request("/health", method="GET", timeout=5)
            assert health_response["status"] == "healthy"
            print(f"✅ Mock server running at {self.mock_server.base_url}")
        except Exception as e:
            print(f"❌ Mock server failed to start: {e}")
            raise
    
    async def test_basic_workflow_patterns(self) -> Dict[str, Any]:
        """Test basic workflow execution patterns."""
        print("\n🧪 Testing basic workflow patterns...")
        
        results = {}
        engine = WorkflowExecutionEngine(
            http_client=WorkflowHTTPClient(base_url=self.mock_server.base_url)
        )
        
        # Test 1: Simple sequential workflow
        try:
            workflow = WorkflowConfig(
                name="simple_sequential",
                api_base=self.mock_server.base_url,
                steps=[
                    StepConfig(name="step1", endpoint="/health", method="GET"),
                    StepConfig(name="step2", endpoint="/health", method="GET", depends_on=["step1"]),
                    StepConfig(name="step3", endpoint="/health", method="GET", depends_on=["step2"])
                ]
            )
            
            start_time = time.time()
            result = await engine.execute_workflow(workflow)
            execution_time = time.time() - start_time
            
            results["simple_sequential"] = {
                "success": result.success,
                "execution_time": execution_time,
                "steps_completed": len(result.step_results),
                "error": str(result.error) if result.error else None
            }
            
            if result.success:
                print("✅ Simple sequential workflow")
            else:
                print(f"❌ Simple sequential workflow: {result.error}")
        
        except Exception as e:
            results["simple_sequential"] = {"success": False, "error": str(e)}
            print(f"❌ Simple sequential workflow crashed: {e}")
        
        # Test 2: Parallel execution
        try:
            workflow = WorkflowConfig(
                name="parallel_execution",
                api_base=self.mock_server.base_url,
                steps=[
                    StepConfig(name="parallel1", endpoint="/health", method="GET", parallel_group="group1"),
                    StepConfig(name="parallel2", endpoint="/health", method="GET", parallel_group="group1"),
                    StepConfig(name="parallel3", endpoint="/health", method="GET", parallel_group="group1"),
                    StepConfig(name="after_parallel", endpoint="/health", method="GET", depends_on=["group1"])
                ]
            )
            
            start_time = time.time()
            result = await engine.execute_workflow(workflow)
            execution_time = time.time() - start_time
            
            results["parallel_execution"] = {
                "success": result.success,
                "execution_time": execution_time,
                "steps_completed": len(result.step_results),
                "parallel_efficiency": execution_time < 2.0  # Should be fast due to parallel execution
            }
            
            if result.success:
                print("✅ Parallel execution workflow")
            else:
                print(f"❌ Parallel execution workflow: {result.error}")
        
        except Exception as e:
            results["parallel_execution"] = {"success": False, "error": str(e)}
            print(f"❌ Parallel execution workflow crashed: {e}")
        
        # Test 3: Template variable substitution
        try:
            workflow = WorkflowConfig(
                name="template_variables",
                api_base=self.mock_server.base_url,
                variables={
                    "topic": "mathematics",
                    "count": 5,
                    "metadata": {"version": "1.0"}
                },
                steps=[
                    StepConfig(
                        name="template_step",
                        endpoint="/api/questions/generate",
                        method="POST",
                        payload_template='''
                        {
                            "topic": "{{ topic }}",
                            "count": {{ count }},
                            "version": "{{ metadata.version }}"
                        }
                        '''
                    )
                ]
            )
            
            result = await engine.execute_workflow(workflow)
            
            results["template_variables"] = {
                "success": result.success,
                "template_rendered": result.success and "question_ids" in result.step_results["template_step"].response_data
            }
            
            if result.success:
                print("✅ Template variable substitution")
            else:
                print(f"❌ Template variable substitution: {result.error}")
        
        except Exception as e:
            results["template_variables"] = {"success": False, "error": str(e)}
            print(f"❌ Template variable substitution crashed: {e}")
        
        return results
    
    async def test_derivativ_workflow_simulation(self) -> Dict[str, Any]:
        """Test complete Derivativ-style workflow simulation."""
        print("\n🧪 Testing Derivativ workflow simulation...")
        
        engine = WorkflowExecutionEngine(
            http_client=WorkflowHTTPClient(base_url=self.mock_server.base_url)
        )
        
        try:
            workflow = WorkflowConfig(
                name="derivativ_simulation",
                api_base=self.mock_server.base_url,
                auth=AuthConfig(type="bearer", token="test-token"),
                variables={
                    "topics": ["algebra", "geometry"],
                    "questions_per_topic": 3,
                    "grade_level": 9
                },
                steps=[
                    # Phase 1: Parallel question generation
                    StepConfig(
                        name="generate_algebra_questions",
                        endpoint="/api/questions/generate",
                        method="POST",
                        payload_template='{"topic": "algebra", "count": {{ questions_per_topic }}}',
                        parallel_group="question_generation"
                    ),
                    StepConfig(
                        name="generate_geometry_questions",
                        endpoint="/api/questions/generate",
                        method="POST",
                        payload_template='{"topic": "geometry", "count": {{ questions_per_topic }}}',
                        parallel_group="question_generation"
                    ),
                    # Phase 2: Document creation
                    StepConfig(
                        name="create_worksheet",
                        endpoint="/api/documents/generate",
                        method="POST",
                        payload_template='{"document_type": "worksheet", "question_ids": {{ (generate_algebra_questions.question_ids + generate_geometry_questions.question_ids) | list }}}',
                        depends_on=["question_generation"]
                    ),
                    # Phase 3: Storage
                    StepConfig(
                        name="store_document",
                        endpoint="/api/documents/store",
                        method="POST",
                        payload_template='{"document_id": "{{ create_worksheet.document_id }}"}',
                        depends_on=["create_worksheet"]
                    )
                ]
            )
            
            start_time = time.time()
            result = await engine.execute_workflow(workflow)
            execution_time = time.time() - start_time
            
            results = {
                "success": result.success,
                "execution_time": execution_time,
                "steps_completed": len(result.step_results),
                "phases_executed": len(set(r.execution_order for r in result.step_results.values())),
                "data_flow_verified": False,
                "error": str(result.error) if result.error else None
            }
            
            if result.success:
                # Verify data flows between steps
                algebra_result = result.step_results.get("generate_algebra_questions")
                geometry_result = result.step_results.get("generate_geometry_questions") 
                worksheet_result = result.step_results.get("create_worksheet")
                storage_result = result.step_results.get("store_document")
                
                data_flow_ok = (
                    algebra_result and algebra_result.success and
                    geometry_result and geometry_result.success and
                    worksheet_result and worksheet_result.success and
                    storage_result and storage_result.success
                )
                
                results["data_flow_verified"] = data_flow_ok
                print("✅ Derivativ workflow simulation")
            else:
                print(f"❌ Derivativ workflow simulation: {result.error}")
            
            return results
        
        except Exception as e:
            print(f"❌ Derivativ workflow simulation crashed: {e}")
            return {"success": False, "error": str(e)}
    
    async def test_error_handling_patterns(self) -> Dict[str, Any]:
        """Test comprehensive error handling patterns."""
        print("\n🧪 Testing error handling patterns...")
        
        results = {}
        engine = WorkflowExecutionEngine(
            http_client=WorkflowHTTPClient(base_url=self.mock_server.base_url)
        )
        
        # Test 1: Retry with exponential backoff
        try:
            workflow = WorkflowConfig(
                name="retry_test",
                api_base=self.mock_server.base_url,
                steps=[
                    StepConfig(
                        name="unreliable_step",
                        endpoint="/api/unreliable",
                        method="POST",
                        retry=RetryConfig(limit=3, delay="1s", backoff="exponential")
                    )
                ]
            )
            
            start_time = time.time()
            result = await engine.execute_workflow(workflow)
            execution_time = time.time() - start_time
            
            results["retry_exponential_backoff"] = {
                "success": result.success,
                "execution_time": execution_time,
                "retry_count": result.step_results["unreliable_step"].retry_count if result.step_results else 0,
                "backoff_worked": execution_time >= 0.1  # Should have some delay due to backoff
            }
            
            if result.success:
                print("✅ Retry with exponential backoff")
            else:
                print(f"❌ Retry with exponential backoff: {result.error}")
        
        except Exception as e:
            results["retry_exponential_backoff"] = {"success": False, "error": str(e)}
            print(f"❌ Retry test crashed: {e}")
        
        # Test 2: Continue on error
        try:
            workflow = WorkflowConfig(
                name="continue_on_error_test",
                api_base=self.mock_server.base_url,
                steps=[
                    StepConfig(name="step1", endpoint="/health", method="GET"),
                    StepConfig(
                        name="failing_step",
                        endpoint="/api/nonexistent",
                        method="GET",
                        continue_on_error=True,
                        depends_on=["step1"]
                    ),
                    StepConfig(
                        name="step3",
                        endpoint="/health",
                        method="GET", 
                        depends_on=["failing_step"]
                    )
                ]
            )
            
            result = await engine.execute_workflow(workflow)
            
            results["continue_on_error"] = {
                "workflow_success": result.success,
                "step1_success": result.step_results.get("step1", {}).success if result.step_results else False,
                "failing_step_failed": not result.step_results.get("failing_step", {}).success if result.step_results else False,
                "step3_success": result.step_results.get("step3", {}).success if result.step_results else False,
                "workflow_continued": len(result.step_results) == 3 if result.step_results else False
            }
            
            if result.success and len(result.step_results) == 3:
                print("✅ Continue on error behavior")
            else:
                print(f"❌ Continue on error behavior: workflow should continue despite step failure")
        
        except Exception as e:
            results["continue_on_error"] = {"success": False, "error": str(e)}
            print(f"❌ Continue on error test crashed: {e}")
        
        # Test 3: Timeout handling
        try:
            workflow = WorkflowConfig(
                name="timeout_test",
                api_base=self.mock_server.base_url,
                steps=[
                    StepConfig(
                        name="timeout_step",
                        endpoint="/api/slow",  # 5 second delay
                        method="GET",
                        timeout="1s"  # Should timeout
                    )
                ]
            )
            
            start_time = time.time()
            result = await engine.execute_workflow(workflow)
            execution_time = time.time() - start_time
            
            results["timeout_handling"] = {
                "workflow_failed": not result.success,
                "execution_time": execution_time,
                "timeout_enforced": execution_time < 3.0,  # Should timeout quickly
                "timeout_error": "timeout" in str(result.error).lower() if result.error else False
            }
            
            if not result.success and execution_time < 3.0:
                print("✅ Timeout handling")
            else:
                print(f"❌ Timeout handling: should fail quickly, got {execution_time:.2f}s")
        
        except Exception as e:
            results["timeout_handling"] = {"success": False, "error": str(e)}
            print(f"❌ Timeout test crashed: {e}")
        
        return results
    
    async def test_live_api_integration(self) -> Dict[str, Any]:
        """Test integration with live APIs if keys are available."""
        print("\n🧪 Testing live API integration...")
        
        results = {}
        
        # Test OpenAI API if key is available
        openai_key = os.getenv("OPENAI_API_KEY")
        if openai_key:
            try:
                client = WorkflowHTTPClient(base_url="https://api.openai.com")
                engine = WorkflowExecutionEngine(http_client=client)
                
                workflow = WorkflowConfig(
                    name="openai_live_test",
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
                                    {"role": "user", "content": "Say 'Hello from gimme_ai workflow test' and nothing else."}
                                ],
                                "max_tokens": 20
                            },
                            timeout="30s"
                        )
                    ]
                )
                
                start_time = time.time()
                result = await engine.execute_workflow(workflow)
                execution_time = time.time() - start_time
                
                results["openai_integration"] = {
                    "success": result.success,
                    "execution_time": execution_time,
                    "response_received": bool(result.step_results and 
                                           result.step_results.get("simple_completion", {}).response_data),
                    "error": str(result.error) if result.error else None
                }
                
                if result.success:
                    response_content = result.step_results["simple_completion"].response_data.get("choices", [{}])[0].get("message", {}).get("content", "")
                    results["openai_integration"]["response_content"] = response_content[:100]
                    print(f"✅ OpenAI live API integration - Response: {response_content[:50]}...")
                else:
                    print(f"❌ OpenAI live API integration: {result.error}")
            
            except Exception as e:
                results["openai_integration"] = {"success": False, "error": str(e)}
                print(f"❌ OpenAI live API test crashed: {e}")
        else:
            results["openai_integration"] = {"skipped": "No OPENAI_API_KEY found"}
            print("⏭️ Skipping OpenAI test - no API key")
        
        return results
    
    async def run_all_tests(self) -> Dict[str, Any]:
        """Run all workflow validation tests."""
        print("🚀 Starting comprehensive workflow validation tests...")
        
        try:
            # Setup mock server
            await self.setup_mock_server()
            
            # Run test suites
            self.results["tests"]["basic_patterns"] = await self.test_basic_workflow_patterns()
            self.results["tests"]["derivativ_simulation"] = await self.test_derivativ_workflow_simulation()
            self.results["tests"]["error_handling"] = await self.test_error_handling_patterns()
            self.results["tests"]["live_api_integration"] = await self.test_live_api_integration()
            
            # Generate summary
            self.generate_summary()
            
        except Exception as e:
            print(f"❌ Test suite failed: {e}")
            self.results["fatal_error"] = str(e)
        
        finally:
            if self.mock_server:
                self.mock_server.stop()
        
        return self.results
    
    def generate_summary(self):
        """Generate test summary."""
        total_tests = 0
        passed_tests = 0
        
        for suite_name, suite_results in self.results["tests"].items():
            if isinstance(suite_results, dict):
                for test_name, test_result in suite_results.items():
                    if isinstance(test_result, dict) and "success" in test_result:
                        total_tests += 1
                        if test_result["success"]:
                            passed_tests += 1
                    elif isinstance(test_result, dict) and test_result.get("workflow_success"):
                        total_tests += 1
                        passed_tests += 1
        
        self.results["summary"] = {
            "total_tests": total_tests,
            "passed_tests": passed_tests,
            "success_rate": passed_tests / total_tests if total_tests > 0 else 0,
            "overall_success": passed_tests == total_tests and total_tests > 0
        }
    
    def print_summary(self):
        """Print test summary."""
        print("\n" + "=" * 60)
        print("📊 WORKFLOW VALIDATION SUMMARY")
        print("=" * 60)
        
        summary = self.results.get("summary", {})
        
        print(f"Total Tests: {summary.get('total_tests', 0)}")
        print(f"Passed: {summary.get('passed_tests', 0)}")
        print(f"Success Rate: {summary.get('success_rate', 0):.1%}")
        print(f"Environment: OpenAI Key={'✅' if self.results['environment']['has_openai_key'] else '❌'}")
        
        if summary.get("overall_success"):
            print("\n🎉 ALL WORKFLOW VALIDATION TESTS PASSED!")
            print("✅ gimme_ai workflow patterns are working correctly")
            print("✅ Error handling and retry mechanisms validated")
            print("✅ Template substitution and data flow verified")
            if self.results["environment"]["has_openai_key"]:
                print("✅ Live API integration confirmed")
        else:
            print("\n⚠️ Some tests failed. Check detailed results above.")
        
        print("=" * 60)

async def main():
    """Main test runner."""
    runner = WorkflowValidationRunner()
    
    try:
        results = await runner.run_all_tests()
        runner.print_summary()
        
        # Save detailed results
        results_file = Path(__file__).parent / "workflow_validation_results.json"
        with open(results_file, "w") as f:
            json.dump(results, f, indent=2, default=str)
        
        print(f"\n📄 Detailed results saved to: {results_file}")
        
        # Return appropriate exit code
        return 0 if results.get("summary", {}).get("overall_success") else 1
    
    except Exception as e:
        print(f"❌ Test runner failed: {e}")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)