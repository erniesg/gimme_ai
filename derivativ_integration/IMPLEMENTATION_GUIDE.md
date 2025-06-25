# Implementation Guide for Next Developer

This guide provides step-by-step instructions for implementing gimme_ai enhancements based on the specifications and reference code in this package.

## 🎯 Quick Start (30 minutes)

### 1. Environment Setup
```bash
# Navigate to gimme_ai project
cd /path/to/gimme_ai

# Install dependencies
npm install
pip install -r requirements.txt

# Copy this integration package
cp -r /path/to/gimme_ai_integration_package ./derivativ_integration/
```

### 2. Review Reference Architecture
- **Start with**: `reference_code/generic_api_workflow.ts` (700 lines) - Core engine
- **Then read**: `reference_code/yaml_config_parser.py` (500 lines) - Configuration parsing
- **Understand**: `reference_code/test_gimme_ai_execution_planning.py` - Execution patterns

### 3. Test Understanding
```bash
# Run reference tests to understand expected behavior
python reference_code/test_gimme_ai_workflow_config.py
python reference_code/test_gimme_ai_execution_planning.py
python reference_code/test_gimme_ai_api_execution.py
```

## 🏗️ Implementation Roadmap

### Day 1: Core Infrastructure (8 hours)

#### Morning (4 hours): Configuration System
```bash
# 1. Create YAML parser module
touch src/config/yaml_parser.py
touch src/config/workflow_validator.py

# 2. Implement based on reference_code/yaml_config_parser.py
# Key classes to implement:
# - YAMLConfigParser
# - ParsedWorkflowConfig
# - WorkflowConfigValidator

# 3. Add Jinja2 templating support
pip install jinja2 pyyaml

# 4. Test with templates/simple_api_test.yaml
```

**Critical Implementation Points:**
- Copy the Jinja2 custom filters from reference code
- Implement Singapore timezone conversion: `2 AM SGT = 6 PM UTC previous day`
- Validate cron schedule format: `"0 18 * * *"`

#### Afternoon (4 hours): HTTP Request Executor
```bash
# 1. Create request execution module
touch src/execution/http_executor.py
touch src/execution/auth_manager.py

# 2. Implement based on reference_code/test_gimme_ai_api_execution.py
# Key classes to implement:
# - HTTPRequestExecutor
# - AuthenticationManager  
# - TemplateRenderer

# 3. Add retry logic with exponential backoff
# 4. Test with live APIs (OpenAI, etc.)
```

**Critical Implementation Points:**
- Support Bearer, API Key, Basic, and Custom authentication
- Implement exponential backoff: `delay * (2 ** (attempt - 1))`
- Handle timeout and network errors gracefully

### Day 2: Workflow Engine (8 hours)

#### Morning (4 hours): Execution Planning
```bash
# 1. Create execution planning module
touch src/execution/execution_planner.py
touch src/execution/workflow_executor.py

# 2. Implement based on reference_code/test_gimme_ai_execution_planning.py
# Key classes to implement:
# - ExecutionPlanner
# - WorkflowExecutor
# - StepConfig, ExecutionPhase, StepGroup

# 3. Add dependency resolution with topological sort
# 4. Test with templates/parallel_question_generation.yaml
```

**Critical Implementation Points:**
- Detect circular dependencies using DFS algorithm
- Support parallel groups with concurrency limits
- Implement proper phase separation based on dependencies

#### Afternoon (4 hours): Generic API Workflow
```bash
# 1. Create main workflow engine
touch src/workflow/generic_api_workflow.py
touch src/workflow/step_executor.py

# 2. Implement based on reference_code/generic_api_workflow.ts
# Key classes to implement:
# - GenericAPIWorkflow
# - StepExecutor
# - WorkflowState

# 3. Integrate all components
# 4. Test with templates/derivativ_daily_workflow.yaml
```

**Critical Implementation Points:**
- Maintain workflow state across step executions
- Support template variable substitution in payloads
- Handle step failures with continue_on_error flag

### Day 3: Testing & Deployment (8 hours)

#### Morning (4 hours): Comprehensive Testing
```bash
# 1. Create test suite
mkdir tests/integration
touch tests/integration/test_live_apis.py
touch tests/integration/test_workflow_execution.py

# 2. Test with real APIs
# - OpenAI API connectivity
# - Derivativ API integration
# - Singapore timezone scheduling

# 3. Load test with multiple parallel workflows
# 4. Validate error handling and recovery
```

#### Afternoon (4 hours): Cloudflare Workers Deployment
```bash
# 1. Create Workers deployment script
touch deploy/cloudflare_worker.js
touch deploy/wrangler.toml

# 2. Package workflow engine for edge runtime
# 3. Deploy and test live workflow
# 4. Monitor performance and logs
```

## 🔧 Key Implementation Details

### Singapore Timezone Scheduling
```python
def convert_sgt_to_utc_cron(sgt_hour: int, sgt_minute: int = 0) -> str:
    """Convert Singapore time to UTC cron expression.
    
    SGT is UTC+8, so subtract 8 hours.
    2 AM SGT = 6 PM UTC previous day
    """
    utc_hour = (sgt_hour - 8) % 24
    return f"{sgt_minute} {utc_hour} * * *"

# Example: 2 AM SGT daily
cron_expression = convert_sgt_to_utc_cron(2, 0)  # "0 18 * * *"
```

### Parallel Execution Pattern
```python
async def execute_parallel_group(self, group: StepGroup) -> List[StepResult]:
    """Execute steps in parallel with optional concurrency control."""
    if group.max_parallel and group.max_parallel < len(group.steps):
        semaphore = asyncio.Semaphore(group.max_parallel)
        
        async def execute_with_limit(step):
            async with semaphore:
                return await self.execute_step(step)
        
        tasks = [execute_with_limit(step) for step in group.steps]
    else:
        tasks = [self.execute_step(step) for step in group.steps]
    
    return await asyncio.gather(*tasks, return_exceptions=True)
```

### Authentication Implementation
```python
def apply_auth(headers: dict, auth_config: dict) -> dict:
    """Apply authentication to request headers."""
    auth_type = auth_config.get("type", "none")
    
    if auth_type == "bearer":
        token = auth_config.get("token", "")
        headers["Authorization"] = f"Bearer {token}"
    elif auth_type == "api_key":
        key = auth_config.get("api_key", "")
        header_name = auth_config.get("header_name", "X-API-Key")
        headers[header_name] = key
    # ... other auth types
    
    return headers
```

## 🧪 Testing Strategy

### Unit Tests (Day 1)
```bash
# Test configuration parsing
python -m pytest tests/unit/test_yaml_parser.py -v

# Test authentication manager
python -m pytest tests/unit/test_auth_manager.py -v

# Test HTTP executor
python -m pytest tests/unit/test_http_executor.py -v
```

### Integration Tests (Day 2)
```bash
# Test workflow execution
python -m pytest tests/integration/test_workflow_engine.py -v

# Test parallel execution
python -m pytest tests/integration/test_parallel_execution.py -v

# Test dependency resolution
python -m pytest tests/integration/test_dependency_resolution.py -v
```

### Live API Tests (Day 3)
```bash
# Test with OpenAI API
OPENAI_API_KEY=your_key python tests/live/test_openai_integration.py

# Test with Derivativ API
DERIVATIV_API_KEY=your_key python tests/live/test_derivativ_workflow.py

# Test Singapore timezone scheduling
python tests/live/test_singapore_scheduling.py
```

## 🚨 Critical Success Factors

### Must-Have Features (Hackathon Minimum)
- [ ] YAML workflow configuration parsing with Jinja2 templates
- [ ] HTTP request execution with authentication (Bearer, API Key)
- [ ] Basic parallel execution with dependency resolution
- [ ] Singapore timezone cron scheduling (2 AM SGT = 6 PM UTC)
- [ ] Error handling with retry mechanisms
- [ ] One complete end-to-end workflow test

### Nice-to-Have Features (Time Permitting)
- [ ] Cloudflare Workers deployment
- [ ] Advanced monitoring and webhooks
- [ ] Complex dependency cycle detection
- [ ] Performance optimization and caching
- [ ] Comprehensive error recovery strategies

### Show-Stopper Issues to Avoid
- **Circular Dependencies**: Must detect and prevent infinite loops
- **Authentication Failures**: Must handle auth errors gracefully
- **Timezone Confusion**: Singapore time conversion must be bulletproof
- **Memory Leaks**: Async operations must be properly cleaned up
- **API Rate Limits**: Must respect and handle rate limiting

## 🎯 Demo Preparation

### 5-Minute Demo Script
1. **Show YAML Configuration** (30 seconds)
   - Display `templates/derivativ_daily_workflow.yaml`
   - Highlight Singapore timezone and parallel groups

2. **Execute Live Workflow** (2 minutes)
   - Run question generation workflow
   - Show real-time parallel execution
   - Display API responses and timing

3. **Demonstrate Error Handling** (1 minute)
   - Trigger API failure
   - Show automatic retry with exponential backoff
   - Demonstrate graceful degradation

4. **Architecture Overview** (1 minute)
   - Show code structure and test coverage
   - Highlight production-ready patterns
   - Explain Cloudflare Workers scalability

5. **Impact Statement** (30 seconds)
   - "Generic workflow engine for any API orchestration"
   - "Production-ready with comprehensive error handling"
   - "Immediate value for automated content generation"

### Backup Strategies
- **Offline Demo**: Pre-recorded workflow execution video
- **Mock APIs**: Local mock servers if live APIs fail
- **Static Results**: Pre-generated successful workflow outputs
- **Code Walkthrough**: Focus on architecture if execution fails

## 📋 Quality Checklist

### Before Demo
- [ ] All critical tests passing
- [ ] Singapore timezone conversion verified
- [ ] Live API integration working
- [ ] Error handling demonstrated
- [ ] Performance acceptable (< 30 seconds for full workflow)

### Code Quality
- [ ] Type hints on all functions
- [ ] Docstrings for all public methods
- [ ] Error handling in all API calls
- [ ] Async/await used correctly
- [ ] Resource cleanup (close connections, etc.)

### Documentation
- [ ] README updated with usage examples
- [ ] API documentation generated
- [ ] Configuration schema documented
- [ ] Troubleshooting guide written

---

**Remember**: Focus on demonstrating the core value proposition - automated workflow orchestration with real business value for content generation. The architecture and error handling showcase production readiness that judges will appreciate.

**Success Metric**: If a teacher can schedule daily question generation and it works reliably at 2 AM Singapore time, you've succeeded! 🎯