# 🚀 gimme_ai Content Creation Setup Guide

This guide shows you how to set up and test the complete content creation pipeline that transforms text into multi-media content using OpenAI, Replicate, and ElevenLabs.

## 🎯 What You'll Build

Your text input → **OpenAI** (scene analysis) → **OpenAI** (voiceover script) → **Replicate** (images) + **ElevenLabs** (audio) → **R2 Storage** → Final output package

## 📋 Prerequisites

### Required API Keys
```bash
# OpenAI for text processing and scene analysis
export OPENAI_API_KEY="sk-..."

# Replicate for image generation  
export REPLICATE_API_TOKEN="r8_..."

# ElevenLabs for voice synthesis
export ELEVENLABS_API_KEY="..."

# Optional: Cloudflare R2 for asset storage
export R2_ACCESS_KEY_ID="..."
export R2_SECRET_ACCESS_KEY="..."
```

### Installation
```bash
cd gimme_ai
poetry install
```

## 🧪 Testing

### 1. Test Basic Functionality
```bash
# Test without any API keys (uses public APIs)
python test_content_workflow.py
```

### 2. Test OpenAI Integration
```bash
# Set your OpenAI key
export OPENAI_API_KEY="sk-..."
python test_content_workflow.py
```

### 3. Test Full Pipeline
```bash
# Set all API keys
export OPENAI_API_KEY="sk-..."
export REPLICATE_API_TOKEN="r8_..."
export ELEVENLABS_API_KEY="..."

python test_content_workflow.py
```

## 🎬 Example Usage

### Simple Python Script
```python
import asyncio
import yaml
from gimme_ai.config.workflow import WorkflowConfig
from gimme_ai.http.workflow_client import WorkflowHTTPClient
from gimme_ai.workflows.execution_engine import WorkflowExecutionEngine

async def create_content(input_text: str):
    # Load workflow from YAML
    with open('examples/content_creation_workflow.yaml') as f:
        config = yaml.safe_load(f)
    
    # Override input text
    config['variables']['input_text'] = input_text
    
    # Execute workflow
    workflow = WorkflowConfig.from_dict(config)
    client = WorkflowHTTPClient(base_url=workflow.api_base)
    engine = WorkflowExecutionEngine(http_client=client)
    
    result = await engine.execute_workflow(workflow)
    return result

# Usage
result = asyncio.run(create_content("Your story text here..."))
```

### YAML Configuration
```yaml
name: "content_creation_pipeline"
variables:
  input_text: "Your input text here"
  voice_style: "calm and engaging"
  image_style: "photorealistic, cinematic"

steps:
  - name: "analyze_scenes"
    api_base: "https://api.openai.com"
    auth: {type: "bearer", token: "${OPENAI_API_KEY}"}
    extract_fields: {scenes: "choices.0.message.content"}
    
  - name: "generate_images"
    api_base: "https://api.replicate.com"
    auth: {type: "api_key", header_name: "Authorization", api_key: "Token ${REPLICATE_API_TOKEN}"}
    poll_for_completion: true
    download_response: true
    store_in_r2: true
```

## 🏗️ Architecture Patterns

### Pattern 1: Self-Contained Logic (Easy)
gimme_ai handles everything - field extraction, transformations, file handling.

```yaml
steps:
  - name: "openai_scenes"
    extract_fields: {scenes: "choices.0.message.content"}
    response_transform: |
      {{ scenes | parse_scenes | tojson }}
```

### Pattern 2: User-Defined Logic (Flexible)
gimme_ai does API orchestration, you handle transformations in your app.

```python
# gimme_ai returns raw responses
raw_result = await engine.execute_workflow(simple_workflow)

# Your app handles transformation
scenes = MyTransforms.parse_openai_response(raw_result)
enhanced_script = MyTransforms.enhance_voiceover(scenes)
final_output = MyTransforms.compile_assets(scenes, script, images)
```

### Pattern 3: Webhook Integration (Advanced)
gimme_ai calls your webhooks between steps for real-time processing.

```yaml
steps:
  - name: "call_your_transform_api"
    api_base: "https://your-app.com"
    endpoint: "/api/transform/scenes"
    payload_template: |
      {
        "openai_response": {{ previous_step.response }},
        "context": {{ workflow_context }}
      }
```

## 📊 Expected Outputs

### Intermediate Assets
- **Scene Breakdown**: JSON with scene descriptions and image prompts
- **Enhanced Script**: Voiceover-optimized narration text
- **Generated Images**: High-quality scene images (PNG/JPG)
- **Voiceover Audio**: Professional voice synthesis (MP3)

### Final Package
```json
{
  "success": true,
  "outputs": {
    "scenes_breakdown": [...],
    "enhanced_voiceover": "...",
    "generated_image": "https://r2.dev/image.png",
    "generated_audio": "https://r2.dev/audio.mp3"
  },
  "workflow_metadata": {
    "total_scenes": 3,
    "processing_time": "2m 15s",
    "assets_stored": true
  }
}
```

## 🔧 Customization

### Modify Input Processing
```yaml
variables:
  input_text: "{{ your_custom_input }}"
  voice_style: "professional" # or "casual", "energetic"
  image_style: "cartoon" # or "photorealistic", "minimalist"
```

### Add Custom Steps
```yaml
steps:
  # Your custom API integration
  - name: "custom_processing"
    api_base: "https://your-api.com"
    endpoint: "/process"
    depends_on: ["previous_step"]
    payload_template: |
      {
        "data": {{ previous_step.output }},
        "custom_params": {{ your_params }}
      }
```

### Handle Different Response Formats
```yaml
# Extract nested fields from any API response
extract_fields:
  image_url: "output.0"           # Replicate format
  text_content: "choices.0.message.content"  # OpenAI format
  job_id: "id"                    # Generic job format
  custom_field: "data.results.items.0.value"  # Deep nesting
```

## 🚨 Troubleshooting

### Common Issues

1. **API Key Errors**
   ```
   ❌ 401 Unauthorized
   ✅ Check your API key format and permissions
   ```

2. **Polling Timeouts**
   ```yaml
   poll_timeout: "20m"  # Increase for slow image generation
   poll_interval: "10s" # Decrease for faster checking
   ```

3. **Response Parsing**
   ```yaml
   # If extraction fails, get raw response first
   extract_fields: {}  # Empty = return full response
   ```

4. **Rate Limits**
   ```yaml
   retry:
     limit: 5
     delay: "30s"
     backoff: "exponential"
   ```

### Debug Mode
```python
import logging
logging.basicConfig(level=logging.DEBUG)

# This will show all HTTP requests/responses
result = await engine.execute_workflow(workflow)
```

## 📈 Performance Tips

1. **Use Parallel Groups** for independent operations
2. **Set Appropriate Timeouts** for each step type
3. **Store Large Files in R2** instead of passing between steps
4. **Extract Only Needed Fields** to reduce memory usage
5. **Use Polling** for long-running jobs (>30s)

## 🎉 Ready to Go!

Your content creation pipeline is now set up to:
- ✅ Transform any text into visual scenes
- ✅ Generate professional voiceover scripts  
- ✅ Create high-quality images via AI
- ✅ Synthesize natural voice audio
- ✅ Store all assets with organized URLs
- ✅ Handle errors gracefully with retries
- ✅ Scale to complex multi-step workflows

Just set your API keys and run `python test_content_workflow.py` to get started!