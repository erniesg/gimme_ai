# Gimme AI Integration Package for Derivativ

This directory contains all the specifications, documentation, and reference implementations needed to enhance the gimme_ai library for Derivativ integration and general consumption.

## 📁 Directory Contents

### Core Documentation
- `GIMME_AI_ENHANCEMENT_REQUIREMENTS.md` - Complete project specifications and requirements
- `GIMME_AI_INTEGRATION_GUIDE.md` - Comprehensive integration guide with architecture decisions
- `CLOUDFLARE_WORKFLOWS_RESEARCH.md` - Research notes on Cloudflare Workflows for automation

### Reference Implementations (`reference_code/`)
**⚠️ IMPORTANT**: These are **reference implementations** for architectural guidance only. They demonstrate the design patterns and approach but should not be used directly in production. The next developer should use these as examples while implementing the production-ready version within the actual gimme_ai codebase structure.

#### Core Components
- `generic_api_workflow.ts` - Core Cloudflare Workers workflow engine architecture (700+ lines)
- `yaml_config_parser.py` - YAML configuration parsing with Jinja2 templating (500+ lines)
- `singapore_timezone_scheduler.py` - Singapore timezone conversion utilities (400+ lines)

#### Test Suites
- `test_gimme_ai_workflow_config.py` - Configuration schema validation tests
- `test_gimme_ai_execution_planning.py` - Parallel vs sequential execution logic tests
- `test_gimme_ai_api_execution.py` - HTTP request execution with retry logic tests

### Templates and Examples (`templates/`)
- Pre-built YAML workflow templates for common Derivativ use cases
- Example configurations for different scheduling scenarios
- Template variables and Jinja2 examples

## 🎯 Integration Goals

### Primary Objectives
1. **Make gimme_ai generally reusable** for any project requiring workflow orchestration
2. **Add Derivativ-specific workflows** while maintaining library's generic nature
3. **Implement daily question generation** at 2 AM Singapore Time using Cloudflare Workflows
4. **Support configurable parameters** for question count, pipeline selection, and scheduling

### Key Features to Implement
- **Generic API passthrough** with authentication and retry strategies
- **YAML-based workflow configuration** with Jinja2 templating
- **Parallel vs sequential step execution** with dependency management
- **Singapore timezone scheduling** (2 AM SGT = 6 PM UTC previous day)
- **Error handling and retry mechanisms** with exponential backoff
- **Real-time monitoring and webhooks** for workflow status updates

## 🏗️ Architecture Overview

### Multi-Layer Architecture
```
Cloudflare Workers (Edge Runtime)
    ↓
GenericAPIWorkflow Engine
    ↓
YAML Configuration + Jinja2 Templates
    ↓
HTTP Request Executor with Auth & Retry
    ↓
Target APIs (Derivativ, OpenAI, etc.)
```

### Key Design Patterns
- **Dependency Graph Resolution** - Automatic topological sorting of workflow steps
- **Parallel Group Execution** - Steps can be grouped for concurrent execution
- **Template-Driven Payloads** - Dynamic request generation using Jinja2
- **Configurable Authentication** - Support for Bearer, API Key, Basic, and custom auth
- **Resilient Error Handling** - Multiple retry strategies with configurable backoff

## 🚀 Implementation Phases

### Phase 1: Core Infrastructure (3 days - Hackathon Ready)
1. **Generic Workflow Engine** - Implement basic orchestration patterns
2. **YAML Configuration Parser** - Support for template rendering and validation
3. **HTTP Request Executor** - Authentication and retry mechanisms
4. **Basic Parallel Execution** - Simple dependency resolution

### Phase 2: Advanced Features (Future Enhancement)
1. **Complex Dependency Management** - Circular dependency detection
2. **Advanced Monitoring** - Comprehensive logging and alerting
3. **Performance Optimization** - Caching and batch processing
4. **Extended Authentication** - OAuth2, JWT, and custom schemes

### Phase 3: Production Deployment (Post-Hackathon)
1. **Cloudflare Workers Deployment** - Edge runtime optimization
2. **Scaling and Load Testing** - Performance validation
3. **Documentation and Examples** - Community adoption support
4. **Maintenance and Updates** - Long-term support strategy

## 📋 Next Developer Tasks

### Immediate Actions (Day 1)
1. **Review all documentation** in this package for complete context
2. **Understand the reference implementations** - focus on architecture patterns, not exact code
3. **Set up gimme_ai development environment** with proper testing framework
4. **Implement basic YAML configuration parsing** following the reference patterns

### Core Implementation (Days 2-3)
1. **Build GenericAPIWorkflow class** with step execution and dependency resolution
2. **Add authentication manager** with support for multiple auth types
3. **Implement HTTP request executor** with retry and error handling
4. **Create workflow templates** for Derivativ daily question generation

### Validation and Testing (Day 3)
1. **Write comprehensive tests** following the test suite patterns in reference_code/
2. **Test with live APIs** (OpenAI, Anthropic) using provided test configurations
3. **Validate Singapore timezone scheduling** - ensure 2 AM SGT = 6 PM UTC works correctly
4. **Deploy test workflow** to Cloudflare Workers for end-to-end validation

## 🔧 Technical Specifications

### Singapore Time Scheduling
- **Target Time**: 2 AM Singapore Time (SGT)
- **UTC Equivalent**: 6 PM UTC previous day (SGT = UTC+8)
- **Cron Expression**: `0 18 * * *` (runs at 18:00 UTC = 02:00 SGT next day)

### Workflow Configuration Schema
```yaml
name: "derivativ_cambridge_igcse_daily"
schedule: "0 18 * * *"  # 2 AM Singapore Time
timezone: "Asia/Singapore"
api_base: "https://api.derivativ.ai"
auth:
  type: "bearer"
  token: "${DERIVATIV_API_KEY}"
steps:
  - name: "generate_algebra_questions"
    endpoint: "/api/questions/generate"
    parallel_group: "question_generation"
    retry:
      limit: 3
      delay: "10s"
      backoff: "exponential"
```

### Error Handling Strategy
- **Automatic Retries**: Exponential backoff with configurable limits
- **Graceful Degradation**: Continue workflow on non-critical step failures
- **Comprehensive Logging**: All decisions and errors tracked for debugging
- **Webhook Notifications**: Real-time status updates for monitoring

## 📊 Success Metrics

### Development Success (Hackathon)
- [ ] Generic workflow engine executes multi-step API calls
- [ ] YAML configurations parse and render correctly with templates
- [ ] Authentication works with real APIs (OpenAI, Derivativ)
- [ ] Singapore timezone scheduling implemented and tested
- [ ] Parallel step execution works with dependency resolution

### Production Readiness (Post-Hackathon)
- [ ] Deployed to Cloudflare Workers with reliable performance
- [ ] Comprehensive error handling prevents workflow failures
- [ ] Monitoring and alerting provide operational visibility
- [ ] Documentation enables easy adoption by other teams
- [ ] Test coverage exceeds 90% for critical workflow logic

## 🎖️ Quality Standards

### Code Quality
- **Test-Driven Development** - All components have comprehensive test coverage
- **Clean Architecture** - Clear separation between workflow engine and business logic
- **Type Safety** - Full TypeScript implementation with proper type definitions
- **Error Resilience** - Graceful handling of network failures and API errors

### Documentation Quality
- **API Documentation** - Complete function and class documentation
- **Usage Examples** - Working examples for common use cases
- **Architecture Diagrams** - Visual representation of system components
- **Troubleshooting Guide** - Common issues and solutions documented

---

**Generated as part of Derivativ AI hackathon project requirements.**
**Last Updated**: December 2024
**Target Completion**: 3-day hackathon timeline