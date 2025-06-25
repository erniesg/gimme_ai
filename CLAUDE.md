# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

### Python Package Management
- **Install dependencies**: `poetry install`
- **Run tests**: `pytest` or `poetry run pytest`
- **Code formatting**: `poetry run black gimme_ai/`
- **Linting**: `poetry run pylint gimme_ai/`
- **Type checking**: `poetry run mypy gimme_ai/`
- **Coverage report**: `pytest --cov=gimme_ai --cov-report=term-missing`

### CLI Commands
The project provides a CLI tool accessible via `gimme-ai` (after poetry install) or `poetry run gimme-ai`:

**Core Commands:**
- **Initialize project**: `gimme-ai init`
- **Deploy to Cloudflare**: `gimme-ai deploy`
- **Validate config**: `gimme-ai validate`

**Testing Commands:**
- **Run all tests**: `gimme-ai test-all [URL]`
- **Test authentication**: `gimme-ai test-auth [URL]`
- **Test rate limits**: `gimme-ai test-rate-limits [URL]`
- **Test workflows**: `gimme-ai test-workflow [URL]`

**NEW: Advanced Workflow Engine (`gimme-ai wf`):**
- **Create workflow**: `gimme-ai wf init --name my-workflow --template content-creation`
- **Execute workflow**: `gimme-ai wf execute workflow.yaml --env-file .env`
- **Validate workflow**: `gimme-ai wf validate workflow.yaml`
- **Dry run**: `gimme-ai wf execute workflow.yaml --dry-run`

**NEW: Secrets Management (`gimme-ai secrets`):**
- **Create template**: `gimme-ai secrets template --environment development`
- **Validate secrets**: `gimme-ai secrets validate --env-file .env.development`
- **Sync to Cloudflare**: `gimme-ai secrets sync-cloudflare --environment production`

### JavaScript Dependencies
- **Install JS dependencies**: `npm install` (for Hono framework used in Cloudflare Workers)

## Architecture Overview

### Core Components

**CLI Interface** (`gimme_ai/cli/`):
- `commands.py`: Main CLI entry point and command registration
- `commands_init.py`: Project initialization and configuration setup
- `commands_deploy.py`: Cloudflare deployment functionality  
- `commands_test.py`: Testing commands for deployed services
- `commands_workflow.py`: Legacy workflow commands
- `commands_workflow_new.py`: Advanced workflow engine (NEW)
- `commands_secrets.py`: Secrets management system (NEW)

**Configuration Management** (`gimme_ai/config/`):
- `schema.py`: Pydantic models for configuration validation
- `workflow.py`: Advanced workflow configuration models (NEW)
- `secrets.py`: Multi-backend secrets management (NEW)
- `derivativ_templates.py`: Cambridge IGCSE workflow templates (NEW)
- Uses `.gimme-config.json` for project settings

**Workflow System** (`gimme_ai/workflows/` + `gimme_ai/http/`):
- `execution_engine.py`: Workflow orchestration with dependency management (NEW)
- `workflow_client.py`: Multi-auth HTTP client with file operations (NEW)
- `r2_client.py`: Cloudflare R2 storage integration (NEW)

**Utilities** (`gimme_ai/utils/`):
- `environment.py`: Environment variable management
- `singapore_scheduler.py`: SGT to UTC timezone conversion (NEW)

**Deployment System** (`gimme_ai/deploy/`):
- `cloudflare.py`: Cloudflare Workers deployment logic
- `templates.py`: Template generation for Workers, Durable Objects
- `wrangler.py`: Wrangler CLI integration
- Generates JavaScript files from Python templates

**Template System** (`gimme_ai/templates/`):
- `worker.js`: Main Cloudflare Worker template
- `durable_objects.js`: Durable Objects for rate limiting
- `workflow.js`: Workflow orchestration template
- `wrangler.toml`: Cloudflare configuration template

### Key Design Patterns

**Configuration-Driven**: The system uses JSON configuration files (`.gimme-config.json`) to define:
- Project settings and API endpoints
- Rate limiting rules per tier
- Required environment variables
- Workflow definitions and parameters

**Template-Based Code Generation**: Python code generates JavaScript files for Cloudflare Workers:
- Templates use Jinja2 for dynamic content
- Generated files include worker scripts, durable objects, and configuration
- Templates support both API and video workflow types

**Multi-Environment Support**: 
- Development (`dev`) and production (`prod`) endpoint configurations
- Environment-specific settings via `.env` files
- Automatic URL detection for testing deployed services

### Workflow System

The workflow system supports orchestrating multi-step API processes:
- **Dual-type workflows**: Both API and video processing capabilities
- **Dependency management**: Steps can depend on previous step outputs
- **Error handling**: Built-in retry logic and error reporting
- **Configuration files**: YAML-based workflow definitions in `derivativ_integration/templates/`

### Security & Rate Limiting

- **Durable Objects**: Used for distributed rate limiting across Cloudflare's edge
- **Admin authentication**: Password-based admin access for privileged operations
- **API key management**: Secure storage of credentials in environment variables
- **CORS support**: Configurable cross-origin resource sharing

## Testing Strategy

The project includes comprehensive testing for deployed services:
- **Integration tests**: Test actual deployed Cloudflare Workers
- **Authentication testing**: Verify admin access and rate limit bypasses
- **Workflow testing**: End-to-end workflow execution validation
- **Rate limit testing**: Verify rate limiting behavior (resets limits during testing)

Tests automatically detect deployment URLs from configuration or accept explicit URLs as parameters.

## Workflow System (NEW)

### Generic API Workflow Engine
gimme_ai now supports generic workflow orchestration for any REST API:

**Key Features:**
- **YAML Configuration**: Define workflows declaratively
- **Step Dependencies**: Sequential and parallel execution support
- **Authentication**: Bearer, API key, basic, and custom auth types
- **Retry Logic**: Configurable retry strategies with exponential backoff
- **Template Support**: Jinja2 templating for dynamic payloads
- **Error Handling**: Continue-on-error and comprehensive error reporting

### Workflow Commands
```bash
# Execute workflow from YAML file
python -c "
import asyncio
from gimme_ai.config.workflow import WorkflowConfig
from gimme_ai.http.workflow_client import WorkflowHTTPClient
from gimme_ai.workflows.execution_engine import WorkflowExecutionEngine
import yaml

async def run_workflow(yaml_file):
    with open(yaml_file) as f:
        config_data = yaml.safe_load(f)
    
    workflow = WorkflowConfig.from_dict(config_data)
    client = WorkflowHTTPClient(base_url=workflow.api_base)
    engine = WorkflowExecutionEngine(http_client=client)
    
    result = await engine.execute_workflow(workflow)
    print(f'Workflow {workflow.name}: {\"✅ Success\" if result.success else \"❌ Failed\"}')
    return result

# Example usage
asyncio.run(run_workflow('examples/basic_workflow.yaml'))
"
```

### Example Workflows
- `examples/basic_workflow.yaml`: Simple sequential API calls
- `examples/parallel_workflow.yaml`: Parallel execution with dependencies
- `examples/derivativ_simulation.yaml`: Production-ready Derivativ simulation

### Authentication Support
```yaml
auth:
  type: "bearer"           # bearer, api_key, basic, custom
  token: "${API_KEY}"      # Environment variable resolution
  
  # OR api_key auth
  type: "api_key"
  header_name: "X-API-Key"
  api_key: "${API_TOKEN}"
  
  # OR basic auth
  type: "basic"
  username: "admin"
  password: "${PASSWORD}"
```

### Workflow Architecture
- **Configuration Layer**: YAML parsing and validation
- **HTTP Client**: Multi-auth support with retry logic
- **Execution Engine**: Dependency resolution and parallel execution
- **Template System**: Jinja2 for dynamic request generation

## Important Notes

- **Rate limit testing resets limits**: Running rate limit tests will reset your gateway's limits before and after testing
- **Dual workflow type**: All workflows are set to 'dual' type to support both API and video processing
- **Cloudflare dependency**: Requires `wrangler` CLI tool for deployment operations
- **Environment variables**: Critical for API keys and admin passwords - never commit these to the repository
- **Workflow engine**: Supports complex dependencies, parallel execution, and error recovery for production use