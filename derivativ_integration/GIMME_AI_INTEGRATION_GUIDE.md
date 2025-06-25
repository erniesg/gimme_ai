# gimme_ai + Derivativ Integration Guide

## 🎯 Overview: Making gimme_ai Production-Ready for Derivativ

This guide provides critical implementation details for enhancing gimme_ai to support Derivativ's educational pipeline while maintaining generic reusability for any API orchestration.

## 📋 Critical Architecture Decisions

### Current gimme_ai State Analysis
- **Existing**: Basic Cloudflare Workers deployment, video workflow templates, simple API gateway
- **Missing**: Generic API orchestration, step dependencies, parallel execution, configurable scheduling
- **Status**: Foundation exists but needs significant enhancement for production use

### Target Architecture: Generic API Workflow Engine
```
gimme_ai (Enhanced) → Cloudflare Workers → Any REST API
├── Generic workflow orchestration via YAML config
├── Step dependency management (sequential/parallel)
├── Configurable retry strategies and error handling
├── Singapore timezone cron scheduling support
└── Real-time monitoring and status reporting
```

## 🔧 Critical Implementation Requirements

### 1. Data Models & Configuration Schema

#### Core Workflow Configuration
```typescript
interface WorkflowConfig {
  name: string;
  description?: string;
  schedule?: string;          // Cron format: "0 18 * * *" = 2 AM SGT
  timezone?: string;          // "Asia/Singapore" 
  api_base: string;          // Base URL for all API calls
  auth?: AuthConfig;         // Authentication configuration
  variables?: Record<string, any>;  // Global variables for templating
  steps: StepConfig[];       // Workflow steps
  monitoring?: MonitoringConfig;
}

interface StepConfig {
  name: string;              // Unique step identifier
  description?: string;
  endpoint: string;          // API endpoint path
  method?: HttpMethod;       // GET, POST, PUT, DELETE
  
  // Execution Control
  depends_on?: string[];     // Step dependencies
  parallel_group?: string;   // Group for parallel execution
  max_parallel?: number;     // Max concurrent executions
  
  // Request Configuration
  headers?: Record<string, string>;
  payload_template?: string; // Jinja2 template for request body
  payload?: any;            // Direct payload (alternative to template)
  
  // Error Handling
  retry?: RetryConfig;
  timeout?: string;         // "10m", "30s", etc.
  continue_on_error?: boolean;
  
  // Response Processing
  response_transform?: string; // Jinja2 template for response transformation
  output_key?: string;       // Key to store result under
}

interface RetryConfig {
  limit: number;             // Max retry attempts
  delay: string;            // Initial delay: "5s", "1m"
  backoff: 'constant' | 'linear' | 'exponential';
  timeout?: string;         // Per-attempt timeout
}
```

#### Authentication Models
```typescript
interface AuthConfig {
  type: 'none' | 'bearer' | 'api_key' | 'basic' | 'custom';
  token?: string;           // For bearer auth
  api_key?: string;         // For API key auth
  username?: string;        // For basic auth
  password?: string;        // For basic auth
  header_name?: string;     // For custom header auth
  custom_headers?: Record<string, string>;
}
```

### 2. Critical Cloudflare Workflows Patterns

#### State Management (CRITICAL)
```typescript
// ✅ CORRECT: Store state in step returns
const questionResults = await step.do('generate_questions', async () => {
  const response = await fetch(apiUrl, requestConfig);
  return await response.json();
});

// Use questionResults in subsequent steps
const documentResult = await step.do('create_documents', async () => {
  // questionResults is persisted and available
  return await processQuestions(questionResults);
});

// ❌ WRONG: Store state in variables (lost on hibernation)
let questionResults = null;
await step.do('generate_questions', async () => {
  questionResults = await fetch(apiUrl); // LOST on workflow hibernation
});
```

#### Step Naming (CRITICAL)
```typescript
// ✅ CORRECT: Deterministic step names
await step.do('generate_algebra_questions', async () => { ... });
await step.do(`process_topic_${topicName}`, async () => { ... }); // If topicName is deterministic

// ❌ WRONG: Non-deterministic names
await step.do(`step_${Date.now()}`, async () => { ... });
await step.do(`process_${Math.random()}`, async () => { ... });
```

#### Parallel Execution (CRITICAL)
```typescript
// ✅ CORRECT: Parallel execution with state collection
const parallelResults = await Promise.all([
  step.do('generate_algebra', async () => { ... }),
  step.do('generate_geometry', async () => { ... }),
  step.do('generate_statistics', async () => { ... })
]);

// ✅ CORRECT: Sequential groups after parallel
const questionResults = await executeParallelSteps(step, topicSteps);
const documentResults = await step.do('create_documents', async () => {
  return await createDocuments(questionResults); // All parallel results available
});
```

### 3. Derivativ-Specific Pipeline Requirements

#### Question Generation Pipeline
```yaml
# derivativ_daily_generation.yaml
name: "derivativ_cambridge_igcse_daily"
schedule: "0 18 * * *"  # 2 AM Singapore Time
timezone: "Asia/Singapore"
api_base: "https://api.derivativ.ai"
auth:
  type: "bearer"
  token: "${DERIVATIV_API_KEY}"

variables:
  topics: ["algebra", "geometry", "statistics", "trigonometry", "probability", "calculus"]
  questions_per_topic: 8
  grade_level: 9
  total_target: 48
  quality_threshold: 0.75

steps:
  # Phase 1: Parallel Question Generation by Topic
  - name: "generate_algebra_questions"
    endpoint: "/api/questions/generate"
    method: "POST"
    parallel_group: "question_generation"
    retry:
      limit: 3
      delay: "10s"
      backoff: "exponential"
      timeout: "5m"
    payload_template: |
      {
        "topic": "algebra",
        "count": {{ questions_per_topic }},
        "grade_level": {{ grade_level }},
        "quality_threshold": {{ quality_threshold }}
      }

  - name: "generate_geometry_questions"
    endpoint: "/api/questions/generate" 
    method: "POST"
    parallel_group: "question_generation"
    retry:
      limit: 3
      delay: "10s" 
      backoff: "exponential"
      timeout: "5m"
    payload_template: |
      {
        "topic": "geometry",
        "count": {{ questions_per_topic }},
        "grade_level": {{ grade_level }},
        "quality_threshold": {{ quality_threshold }}
      }

  # ... similar for other topics

  # Phase 2: Document Generation (depends on all question generation)
  - name: "create_worksheet"
    endpoint: "/api/documents/generate"
    method: "POST"
    depends_on: ["question_generation"]  # Wait for parallel group
    retry:
      limit: 2
      delay: "5s"
      timeout: "10m"
    payload_template: |
      {
        "document_type": "worksheet",
        "question_ids": {{ collect_question_ids(steps.question_generation) | tojson }},
        "detail_level": "medium"
      }

  - name: "create_answer_key"
    endpoint: "/api/documents/generate"
    method: "POST"
    depends_on: ["question_generation"]
    payload_template: |
      {
        "document_type": "answer_key", 
        "question_ids": {{ collect_question_ids(steps.question_generation) | tojson }},
        "include_solutions": true
      }

  - name: "create_teaching_notes"
    endpoint: "/api/documents/generate"
    method: "POST"
    depends_on: ["question_generation"]
    payload_template: |
      {
        "document_type": "teaching_notes",
        "question_ids": {{ collect_question_ids(steps.question_generation) | tojson }},
        "include_pedagogy": true
      }

  # Phase 3: Storage and Export (depends on document creation)
  - name: "store_documents"
    endpoint: "/api/documents/store"
    method: "POST"
    depends_on: ["create_worksheet", "create_answer_key", "create_teaching_notes"]
    payload_template: |
      {
        "documents": [
          {
            "id": "{{ steps.create_worksheet.document_id }}",
            "type": "worksheet",
            "formats": ["pdf", "docx", "html"]
          },
          {
            "id": "{{ steps.create_answer_key.document_id }}",
            "type": "answer_key", 
            "formats": ["pdf", "docx"]
          },
          {
            "id": "{{ steps.create_teaching_notes.document_id }}",
            "type": "teaching_notes",
            "formats": ["pdf", "html"]
          }
        ],
        "create_dual_versions": true
      }

monitoring:
  webhook_url: "https://api.derivativ.ai/webhooks/workflow_complete"
  alerts:
    on_failure: true
    on_long_duration: "30m"
```

## 🚨 Critical Implementation Gotchas

### 1. Cloudflare Workflows Limitations
- **No `cd` or filesystem operations**: All data must be passed via HTTP
- **Hibernation resets memory**: Variables outside steps are lost
- **10,000 step limit per workflow**: Plan step granularity carefully
- **No nested workflows**: Design flat execution plans

### 2. Singapore Timezone Scheduling
```javascript
// CRITICAL: Cron runs in UTC, convert SGT to UTC
// 2 AM SGT = 6 PM UTC previous day
// Cron: "0 18 * * *" for daily 2 AM SGT execution

// In wrangler.toml:
[triggers]
crons = [
  "0 18 * * *"  # 2 AM SGT daily
]
```

### 3. Step Dependency Resolution
```typescript
// Complex dependency graph resolution needed
interface ExecutionPlan {
  phases: ExecutionPhase[];
}

interface ExecutionPhase {
  parallel_groups: StepGroup[];
  sequential_steps: StepConfig[];
}

// Algorithm: Topological sort with parallel group detection
function buildExecutionPlan(steps: StepConfig[]): ExecutionPlan {
  // 1. Build dependency graph
  // 2. Identify parallel groups (steps with same parallel_group)
  // 3. Topological sort with group awareness
  // 4. Return phase-based execution plan
}
```

### 4. Error Handling Strategies
```typescript
// CRITICAL: Comprehensive error handling needed
interface ErrorHandlingStrategy {
  retry_failed_steps: boolean;
  continue_on_non_critical_failure: boolean;
  rollback_on_critical_failure: boolean;
  notification_channels: string[];
}

// Derivativ-specific: Questions are expensive, preserve partial results
await step.do('backup_partial_results', async () => {
  if (hasPartialResults) {
    await saveToDatabase(partialResults);
  }
});
```

## 📊 Performance & Scaling Considerations

### 1. Request Patterns
- **Question Generation**: CPU-intensive, 5-10s per question, highly parallelizable
- **Document Creation**: Template-based, 10-20s per document, moderate parallelization
- **Storage Operations**: I/O-bound, 2-5s per operation, highly parallelizable

### 2. Concurrency Limits
```yaml
# Recommended concurrency settings
max_parallel_questions: 6    # Balance API load vs speed
max_parallel_documents: 3    # Document generation is heavier
max_parallel_storage: 10     # Storage is lightweight

# Total pipeline target: <20 minutes for 48 questions
```

### 3. Rate Limiting Integration
```typescript
// gimme_ai should bypass rate limits for scheduled workflows
const authHeaders = {
  'Authorization': `Bearer ${apiToken}`,
  'X-Gimme-AI-Scheduled': 'true',  // Bypass rate limiting
  'X-Workflow-Instance': instanceId
};
```

## 🔧 Essential gimme_ai Enhancements Needed

### 1. Core Engine
- [ ] **GenericAPIWorkflow class** extending WorkflowEntrypoint
- [ ] **YAML configuration parser** with schema validation
- [ ] **Jinja2 templating engine** for payloads and responses
- [ ] **Dependency graph resolver** for execution planning
- [ ] **Parallel group executor** with proper state collection

### 2. Scheduling & Deployment
- [ ] **Timezone-aware cron parsing** (SGT → UTC conversion)
- [ ] **Enhanced wrangler integration** for workflow deployment
- [ ] **Environment variable management** for API keys
- [ ] **Multi-environment support** (dev/staging/prod)

### 3. Monitoring & Observability
- [ ] **Real-time status API** for workflow monitoring
- [ ] **Webhook notification system** for completion/failure
- [ ] **Performance metrics collection** (step duration, success rates)
- [ ] **Audit logging** for compliance and debugging

### 4. Testing Infrastructure
- [ ] **Unit tests** for all core components
- [ ] **Integration tests** with live API endpoints
- [ ] **End-to-end workflow tests** with realistic data
- [ ] **Performance benchmarking** for scalability validation

## 🎯 Implementation Priority Order

### Phase 1: Core Foundation (Days 1-2)
1. Generic workflow configuration schema
2. Basic step execution with HTTP calling
3. Simple dependency resolution (sequential only)
4. Error handling and retry logic
5. Basic templating support

### Phase 2: Advanced Features (Days 3-4) 
1. Parallel execution with step groups
2. Complex dependency graph resolution
3. Singapore timezone scheduling
4. Comprehensive error recovery
5. Integration with existing gimme_ai CLI

### Phase 3: Production Readiness (Days 5-6)
1. Full Derivativ pipeline implementation
2. Performance optimization and testing
3. Monitoring and alerting setup
4. Documentation and deployment guides
5. End-to-end validation with real data

## 🚀 Success Criteria

### Technical Validation
- [ ] 50 questions generated across 6 topics in <20 minutes
- [ ] 99% workflow success rate with proper error recovery
- [ ] Real-time status monitoring and notifications
- [ ] Zero-downtime deployments and configuration updates

### Derivativ Integration
- [ ] Daily 2 AM SGT execution working reliably
- [ ] Complete document generation pipeline (worksheet + answer key + teaching notes)
- [ ] Proper storage with dual versions (student/teacher)
- [ ] Quality score integration and conditional logic

### Reusability
- [ ] Any REST API callable via YAML configuration
- [ ] Generic enough for non-Derivativ use cases
- [ ] Comprehensive documentation and examples
- [ ] Clean separation of concerns (gimme_ai vs Derivativ-specific)

This guide provides the foundation for implementing a production-ready workflow orchestration system that serves Derivativ's immediate needs while maintaining broad applicability for future projects.