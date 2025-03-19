// Workflow template for {{ project_name }}
import { WorkflowEntrypoint } from 'cloudflare:workers';
import { NonRetryableError } from 'cloudflare:workflows';
import * as WorkflowUtils from './workflow_utils.js';

// Import handlers based on workflow type
{% if workflow.type == 'api' %}
import apiWorkflowHandler from './handlers/api_workflow.js';
{% elif workflow.type == 'video' %}
import videoWorkflowHandler from './handlers/video_workflow.js';
{% else %}
// Import both handlers for dual mode
import apiWorkflowHandler from './handlers/api_workflow.js';
import videoWorkflowHandler from './handlers/video_workflow.js';
{% endif %}

// Get API base URL from config
const apiBaseUrl = '{{ endpoints.prod }}';  // This will be replaced during template rendering

// Get steps from config
const workflowSteps = {{ workflow.steps | tojson }};  // This will be replaced during template rendering

/**
 * {{ workflow_class_name }} - A workflow for {{ project_name }}
 * Type: {{ workflow.type }}
 */
export class {{ workflow_class_name }} extends WorkflowEntrypoint {
  /**
   * Run the workflow
   */
  async run(event, step) {
    console.log('Event received:', JSON.stringify(event));

    // Initialize workflow first to get the job_id
    const initResult = await step.do("init_step", async () => {
      const response = await fetch(`${apiBaseUrl}/workflow/init`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Auth-Source': 'gimme-ai-gateway',
          'X-Auth-Mode': 'admin'
        },
        body: JSON.stringify({
          // Since we don't have content in the event, we'll use a default or fetch from state
          content: "Debug Modal connection",
          options: {}
        })
      });

      if (!response.ok) {
        const errorText = await response.text();
        console.error('Init step failed:', errorText);
        throw new NonRetryableError(`Failed to initialize workflow: ${errorText}`);
      }

      const result = await response.json();
      console.log('Init step result:', result);
      return result;
    });

    // Store the job_id for subsequent steps
    const jobId = initResult.job_id;
    console.log('Using job_id:', jobId);

    // Generate script
    await step.do("generate_script", async () => {
      const response = await fetch(`${apiBaseUrl}/workflow/generate_script/${jobId}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Auth-Source': 'gimme-ai-gateway',
          'X-Auth-Mode': 'admin'
        }
      });

      if (!response.ok) {
        const errorText = await response.text();
        console.error('Generate script step failed:', errorText);
        throw new NonRetryableError(`Failed to generate script: ${errorText}`);
      }

      const result = await response.json();
      console.log('Generate script result:', result);
      return result;
    });

    // Poll until script generation is complete
    await step.do("poll_script_generation", async () => {
      let attempts = 0;
      const maxAttempts = 60;

      while (attempts < maxAttempts) {
        const response = await fetch(`${apiBaseUrl}/workflow/status/${jobId}?step=script`, {
          headers: {
            'X-Auth-Source': 'gimme-ai-gateway',
            'X-Auth-Mode': 'admin'
          }
        });

        if (!response.ok) {
          console.error('Script status check failed:', await response.text());
          await step.sleep("retry_delay", "5 seconds");
          attempts++;
          continue;
        }

        const status = await response.json();
        console.log('Script status:', status);

        if (status.status === "completed") {
          return status;
        } else if (status.status === "failed") {
          throw new NonRetryableError(`Script generation failed: ${status.error || 'Unknown error'}`);
        }

        await step.sleep("polling_delay", "5 seconds");
        attempts++;
      }

      throw new NonRetryableError("Timeout waiting for script generation");
    });

    // After script is ready, trigger audio and base video in parallel
    await Promise.all([
      step.do("generate_audio", async () => {
        const response = await fetch(`${apiBaseUrl}/workflow/generate_audio/${jobId}`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-Auth-Source': 'gimme-ai-gateway',
            'X-Auth-Mode': 'admin'
          }
        });

        if (!response.ok) {
          throw new NonRetryableError(`Failed to start audio generation: ${await response.text()}`);
        }

        return await response.json();
      }),
      step.do("generate_base_video", async () => {
        const response = await fetch(`${apiBaseUrl}/workflow/generate_base_video/${jobId}`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-Auth-Source': 'gimme-ai-gateway',
            'X-Auth-Mode': 'admin'
          }
        });

        if (!response.ok) {
          throw new NonRetryableError(`Failed to start base video generation: ${await response.text()}`);
        }

        return await response.json();
      })
    ]);

    // Return the final status
    return { jobId, status: "processing" };
  }

  /**
   * Get request body for a step
   */
  getRequestBody(stepName, state) {
    // Determine if this is a video or API workflow based on URL path or payload properties
    const isVideoWorkflow = state.workflow_type === 'video' ||
                             state.content && state.options && !state.instanceId;

    // For the first step, include the full payload
    if (stepName === workflowSteps[0]?.name) {
      // For video workflow, use specific format
      if (isVideoWorkflow) {
        return {
          content: state.content,
          options: state.options || {},
          apiPrefix: state.apiPrefix || '/api/video'
        };
      }
      // For API workflow, pass through all parameters
      return {
        ...state,
        apiPrefix: state.apiPrefix || '/api/video'
      };
    }

    // For subsequent steps, include minimal information
    return {
      requestId: state.requestId,
      job_id: state.job_id || state.instanceId,
      apiPrefix: state.apiPrefix || '/api/video'
    };
  }
}

/**
 * HTTP handler for workflow requests
 */
export const workflowHandler = {
  async fetch(request, env) {
    const url = new URL(request.url);
    const path = url.pathname;

    console.log("Workflow handler received path:", path);

    // Set project name in env for handlers to use
    env.PROJECT_NAME = "{{ project_name }}";

    // Handle workflow API route
    if (path.startsWith('/workflow')) {
      {% if workflow.type in ['api', 'dual'] %}
      // Handle via API workflow handler
      return apiWorkflowHandler.fetch(request, env);
      {% else %}
      // No API workflow in video-only mode
      return new Response(JSON.stringify({
        error: "API workflow not available",
        message: "This deployment only supports video workflows"
      }), {
        status: 400,
        headers: { "Content-Type": "application/json" }
      });
      {% endif %}
    }

    // Handle video workflow routes
    if (path.startsWith('/generate_video_stream') ||
        path.startsWith('/job_status/') ||
        path.startsWith('/get_video/') ||
        path.startsWith('/videos/') ||
        path.startsWith('/cleanup/')) {
      {% if workflow.type in ['video', 'dual'] %}
      // Use video workflow handler
      return videoWorkflowHandler.fetch(request, env);
      {% else %}
      // No video workflow in API-only mode
      return new Response(JSON.stringify({
        error: "Video workflow not available",
        message: "This deployment only supports API workflows"
      }), {
        status: 400,
        headers: { "Content-Type": "application/json" }
      });
      {% endif %}
    }

    // No handler matched
    return new Response(JSON.stringify({
      error: "Workflow endpoint not found",
      path: path,
      type: "{{ workflow.type }}"
    }), {
      status: 404,
      headers: { "Content-Type": "application/json" }
    });
  }
};

/**
 * Default workflow request handler (backwards compatible)
 */
async function defaultWorkflowRequestHandler(request, env, workflowClass, workflowType) {
  const url = new URL(request.url);

  if (!url.pathname.startsWith('/workflow')) {
    return new Response('Not found', { status: 404 });
  }

  // Check for status requests
  const instanceId = url.searchParams.get('instanceId');
  if (instanceId) {
    try {
      const instance = await env[workflowClass].get(instanceId);
      const status = await instance.status();
      return Response.json({ status });
    } catch (error) {
      return Response.json({
        error: 'Invalid instance ID',
        message: String(error)
      }, { status: 404 });
    }
  }

  // Create new workflow instance
  let params = {};
  if (request.method === 'POST') {
    try {
      params = await request.json();
    } catch (e) {
      return Response.json({
        error: 'Invalid JSON',
        message: String(e)
      }, { status: 400 });
    }
  }

  // Add requestId if not provided
  if (!params.requestId) {
    params.requestId = crypto.randomUUID();
  }

  try {
    const instance = await env[workflowClass].create({
      ...params,
      requestId: params.requestId,
      workflow_type: workflowType || 'api'
    });
    return Response.json({
      success: true,
      instanceId: instance.id,
      requestId: params.requestId,
      message: 'Workflow started'
    });
  } catch (error) {
    console.error("Workflow creation error:", error, "Class:", workflowClass, "Available bindings:", Object.keys(env));
    return Response.json({
      success: false,
      error: 'Failed to start workflow',
      message: String(error),
      availableBindings: Object.keys(env)
    }, { status: 500 });
  }
}

// Helper function to parse time strings like "5s" to milliseconds
function parseTimeString(timeStr) {
  const match = timeStr.match(/^(\d+)([smh])$/);
  if (!match) return 5000; // Default to 5 seconds

  const [_, value, unit] = match;
  const numValue = parseInt(value, 10);

  switch (unit) {
    case 's': return numValue * 1000;
    case 'm': return numValue * 60 * 1000;
    case 'h': return numValue * 60 * 60 * 1000;
    default: return 5000;
  }
}
