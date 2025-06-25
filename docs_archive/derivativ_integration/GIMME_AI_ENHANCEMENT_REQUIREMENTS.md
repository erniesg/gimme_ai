# gimme_ai Enhancement Requirements for Derivativ Integration

## 🎯 Project Overview

**Objective**: Enhance gimme_ai to be a generic, reusable workflow orchestration engine that can handle Derivativ's daily question generation pipeline while remaining modular for other use cases.

**Key Requirement**: Daily automated generation of 50 Cambridge IGCSE questions at 2:00 AM Singapore Time via Cloudflare Workflows.

## 📁 Project Structure

```
gimme_ai_enhancement_specs/
├── generic_api_workflow.ts          # Core Cloudflare Workers workflow engine
├── yaml_config_parser.py            # YAML configuration with Jinja2 templating  
├── singapore_timezone_scheduler.py  # SGT timezone conversion utilities
├── test_gimme_ai_workflow_config.py # Configuration validation tests
├── test_gimme_ai_api_execution.py   # API execution and retry logic tests
└── test_gimme_ai_execution_planning.py # Parallel/sequential execution tests
```

## 🏗️ Core Architecture Requirements

### 1. Generic Workflow Engine (TypeScript)

**File**: `generic_api_workflow.ts`
**Purpose**: Production-ready Cloudflare Workers workflow engine

**Key Components**:
```typescript
// Core interfaces required
interface WorkflowConfig {
  name: string;
  schedule?: string;           // Cron format
  timezone?: string;           // "Asia/Singapore"
  api_base: string;           // "https://api.derivativ.ai"
  auth?: AuthConfig;
  variables?: Record<string, any>;
  steps: StepConfig[];
  monitoring?: MonitoringConfig;
}

interface StepConfig {
  name: string;
  endpoint: string;
  method?: HttpMethod;
  depends_on?: string[];       // Step dependencies
  parallel_group?: string;     // For parallel execution
  max_parallel?: number;       // Concurrency control
  retry?: RetryConfig;
  timeout?: string;
  payload_template?: string;   // Jinja2 template
}
```

**Critical Cloudflare Workflows Compliance**:
- State persistence via `step.do()` returns only
- Deterministic step naming (no timestamps/random values)
- Proper hibernation handling
- 10,000 step limit awareness

### 2. Configuration Management (Python)

**File**: `yaml_config_parser.py`
**Purpose**: YAML configuration parsing with Jinja2 templating

**Required Features**:
- Schema validation with comprehensive error reporting
- Jinja2 template rendering with custom filters
- Pre-built Derivativ workflow templates
- Environment variable substitution

**Example Derivativ Configuration**:
```yaml
name: "derivativ_cambridge_igcse_daily"
schedule: "0 18 * * *"  # 2 AM SGT → 6 PM UTC
timezone: "Asia/Singapore"
api_base: "https://api.derivativ.ai"

variables:
  topics: ["algebra", "geometry", "statistics"]
  questions_per_topic: 8
  grade_level: 9

steps:
  # Phase 1: Parallel question generation
  - name: "generate_algebra_questions"
    endpoint: "/api/questions/generate"
    parallel_group: "question_generation"
    
  # Phase 2: Document creation (depends on Phase 1)
  - name: "create_worksheet"
    endpoint: "/api/documents/generate"
    depends_on: ["question_generation"]
```

### 3. Singapore Timezone Scheduling (Python)

**File**: `singapore_timezone_scheduler.py`
**Purpose**: Convert Singapore business hours to UTC for Cloudflare Workers

**Critical Functions**:
- SGT → UTC cron conversion (2 AM SGT = 6 PM UTC previous day)
- Predefined business hour schedules
- Automatic wrangler.toml generation

## 🔄 Workflow Execution Patterns

### Sequential vs Parallel Execution

**Sequential Pattern** (Dependencies):
```yaml
steps:
  - name: "init"
    endpoint: "/api/init"
  - name: "process"
    depends_on: ["init"]
  - name: "cleanup"  
    depends_on: ["process"]
```

**Parallel Pattern** (Concurrent):
```yaml
steps:
  - name: "task1"
    parallel_group: "workers"
  - name: "task2" 
    parallel_group: "workers"
  - name: "task3"
    parallel_group: "workers"
```

**Mixed Pattern** (Derivativ-style):
```yaml
steps:
  # Phase 1: Parallel generation across topics
  - name: "generate_algebra"
    parallel_group: "question_generation"
  - name: "generate_geometry"
    parallel_group: "question_generation"
    
  # Phase 2: Sequential processing (waits for Phase 1)
  - name: "create_documents"
    depends_on: ["question_generation"]
```

## 🔌 Derivativ API Integration Requirements

### Required Endpoints Support

**Question Generation**: 
- `POST /api/questions/generate`
- Input: `{topic, count, grade_level, quality_threshold}`
- Output: `{question_ids[], status, metadata}`

**Document Generation**:
- `POST /api/documents/generate` 
- Input: `{document_type, question_ids[], detail_level}`
- Output: `{document_id, status}`

**Storage Operations**:
- `POST /api/documents/store`
- Input: `{documents[], create_dual_versions, metadata}`
- Output: `{storage_id, status}`

### Authentication Requirements
```yaml
auth:
  type: "bearer"
  token: "${DERIVATIV_API_KEY}"
```

### Error Handling & Retries
```yaml
retry:
  limit: 3
  delay: "10s"
  backoff: "exponential"
  timeout: "5m"
```

## 🚨 Critical Implementation Constraints

### Cloudflare Workflows Limitations
Based on latest docs, these are **CRITICAL** to follow:

1. **State Persistence**: 
   ```typescript
   // ✅ CORRECT - State persisted via step returns
   const result = await step.do('step1', async () => {
     return await apiCall();
   });
   
   // ❌ WRONG - Variables lost on hibernation  
   let result = null;
   await step.do('step1', async () => {
     result = await apiCall(); // LOST!
   });
   ```

2. **Deterministic Step Names**:
   ```typescript
   // ✅ CORRECT
   await step.do('generate_algebra_questions', async () => {});
   
   // ❌ WRONG
   await step.do(`step_${Date.now()}`, async () => {}); // Non-deterministic
   ```

3. **Idempotent Operations**:
   ```typescript
   await step.do('charge_customer', async () => {
     // Check if already charged BEFORE charging
     const existing = await checkExistingCharge(customerId);
     if (existing.charged) return;
     return await chargeCustomer(customerId);
   });
   ```

4. **Granular Steps**:
   ```typescript
   // ✅ CORRECT - Separate concerns
   const data = await step.do('fetch_data', async () => { ... });
   const processed = await step.do('process_data', async () => { ... });
   
   // ❌ WRONG - Too much in one step
   await step.do('fetch_and_process', async () => {
     const data = await fetch(); // If this succeeds but next fails...
     return await process(data); // ...whole step retries
   });
   ```

## 🧪 Testing Strategy Requirements

### Local Development
```bash
# Test YAML configuration parsing
python gimme_ai_enhancement_specs/yaml_config_parser.py

# Test Singapore timezone conversion  
python gimme_ai_enhancement_specs/singapore_timezone_scheduler.py

# Run workflow validation tests
pytest gimme_ai_enhancement_specs/test_gimme_ai_workflow_config.py
```

### Live API Testing Strategy
Since Derivativ API isn't deployed yet, implement testing in phases:

**Phase 1**: Mock API Testing
- Test workflow engine with OpenAI/Replicate APIs
- Validate retry logic, parallel execution, error handling

**Phase 2**: Derivativ Integration Testing
- Once Derivativ API is deployed, update endpoints
- Test complete question generation pipeline
- Validate Singapore timezone scheduling

**Phase 3**: Production Validation
- Deploy to Cloudflare Workers
- Monitor daily 2 AM SGT executions
- Validate 50 questions generated successfully

## 📊 Data Models & Input/Output Specifications

### Workflow Configuration Schema
```yaml
# Required fields
name: string                    # Unique workflow identifier
api_base: string               # Base URL for all API calls
steps: StepConfig[]            # Array of workflow steps

# Optional fields  
schedule: string               # Cron format (UTC)
timezone: string               # Source timezone for conversion
auth: AuthConfig              # Authentication configuration
variables: object             # Global template variables
monitoring: MonitoringConfig  # Webhook notifications
```

### Step Configuration Schema
```yaml
# Required fields
name: string                   # Unique step identifier
endpoint: string              # API endpoint path

# Optional fields
method: HttpMethod            # GET, POST, PUT, DELETE, PATCH
depends_on: string[]          # Step dependencies 
parallel_group: string       # Parallel execution group
max_parallel: number         # Concurrency limit
payload_template: string     # Jinja2 template for request body
retry: RetryConfig           # Retry configuration
timeout: string              # Step timeout ("5m", "30s")
continue_on_error: boolean   # Allow step failure
```

### Derivativ-Specific Data Models
```typescript
// Question Generation Request
interface QuestionGenerationRequest {
  topic: string;              // "algebra", "geometry", etc.
  count: number;              // Number of questions to generate
  grade_level: number;        // 7, 8, 9, 10, 11
  quality_threshold: number;  // 0.0 - 1.0
  request_id: string;         // For tracking
}

// Document Generation Request  
interface DocumentGenerationRequest {
  document_type: "worksheet" | "answer_key" | "teaching_notes";
  question_ids: string[];
  detail_level: "low" | "medium" | "high";
  include_solutions?: boolean;
  metadata?: Record<string, any>;
}
```

## 🛠️ Implementation Agreements & Standards

### Code Organization Standards
```
gimme_ai/
├── src/
│   ├── workflows/           # Cloudflare Workers workflow definitions
│   ├── config/             # YAML configuration parsing
│   ├── scheduling/         # Timezone and cron utilities
│   └── templates/          # Pre-built workflow templates
├── tests/
│   ├── unit/              # Component testing
│   ├── integration/       # API integration testing
│   └── e2e/               # End-to-end workflow testing
└── examples/
    ├── derivativ.yaml     # Derivativ daily generation config
    └── generic.yaml       # Generic workflow examples
```

### API Contract Standards
1. **Authentication**: All APIs must support Bearer token authentication
2. **Error Responses**: Consistent HTTP status codes and error formats
3. **Request IDs**: All requests must include tracking IDs
4. **Timeouts**: All endpoints must respond within configured timeouts
5. **Idempotency**: All non-GET operations must be idempotent

### Configuration Standards
1. **Environment Variables**: All secrets via environment variables
2. **YAML Schema**: Strict schema validation with helpful error messages
3. **Template Variables**: Consistent naming conventions (snake_case)
4. **Timezone Handling**: Always specify timezone explicitly
5. **Retry Policies**: Configurable per-step retry strategies

### Monitoring & Observability Requirements
```yaml
monitoring:
  webhook_url: "https://api.derivativ.ai/webhooks/workflow_complete"
  alerts:
    on_failure: true
    on_long_duration: "30m"
```

## 🚀 Deployment Requirements

### Cloudflare Workers Configuration
```toml
# wrangler.toml - Auto-generated from templates
[triggers]
crons = [
  "0 18 * * *"  # Daily question generation (2 AM SGT → UTC)
]

[[workflows]]
binding = "DERIVATIV_WORKFLOW"
class_name = "DerivativWorkflow"
```

### Environment Variables Required
```bash
# Derivativ API Integration
DERIVATIV_API_KEY=xxx
DERIVATIV_API_BASE=https://api.derivativ.ai

# Monitoring & Notifications  
WEBHOOK_URL=https://api.derivativ.ai/webhooks/workflow_complete
ENVIRONMENT=production

# Feature Flags
ENABLE_PARALLEL_GENERATION=true
MAX_CONCURRENT_STEPS=6
```

## ⚠️ Critical Implementation Caveats

### Singapore Timezone Gotchas
- **SGT is UTC+8 year-round** (no DST)
- **2 AM SGT = 6 PM UTC previous day** 
- **Cron runs in UTC on Cloudflare Workers**
- **Must convert before deployment**

### Cloudflare Workflows Gotchas  
- **No filesystem access** - all data via HTTP/bindings
- **10,000 step limit** - plan step granularity carefully
- **No nested workflows** - design flat execution plans
- **Hibernation resets memory** - only step returns persist
- **Step names are cache keys** - must be deterministic

### Derivativ Pipeline Gotchas
- **Question generation is expensive** - preserve partial results
- **Topics must be processed in parallel** - 6 topics × 8 questions = 48 total
- **Documents depend on all questions** - proper dependency management critical
- **Quality thresholds vary by topic** - configurable per step

### Performance Considerations
- **Question Generation**: 5-10s per question, highly parallelizable
- **Document Creation**: 10-20s per document, moderate parallelization  
- **Storage Operations**: 2-5s per operation, highly parallelizable
- **Total Pipeline Target**: <20 minutes for 48 questions

## 📝 Next Developer Checklist

### Phase 1: Foundation (Days 1-2)
- [ ] Set up Cloudflare Workers development environment
- [ ] Implement generic workflow configuration schema validation
- [ ] Create basic step execution with HTTP calling capabilities
- [ ] Add simple dependency resolution (sequential only)
- [ ] Implement error handling and retry logic

### Phase 2: Advanced Features (Days 3-4)
- [ ] Add parallel execution with step groups
- [ ] Implement complex dependency graph resolution
- [ ] Integrate Singapore timezone scheduling
- [ ] Add comprehensive error recovery mechanisms
- [ ] Create Derivativ-specific workflow templates

### Phase 3: Integration & Testing (Days 5-6)
- [ ] Test with live OpenAI/Replicate APIs
- [ ] Validate complete workflow execution patterns
- [ ] Deploy to Cloudflare Workers staging environment
- [ ] Test Singapore timezone scheduling accuracy
- [ ] Performance optimization and monitoring setup

### Success Criteria
- [ ] 50 questions generated across 6 topics in <20 minutes
- [ ] 99% workflow success rate with proper error recovery
- [ ] Real-time status monitoring and notifications
- [ ] Zero-downtime deployments and configuration updates
- [ ] Daily 2 AM SGT execution working reliably

---

**Note**: All implementation files are provided in `gimme_ai_enhancement_specs/` directory as reference implementations. The next developer should use these as architectural guidance while implementing the production-ready version within the gimme_ai codebase structure.