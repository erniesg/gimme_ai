// Workflow template for gimme-ai-test
import { WorkflowEntrypoint } from 'cloudflare:workers';
import * as WorkflowUtils from './workflow_utils.js';

// Import specialized handlers

import apiWorkflowHandler from './handlers/api_workflow.js';


// Workflow configuration - this will be replaced with actual config during deployment
const WORKFLOW_CONFIG = {
  type: "api",
  steps: [],
  defaults: {
    retry_limit: 3,
    timeout: "5m",
    polling_interval: "5s",
    method: "POST"
  },
  endpoints: {
    dev: "http://localhost:8000",
    prod: "https://berlayar-ai--wanx-backend-app-function.modal.run"
  }
};

/**
 * GimmeAiTestWorkflow - A workflow for gimme-ai-test
 */
export class GimmeAiTestWorkflow extends WorkflowEntrypoint {
  /**
   * Run the workflow
   */
  async run(event, step) {
    // Extensive logging to understand what's happening
    console.log("==================== DEBUG START ====================");
    console.log("WORKFLOW RUN STARTED");
    console.log("Full payload:", JSON.stringify(event.payload));
    console.log("Workflow config:", JSON.stringify(WORKFLOW_CONFIG));

    // Initialize state with whatever came in the request
    const state = {
      ...event.payload,
      requestId: event.payload.requestId || crypto.randomUUID(),
      startTime: new Date().toISOString()
    };

    console.log(`Starting workflow: ${state.requestId} (type: ${state.workflow_type || 'unknown'})`);
    console.log("Available environment variables:", Object.keys(this.env));

    // Execute one explicit step for testing
    try {
      console.log("Attempting to execute a test step...");
      const testResult = await step.do(
        'test_step',
        { timeout: "30s" },
        async () => {
          console.log("Inside test step - sleeping for 5 seconds to test timing");
          await new Promise(resolve => setTimeout(resolve, 5000));
          console.log("Test step completed");
          return { status: "test_completed" };
        }
      );
      console.log("Test step result:", JSON.stringify(testResult));
    } catch (error) {
      console.error("Error in test step:", error);
    }

    // Skip actual implementation for now, just return debug info
    console.log("==================== DEBUG END ====================");

    return {
      status: "debug_completed",
      workflow_type: state.workflow_type,
      requestId: state.requestId,
      config_steps: WORKFLOW_CONFIG.steps ? WORKFLOW_CONFIG.steps.map(s => s.name) : [],
      debug_time: new Date().toISOString()
    };
  }

  /**
   * Get request body for a step
   */
  getRequestBody(stepName, state) {
    // Determine if this is a video or API workflow based on URL path or payload properties
    const isVideoWorkflow = state.workflow_type === 'video' ||
                             state.content && state.options && !state.instanceId;

    // For the first step, include the full payload
    if (stepName === WORKFLOW_CONFIG.steps[0]?.name) {
      // For video workflow, use specific format
      if (isVideoWorkflow) {
        return {
          content: state.content,
          options: state.options || {}
        };
      }
      // For API workflow, pass through all parameters
      return {
        ...state
      };
    }

    // For subsequent steps, include minimal information
    return {
      requestId: state.requestId,
      job_id: state.job_id || state.instanceId
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
    env.PROJECT_NAME = "gimme-ai-test";

    // Handle workflow API route
    if (path.startsWith('/workflow')) {
      // Handle via API workflow handler
      return apiWorkflowHandler.fetch(request, env);
    }

    // Handle video workflow routes
    if (path.startsWith('/generate_video_stream') ||
        path.startsWith('/job_status/') ||
        path.startsWith('/get_video/') ||
        path.startsWith('/videos/') ||
        path.startsWith('/cleanup/')) {
      return videoWorkflowHandler.fetch(request, env);
    }

    // No handler matched
    return new Response(JSON.stringify({
      error: "Workflow endpoint not found",
      path: path
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