"""Enhanced workflow commands for gimme_ai CLI with new workflow engine."""

import os
import sys
import json
import yaml
import asyncio
import click
import logging
from pathlib import Path
from typing import Optional, Dict, Any

from ..config.workflow import WorkflowConfig, validate_workflow_config
from ..http.workflow_client import WorkflowHTTPClient
from ..workflows.execution_engine import WorkflowExecutionEngine
from ..utils.environment import load_env_file

logger = logging.getLogger(__name__)


@click.group(name="workflow")
def workflow_group():
    """Manage workflows with the new workflow engine."""
    pass


@workflow_group.command(name="init")
@click.option(
    "--name",
    help="Workflow name",
    required=True
)
@click.option(
    "--template",
    type=click.Choice(["content-creation", "api-orchestration", "data-pipeline", "custom"]),
    default="content-creation",
    help="Workflow template to use"
)
@click.option(
    "--output",
    default="workflow.yaml",
    help="Output file for workflow configuration"
)
def init_workflow(name: str, template: str, output: str):
    """Initialize a new workflow configuration."""
    
    try:
        click.echo(f"🚀 Creating workflow: {name}")
        click.echo(f"📋 Template: {template}")
        
        # Generate workflow based on template
        workflow_config = generate_workflow_template(name, template)
        
        # Save to YAML file
        with open(output, 'w') as f:
            yaml.dump(workflow_config, f, default_flow_style=False, indent=2)
        
        click.echo(f"✅ Created workflow configuration: {output}")
        click.echo(f"\n📝 Next steps:")
        click.echo(f"   1. Edit {output} to customize your workflow")
        click.echo(f"   2. Set required environment variables")
        click.echo(f"   3. Run: gimme-ai workflow validate {output}")
        click.echo(f"   4. Run: gimme-ai workflow execute {output}")
        
    except Exception as e:
        click.echo(f"❌ Error creating workflow: {e}", err=True)
        sys.exit(1)


@workflow_group.command(name="validate")
@click.argument("workflow_file", type=click.Path(exists=True))
def validate_workflow(workflow_file: str):
    """Validate a workflow configuration file."""
    
    try:
        click.echo(f"🔍 Validating workflow: {workflow_file}")
        
        # Load and parse workflow
        with open(workflow_file) as f:
            workflow_data = yaml.safe_load(f)
        
        # Validate configuration
        issues = validate_workflow_config(workflow_data)
        
        if issues:
            click.echo("❌ Validation failed:")
            for issue in issues:
                click.echo(f"   • {issue}")
            sys.exit(1)
        else:
            # Try to create workflow object
            workflow = WorkflowConfig.from_dict(workflow_data)
            
            click.echo("✅ Workflow validation passed!")
            click.echo(f"   📛 Name: {workflow.name}")
            click.echo(f"   🌐 API Base: {workflow.api_base}")
            click.echo(f"   📋 Steps: {len(workflow.steps)}")
            
            if workflow.auth:
                click.echo(f"   🔐 Auth: {workflow.auth.type}")
            
            if workflow.schedule:
                click.echo(f"   ⏰ Schedule: {workflow.schedule}")
        
    except Exception as e:
        click.echo(f"❌ Validation error: {e}", err=True)
        sys.exit(1)


@workflow_group.command(name="execute")
@click.argument("workflow_file", type=click.Path(exists=True))
@click.option(
    "--env-file",
    default=".env",
    help="Environment file with API keys"
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Validate and show execution plan without running"
)
@click.option(
    "--verbose", "-v",
    is_flag=True,
    help="Show detailed execution output"
)
def execute_workflow(workflow_file: str, env_file: str, dry_run: bool, verbose: bool):
    """Execute a workflow configuration."""
    
    try:
        # Set up logging
        if verbose:
            logging.basicConfig(level=logging.DEBUG)
        else:
            logging.basicConfig(level=logging.INFO)
        
        click.echo(f"🚀 Executing workflow: {workflow_file}")
        
        # Load environment variables
        if os.path.exists(env_file):
            env_vars = load_env_file(env_file)
            for key, value in env_vars.items():
                os.environ[key] = value
            click.echo(f"📋 Loaded environment from: {env_file}")
        
        # Load and parse workflow
        with open(workflow_file) as f:
            workflow_data = yaml.safe_load(f)
        
        workflow = WorkflowConfig.from_dict(workflow_data)
        
        # Resolve environment variables
        resolved_workflow = workflow.resolve_env_vars()
        
        if dry_run:
            click.echo("🔍 Dry run - showing execution plan:")
            show_execution_plan(resolved_workflow)
            return
        
        # Execute workflow
        asyncio.run(run_workflow_execution(resolved_workflow, verbose))
        
    except Exception as e:
        click.echo(f"❌ Execution error: {e}", err=True)
        if verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


@workflow_group.command(name="test")
@click.option(
    "--api",
    type=click.Choice(["openai", "replicate", "elevenlabs", "all"]),
    default="openai",
    help="Which API to test"
)
@click.option(
    "--env-file",
    default=".env",
    help="Environment file with API keys"
)
def test_apis(api: str, env_file: str):
    """Test API connections and credentials."""
    
    try:
        click.echo(f"🧪 Testing API connections...")
        
        # Load environment
        if os.path.exists(env_file):
            env_vars = load_env_file(env_file)
            for key, value in env_vars.items():
                os.environ[key] = value
        
        # Run API tests
        asyncio.run(run_api_tests(api))
        
    except Exception as e:
        click.echo(f"❌ Test error: {e}", err=True)
        sys.exit(1)


def generate_workflow_template(name: str, template: str) -> Dict[str, Any]:
    """Generate workflow configuration based on template."""
    
    base_config = {
        "name": name,
        "description": f"Generated {template} workflow",
        "api_base": "https://api.openai.com"
    }
    
    if template == "content-creation":
        return {
            **base_config,
            "description": "Content creation pipeline with OpenAI, Replicate, and ElevenLabs",
            "variables": {
                "input_text": "Your content text here...",
                "voice_style": "professional",
                "image_style": "photorealistic"
            },
            "steps": [
                {
                    "name": "analyze_content",
                    "endpoint": "/v1/chat/completions",
                    "method": "POST",
                    "auth": {"type": "bearer", "token": "${OPENAI_API_KEY}"},
                    "headers": {"Content-Type": "application/json"},
                    "payload_template": """{
                        "model": "gpt-4",
                        "messages": [
                            {"role": "user", "content": "Analyze this content: {{ input_text }}"}
                        ],
                        "max_tokens": 500
                    }""",
                    "extract_fields": {"analysis": "choices.0.message.content"},
                    "timeout": "30s"
                },
                {
                    "name": "generate_image",
                    "api_base": "https://api.replicate.com",
                    "endpoint": "/v1/predictions",
                    "method": "POST",
                    "auth": {"type": "api_key", "header_name": "Authorization", "api_key": "Token ${REPLICATE_API_TOKEN}"},
                    "depends_on": ["analyze_content"],
                    "poll_for_completion": True,
                    "poll_interval": "5s",
                    "poll_timeout": "10m",
                    "completion_field": "status",
                    "completion_values": ["succeeded"],
                    "extract_fields": {"image_url": "output.0"},
                    "timeout": "15m"
                }
            ]
        }
    
    elif template == "api-orchestration":
        return {
            **base_config,
            "description": "General API orchestration workflow",
            "steps": [
                {
                    "name": "step1",
                    "endpoint": "/api/step1",
                    "method": "POST",
                    "payload": {"action": "initialize"}
                },
                {
                    "name": "step2",
                    "endpoint": "/api/step2",
                    "method": "POST",
                    "depends_on": ["step1"],
                    "payload_template": '{"data": {{ step1.response }}}',
                    "retry": {"limit": 3, "delay": "5s", "backoff": "exponential"}
                }
            ]
        }
    
    elif template == "data-pipeline":
        return {
            **base_config,
            "description": "Data processing pipeline",
            "steps": [
                {
                    "name": "fetch_data",
                    "endpoint": "/api/data",
                    "method": "GET",
                    "extract_fields": {"records": "data", "count": "total"}
                },
                {
                    "name": "process_batch1",
                    "endpoint": "/api/process",
                    "method": "POST",
                    "depends_on": ["fetch_data"],
                    "parallel_group": "processing",
                    "payload_template": '{"batch": {{ fetch_data.records[:50] }}}'
                },
                {
                    "name": "process_batch2",
                    "endpoint": "/api/process",
                    "method": "POST",
                    "depends_on": ["fetch_data"],
                    "parallel_group": "processing",
                    "payload_template": '{"batch": {{ fetch_data.records[50:100] }}}'
                },
                {
                    "name": "aggregate_results",
                    "endpoint": "/api/aggregate",
                    "method": "POST",
                    "depends_on": ["processing"]
                }
            ]
        }
    
    else:  # custom
        return {
            **base_config,
            "description": "Custom workflow template",
            "variables": {"custom_param": "value"},
            "steps": [
                {
                    "name": "custom_step",
                    "endpoint": "/api/custom",
                    "method": "POST",
                    "payload": {"param": "{{ custom_param }}"}
                }
            ]
        }


def show_execution_plan(workflow: WorkflowConfig):
    """Show workflow execution plan."""
    
    from ..workflows.execution_engine import WorkflowExecutionEngine
    from ..http.workflow_client import WorkflowHTTPClient
    
    client = WorkflowHTTPClient(base_url=workflow.api_base)
    engine = WorkflowExecutionEngine(http_client=client)
    
    try:
        phases = engine._resolve_dependencies(workflow.steps)
        
        click.echo(f"\n📋 Execution Plan for '{workflow.name}':")
        click.echo(f"   🌐 API Base: {workflow.api_base}")
        click.echo(f"   🔐 Auth: {workflow.auth.type if workflow.auth else 'None'}")
        click.echo(f"   📊 Total Steps: {len(workflow.steps)}")
        click.echo(f"   🔄 Execution Phases: {len(phases)}")
        
        for i, phase in enumerate(phases, 1):
            click.echo(f"\n   Phase {i}:")
            for step in phase:
                parallel_info = f" (parallel group: {step.parallel_group})" if step.parallel_group else ""
                depends_info = f" (depends on: {step.depends_on})" if step.depends_on else ""
                click.echo(f"     • {step.name}{parallel_info}{depends_info}")
        
        click.echo(f"\n✅ Execution plan valid")
        
    except Exception as e:
        click.echo(f"❌ Planning error: {e}")


async def run_workflow_execution(workflow: WorkflowConfig, verbose: bool):
    """Execute workflow and show results."""
    
    click.echo(f"\n🚀 Executing workflow: {workflow.name}")
    
    client = WorkflowHTTPClient(base_url=workflow.api_base)
    engine = WorkflowExecutionEngine(http_client=client)
    
    try:
        result = await engine.execute_workflow(workflow)
        
        click.echo(f"\n{'='*60}")
        if result.success:
            click.echo("✅ Workflow completed successfully!")
            click.echo(f"⏱️  Total execution time: {result.total_execution_time:.2f}s")
            click.echo(f"📊 Steps executed: {len(result.step_results)}")
            
            if verbose:
                click.echo(f"\n📋 Step Results:")
                for step_name, step_result in result.step_results.items():
                    if step_result.success:
                        click.echo(f"   ✅ {step_name}: {step_result.execution_time:.2f}s")
                        if hasattr(step_result, 'response_data') and step_result.response_data:
                            if isinstance(step_result.response_data, dict):
                                keys = list(step_result.response_data.keys())[:3]
                                click.echo(f"      📄 Response keys: {keys}")
                    else:
                        click.echo(f"   ❌ {step_name}: {step_result.error}")
            
            click.echo(f"\n🎯 Workflow completed successfully!")
            
        else:
            click.echo("❌ Workflow failed!")
            click.echo(f"💥 Error: {result.error}")
            
            click.echo(f"\n📋 Step Results:")
            for step_name, step_result in result.step_results.items():
                if step_result.success:
                    click.echo(f"   ✅ {step_name}: {step_result.execution_time:.2f}s")
                else:
                    click.echo(f"   ❌ {step_name}: {step_result.error}")
    
    except Exception as e:
        click.echo(f"❌ Execution failed: {e}")
        raise


async def run_api_tests(api: str):
    """Run API connection tests."""
    
    from ..config.workflow import AuthConfig, StepConfig
    
    tests = []
    
    if api in ["openai", "all"]:
        if os.getenv("OPENAI_API_KEY"):
            tests.append(("OpenAI", test_openai_connection))
        else:
            click.echo("⚠️  OPENAI_API_KEY not found")
    
    if api in ["replicate", "all"]:
        if os.getenv("REPLICATE_API_TOKEN"):
            tests.append(("Replicate", test_replicate_connection))
        else:
            click.echo("⚠️  REPLICATE_API_TOKEN not found")
    
    if api in ["elevenlabs", "all"]:
        if os.getenv("ELEVENLABS_API_KEY"):
            tests.append(("ElevenLabs", test_elevenlabs_connection))
        else:
            click.echo("⚠️  ELEVENLABS_API_KEY not found")
    
    if not tests:
        click.echo("❌ No API keys found to test")
        return
    
    for api_name, test_func in tests:
        click.echo(f"🧪 Testing {api_name}...")
        try:
            success = await test_func()
            if success:
                click.echo(f"   ✅ {api_name} connection successful")
            else:
                click.echo(f"   ❌ {api_name} connection failed")
        except Exception as e:
            click.echo(f"   ❌ {api_name} error: {e}")


async def test_openai_connection():
    """Test OpenAI API connection."""
    
    from ..config.workflow import AuthConfig, StepConfig
    
    auth = AuthConfig(type="bearer", token=os.getenv("OPENAI_API_KEY"))
    client = WorkflowHTTPClient(base_url="https://api.openai.com")
    client.set_auth(auth)
    
    try:
        response = client.make_request(
            endpoint="/v1/chat/completions",
            method="POST",
            headers={"Content-Type": "application/json"},
            payload={
                "model": "gpt-3.5-turbo",
                "messages": [{"role": "user", "content": "Say 'test' and nothing else."}],
                "max_tokens": 5
            },
            timeout=30
        )
        return "choices" in response and len(response["choices"]) > 0
    except Exception:
        return False


async def test_replicate_connection():
    """Test Replicate API connection."""
    
    from ..config.workflow import AuthConfig
    
    auth = AuthConfig(
        type="api_key", 
        header_name="Authorization", 
        api_key=f"Token {os.getenv('REPLICATE_API_TOKEN')}"
    )
    client = WorkflowHTTPClient(base_url="https://api.replicate.com")
    client.set_auth(auth)
    
    try:
        response = client.make_request(
            endpoint="/v1/models",
            method="GET",
            timeout=30
        )
        return "results" in response or isinstance(response, list)
    except Exception:
        return False


async def test_elevenlabs_connection():
    """Test ElevenLabs API connection."""
    
    from ..config.workflow import AuthConfig
    
    auth = AuthConfig(
        type="api_key",
        header_name="xi-api-key",
        api_key=os.getenv("ELEVENLABS_API_KEY")
    )
    client = WorkflowHTTPClient(base_url="https://api.elevenlabs.io")
    client.set_auth(auth)
    
    try:
        response = client.make_request(
            endpoint="/v1/voices",
            method="GET",
            timeout=30
        )
        return "voices" in response or isinstance(response, list)
    except Exception:
        return False