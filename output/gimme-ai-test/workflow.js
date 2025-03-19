// Workflow template for gimme-ai-test
import { WorkflowEntrypoint } from 'cloudflare:workers';
import * as WorkflowUtils from './workflow_utils.js';

// Import handlers based on workflow type

// Import both handlers for dual mode
import apiWorkflowHandler from './handlers/api_workflow.js';
import videoWorkflowHandler from './handlers/video_workflow.js';


// Workflow configuration - this will be replaced with actual config during deployment
const WORKFLOW_CONFIG = {
  type: "dual", // Always set to dual
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
 * Type: dual
 */
export class GimmeAiTestWorkflow extends WorkflowEntrypoint {
  /**
   * Run the workflow
   */
  async run(event, step) {
    // Initialize state with whatever came in the request
    const state = {
      ...event.payload,
      requestId: event.payload.requestId || crypto.randomUUID(),
      job_id: event.payload.job_id || event.payload.requestId,
      startTime: new Date().toISOString(),
      workflow_type: event.payload.workflow_type || 'dual'
    };

    console.log(`Starting workflow: ${state.requestId}, job_id: ${state.job_id}, type: ${state.workflow_type}`);

    // Get API base URL from environment
    const apiBaseUrl = this.env.MODAL_ENDPOINT ||
      (this.env.ENV === 'development' ? "http://localhost:8000" : "https://berlayar-ai--wanx-backend-app-function.modal.run");

    console.log(`Using API base URL: ${apiBaseUrl}`);

    // Execute workflow steps based on config
    try {
      // Track step results
      const results = {};

      // Initialize workflow with backend
      results.init = await step.do('init_step', { timeout: "30s" }, async () => {
        if (state.workflow_type === 'video') {
          // For video workflow, initialize with content
          const initEndpoint = `${apiBaseUrl}/workflow/init`;
          const response = await fetch(initEndpoint, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              'X-Auth-Source': 'gimme-ai-gateway',
              'X-Auth-Mode': 'admin'
            },
            body: JSON.stringify({
              content: state.content,
              options: state.options || {}
            })
          });

          if (!response.ok) {
            throw new Error(`Failed to initialize workflow: ${await response.text()}`);
          }

          const data = await response.json();
          return {
            job_id: data.job_id,
            status: 'completed'
          };
        } else {
          // For API workflow, just return the request ID
          return {
            job_id: state.requestId,
            status: 'completed'
          };
        }
      });

      // Update state with job_id from initialization
      if (results.init && results.init.job_id) {
        state.job_id = results.init.job_id;
      }

      // Define workflow steps from config
      const workflowSteps = [{"endpoint": "/workflow/init", "method": "POST", "name": "init"}, {"depends_on": ["init"], "endpoint": "/workflow/generate_script/{job_id}", "method": "POST", "name": "generate_script", "poll": {"endpoint": "/workflow/status/{job_id}", "interval": "5s", "max_attempts": 60}}, {"depends_on": ["generate_script"], "endpoint": "/workflow/generate_audio/{job_id}", "method": "POST", "name": "generate_audio", "poll": {"endpoint": "/workflow/status/{job_id}", "interval": "5s", "max_attempts": 60}}, {"depends_on": ["generate_script"], "endpoint": "/workflow/generate_base_video/{job_id}", "method": "POST", "name": "generate_base_video", "poll": {"endpoint": "/workflow/status/{job_id}", "interval": "5s", "max_attempts": 60}}, {"depends_on": ["generate_audio"], "endpoint": "/workflow/generate_captions/{job_id}", "method": "POST", "name": "generate_captions", "poll": {"endpoint": "/workflow/status/{job_id}", "interval": "5s", "max_attempts": 60}}, {"depends_on": ["generate_base_video", "generate_audio", "generate_captions"], "endpoint": "/workflow/combine_final_video/{job_id}", "method": "POST", "name": "combine_final_video", "poll": {"endpoint": "/workflow/status/{job_id}", "interval": "5s", "max_attempts": 60}}];

      // Skip the init step since we've already done it
      const stepsToRun = workflowSteps.filter(step => step.name !== 'init');

      // Process each step in order
      for (const configStep of stepsToRun) {
        // Format the endpoint by replacing {job_id} with the actual job_id
        const endpoint = configStep.endpoint.replace(/{job_id}/g, state.job_id);

        // Check if dependencies are met
        const dependencies = configStep.depends_on || [];
        const dependenciesMet = dependencies.every(dep =>
          results[dep] && results[dep].status === 'completed');

        if (dependenciesMet) {
          console.log(`Executing step: ${configStep.name}`);

          // Call the step endpoint
          results[configStep.name] = await step.do(
            configStep.name,
            { timeout: "10m" }, // 10 minute timeout for each step
            async () => {
              const stepEndpoint = `${apiBaseUrl}${endpoint}`;
              const response = await fetch(stepEndpoint, {
                method: configStep.method || 'POST',
                headers: {
                  'Content-Type': 'application/json',
                  'X-Auth-Source': 'gimme-ai-gateway',
                  'X-Auth-Mode': 'admin'
                }
              });

              if (!response.ok) {
                throw new Error(`Failed to execute step ${configStep.name}: ${await response.text()}`);
              }

              // If polling is configured for this step, use it
              if (configStep.poll) {
                const pollEndpoint = configStep.poll.endpoint.replace(/{job_id}/g, state.job_id);
                const interval = configStep.poll.interval || "5s";
                const maxAttempts = configStep.poll.max_attempts || 60;

                return await WorkflowUtils.pollUntilComplete(
                  step,
                  `${apiBaseUrl}${pollEndpoint}`,
                  state,
                  interval,
                  maxAttempts
                );
              }

              return { status: 'completed' };
            }
          );
        }
      }

      // Return final result
      return {
        job_id: state.job_id,
        workflow_type: state.workflow_type,
        status: "completed",
        steps: Object.keys(results).map(key => ({
          name: key,
          status: results[key]?.status || 'unknown'
        }))
      };
    } catch (error) {
      console.error(`Workflow error: ${error.message}`);
      return {
        job_id: state.job_id,
        workflow_type: state.workflow_type,
        status: "failed",
        error: error.message
      };
    }
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
      
      // Use video workflow handler
      return videoWorkflowHandler.fetch(request, env);
      
    }

    // No handler matched
    return new Response(JSON.stringify({
      error: "Workflow endpoint not found",
      path: path,
      type: "dual"
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