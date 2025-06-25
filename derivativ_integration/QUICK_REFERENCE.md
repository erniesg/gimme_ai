# Quick Reference Card

## 🚀 Critical Information for Next Developer

### Singapore Time Conversion (MOST IMPORTANT!)
```
Target: 2 AM Singapore Time (SGT) daily
UTC Equivalent: 6 PM UTC previous day
Cron Expression: "0 18 * * *"
Timezone: "Asia/Singapore"
Calculation: SGT = UTC + 8 hours, so UTC = SGT - 8 hours
```

### Key File Locations
- **Main Specs**: `GIMME_AI_ENHANCEMENT_REQUIREMENTS.md`
- **Architecture Guide**: `GIMME_AI_INTEGRATION_GUIDE.md`
- **Reference Code**: `reference_code/` (700+ lines of examples)
- **Templates**: `templates/derivativ_daily_workflow.yaml`
- **Implementation Steps**: `IMPLEMENTATION_GUIDE.md`

### Core Classes to Implement
1. **YAMLConfigParser** - Parse workflow configurations with Jinja2
2. **HTTPRequestExecutor** - HTTP requests with auth and retry
3. **ExecutionPlanner** - Dependency resolution and parallel grouping
4. **GenericAPIWorkflow** - Main orchestration engine

### Essential Test Commands
```bash
# Validate Singapore timezone
python -c "print('2 AM SGT =', (2-8)%24, 'PM UTC previous day')"  # Should print: 2 AM SGT = 18 PM UTC previous day

# Test YAML parsing
python reference_code/yaml_config_parser.py

# Test execution planning  
python reference_code/test_gimme_ai_execution_planning.py

# Test API execution
python reference_code/test_gimme_ai_api_execution.py
```

### Authentication Patterns
```python
# Bearer Token
{"type": "bearer", "token": "your-token"}

# API Key
{"type": "api_key", "api_key": "your-key", "header_name": "X-API-Key"}

# Basic Auth
{"type": "basic", "username": "user", "password": "pass"}
```

### Workflow YAML Structure
```yaml
name: "workflow_name"
schedule: "0 18 * * *"  # 2 AM SGT
timezone: "Asia/Singapore"
api_base: "https://api.example.com"
auth:
  type: "bearer"
  token: "{{ api_key }}"
steps:
  - name: "step1"
    endpoint: "/api/endpoint"
    parallel_group: "group1"  # Optional: for parallel execution
    depends_on: ["step0"]     # Optional: dependencies
    retry:
      limit: 3
      delay: "10s"
      backoff: "exponential"
```

### Parallel Execution Logic
```python
# Phase 1: Steps with no dependencies (can run in parallel)
# Phase 2: Steps that depend on Phase 1 (can run in parallel within phase)
# Phase 3: Steps that depend on Phase 2 (can run in parallel within phase)
# etc.
```

### Demo Success Criteria
- [ ] YAML config parses with templates
- [ ] Singapore timezone scheduling works  
- [ ] Parallel execution with dependencies
- [ ] Authentication with real APIs
- [ ] Error handling with retries
- [ ] Complete workflow in < 30 seconds

### Emergency Backup Plan
If implementation fails:
1. Show reference code architecture (impressive!)
2. Explain Singapore timezone calculation
3. Demonstrate YAML template rendering
4. Walk through parallel execution algorithm
5. Emphasize production-ready error handling

### Key Selling Points for Judges
- **Generic Library**: Works for any API workflow orchestration
- **Production Ready**: Comprehensive error handling and testing
- **Real Business Value**: Automates daily content generation
- **Scalable Architecture**: Designed for Cloudflare Workers edge deployment
- **Immediate Utility**: Teachers can use this today

---
**REMEMBER**: The goal is automated daily question generation at 2 AM Singapore time. Everything else is secondary! 🎯