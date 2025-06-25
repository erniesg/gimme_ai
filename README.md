# 🚀 gimme_ai

Secure API gateway for AI services in minutes, not days.

## 🏎️ Quick Start

```bash
# Install
pip install gimme_ai
npm install -g wrangler

# Deploy
gimme-ai init
gimme-ai deploy

# Test your gateway
gimme-ai test-all
```

## ✨ Why gimme_ai?

- **Zero Configuration**: Works out-of-the-box with sensible defaults
- **API Security**: Keep credentials and manage rate limits behind Cloudflare's edge
- **Instant Auth**: Admin access with zero setup
- **AI-Optimized**: Designed specifically for LLM and AI service patterns
- **Workflow Support**: Orchestrate multi-step API processes with dependency management
- **Production Ready**: CORS, error handling, logging, and global CDN included

No complex setup. No infrastructure headaches. Just secure, scalable API gateways.

## 📋 Usage Guide

### Deployment

```bash
# Initialize with interactive setup
gimme-ai init

# Deploy to Cloudflare
gimme-ai deploy
```

### Testing

```bash
# Run all tests (auto-detects URL from your config)
gimme-ai test-all

# Specify URL explicitly if needed
gimme-ai test-all https://your-project.workers.dev

# Test specific components
gimme-ai test-auth
gimme-ai test-rate-limits
gimme-ai test-workflow
```

⚠️ **Note**: Rate limit tests will reset your gateway's limits before and after testing, which could affect ongoing API usage.

### Advanced Options

```bash
# Skip confirmation prompts
gimme-ai test-all --skip-reset-confirm

# Use a specific admin password
gimme-ai test-all --admin-password=your-password

# Verbose output for troubleshooting
gimme-ai test-all --verbose
```

## 🛠️ Features

### Rate Limit Management

Control API usage with built-in rate limiting:

```bash
# Reset rate limits during development
gimme-ai test-rate-limits https://your-project.workers.dev
```

Default rate limits:
- Per-IP: 10 requests/minute
- Global: 100 requests/minute
- Admin users bypass limits with proper authentication

### Workflow Orchestration

**NEW**: Advanced workflow engine for complex multi-API orchestration:

```bash
# Create a new workflow
gimme-ai wf init --name content-pipeline

# Execute workflows
gimme-ai wf execute workflow.yaml --env-file .env

# Validate workflow configurations
gimme-ai wf validate workflow.yaml
```

#### Features:
- **Dependency Management**: Sequential and parallel step execution
- **Multi-API Support**: OpenAI, Replicate, ElevenLabs, and any REST API
- **File Operations**: Upload/download binary files, R2 storage integration
- **Smart Polling**: Automatic job completion detection (Replicate-style)
- **Response Transformation**: Jinja2 templates for data manipulation
- **Error Handling**: Configurable retry logic with exponential backoff
- **Singapore Timezone**: Built-in SGT to UTC conversion for Cloudflare Workers

#### Derivativ Integration:
- **Cambridge IGCSE Templates**: Pre-built workflows for educational content
- **Daily Question Generation**: Automated 50-question generation at 2 AM SGT
- **Multi-Subject Support**: Mathematics, Physics, Chemistry, Biology, English, Computer Science
- **Document Generation**: Automated worksheet and answer key creation

### Security

- API keys stored securely in environment variables
- Admin authentication for privileged operations
- Protection from DDoS and other attacks via Cloudflare

## 🎯 Workflow Examples

### Basic Content Creation Pipeline

```yaml
name: "content_creation_pipeline"
description: "Generate content using OpenAI and ElevenLabs"
api_base: "https://api.openai.com"

steps:
  - name: "generate_script"
    endpoint: "/v1/chat/completions"
    method: "POST"
    auth:
      type: "bearer"
      token: "${OPENAI_API_KEY}"
    payload_template: |
      {
        "model": "gpt-4",
        "messages": [{"role": "user", "content": "Create a 60-second video script about {{ topic }}"}],
        "max_tokens": 500
      }
    extract_fields:
      script: "choices.0.message.content"

  - name: "generate_voiceover"
    api_base: "https://api.elevenlabs.io"
    endpoint: "/v1/text-to-speech/21m00Tcm4TlvDq8ikWAM"
    depends_on: ["generate_script"]
    auth:
      type: "api_key"
      header_name: "xi-api-key"
      api_key: "${ELEVENLABS_API_KEY}"
    payload_template: |
      {"text": "{{ generate_script.script }}"}
    download_response: true
    store_in_r2: true
    r2_bucket: "content-assets"
```

### Derivativ Daily Question Generation

```yaml
name: "derivativ_cambridge_igcse_daily"
description: "Daily Cambridge IGCSE question generation"
schedule: "0 18 * * *"  # 2 AM SGT = 6 PM UTC
timezone: "Asia/Singapore"

variables:
  topics: ["mathematics", "physics", "chemistry"]
  questions_per_topic: 8
  grade_level: 9

steps:
  # Parallel question generation
  - name: "generate_mathematics_questions"
    endpoint: "/api/questions/generate"
    parallel_group: "question_generation"
    payload_template: |
      {
        "subject": "mathematics",
        "count": {{ questions_per_topic }},
        "grade_level": {{ grade_level }}
      }

  # Document creation (depends on all questions)
  - name: "create_worksheet"
    endpoint: "/api/documents/generate"
    depends_on: ["question_generation"]
    payload_template: |
      {
        "document_type": "worksheet",
        "question_ids": {{ steps | collect_question_ids | tojson }}
      }
```

### Singapore Timezone Utilities

```python
from gimme_ai.utils.singapore_scheduler import SingaporeScheduler

# Convert Singapore time to UTC cron
scheduler = SingaporeScheduler()
utc_cron = scheduler.convert_time_to_utc_cron("02:00", "daily")
print(utc_cron)  # "0 18 * * *" (6 PM UTC = 2 AM SGT next day)

# Generate Derivativ schedule
derivativ_cron = scheduler.generate_derivativ_schedule()
print(derivativ_cron)  # "0 18 * * *"
```

### Available Templates

Use pre-built templates for common workflows:

```bash
# List available templates
gimme-ai wf templates

# Generate Derivativ daily workflow
gimme-ai wf generate derivativ_daily \
  --subjects mathematics,physics,chemistry \
  --grade-level 9 \
  --questions-per-topic 8 \
  --output derivativ_workflow.yaml
```

## 🔧 Development

### Running Tests

```bash
# Test new workflow features
python -m pytest tests/unit/utils/test_singapore_scheduler.py -v
python -m pytest tests/unit/config/test_derivativ_templates.py -v

# Test entire workflow system
python -m pytest tests/unit/config/test_workflow_schema.py -v
python -m pytest tests/unit/workflows/test_execution_engine.py -v
```

### Contributing

1. Fork the repository
2. Create a feature branch
3. Add comprehensive tests (TDD approach)
4. Update documentation
5. Submit a pull request

## 📖 License

MIT
