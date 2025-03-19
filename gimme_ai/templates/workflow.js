// Workflow template for {{ project_name }}
import { WorkflowEntrypoint } from 'cloudflare:workers';
import * as WorkflowUtils from './workflow_utils.js';

// Import specialized handlers
{% if workflow.type == 'video' %}
import './handlers/video_workflow.js';
{% elif workflow.type == 'api' %}
import './handlers/api_workflow.js';
{% elif workflow.type == 'dual' %}
import './handlers/api_workflow.js';
import './handlers/video_workflow.js';
{% elif workflow.type == 'custom' %}
import './handlers/custom_workflow.js';
{% endif %}

// Workflow configuration - this will be replaced with actual config during deployment
const WORKFLOW_CONFIG = {
  type: "{{ workflow.type | default('api') }}",
  steps: [],
  defaults: {
    retry_limit: 3,
    timeout: "5m",
    polling_interval: "5s",
    method: "POST"
  },
  endpoints: {
    dev: "{{ endpoints.dev }}",
    prod: "{{ endpoints.prod }}"
  }
};

/**
 * {{ workflow_class_name }} - A workflow for {{ project_name }}
 */
export class {{ workflow_class_name }} extends WorkflowEntrypoint {
  /**
   * Run the workflow
   */
  async run(event, step) {
    // Initialize state with whatever came in the request
    const state = {
      ...event.payload,
      requestId: event.payload.requestId || crypto.randomUUID(),
      startTime: new Date().toISOString()
    };

    console.log(`Starting workflow: ${state.requestId}`);

    // Execute each step in order
    for (const stepConfig of WORKFLOW_CONFIG.steps) {
      // Check if dependencies are satisfied
      if (stepConfig.depends_on && stepConfig.depends_on.length > 0) {
        for (const dependency of stepConfig.depends_on) {
          if (!state[dependency + '_completed']) {
            throw new Error(`Dependency ${dependency} not completed before ${stepConfig.name}`);
          }
        }
      }

      // Execute the step
      const stepResult = await step.do(
        stepConfig.name,
        {
          retries: stepConfig.retry?.limit || WORKFLOW_CONFIG.defaults.retry_limit || 3,
          timeout: stepConfig.timeout || WORKFLOW_CONFIG.defaults.timeout || "5m"
        },
        async () => {
          // Get API base URL from environment, payload, or config
          const baseUrl = this.env.MODAL_ENDPOINT ||
                          state.apiBaseUrl ||
                          WORKFLOW_CONFIG.endpoints.prod;

          // Get auth mode (admin by default)
          const authMode = 'admin';

          // Format the endpoint URL
          const endpoint = WorkflowUtils.formatEndpoint(stepConfig.endpoint, state, baseUrl);

          // Determine method
          const method = stepConfig.method || WORKFLOW_CONFIG.defaults.method || 'POST';

          // Prepare request body
          const body = this.getRequestBody(stepConfig.name, state);

          // Prepare config for API calls
          const apiConfig = {
            baseUrl,
            headers: WorkflowUtils.getDefaultHeaders({ auth_mode: authMode })
          };

          // Make the API call
          console.log(`Executing step: ${stepConfig.name}, endpoint: ${endpoint}`);

          const response = await fetch(endpoint, {
            method: method,
            headers: apiConfig.headers,
            body: method !== 'GET' ? JSON.stringify(body) : undefined
          });

          if (!response.ok) {
            throw new Error(`Step ${stepConfig.name} failed (${response.status}): ${await response.text()}`);
          }

          let result;
          if (response.headers.get('Content-Type')?.includes('application/json')) {
            result = await response.json();
          } else {
            result = { text: await response.text() };
          }

          // If this step has polling configured, poll until complete
          if (stepConfig.poll) {
            return await WorkflowUtils.pollUntilComplete(
              step,
              stepConfig.poll.endpoint,
              {...state, ...result},
              apiConfig,
              stepConfig.poll.interval || WORKFLOW_CONFIG.defaults.polling_interval || "5s",
              stepConfig.poll.max_attempts || 60
            );
          }

          return result;
        }
      );

      // Update state with step result
      state[stepConfig.name + '_result'] = stepResult;
      state[stepConfig.name + '_completed'] = true;

      // Add any specific properties from the result to the state
      if (stepResult.job_id && !state.job_id) {
        state.job_id = stepResult.job_id;
      }

      console.log(`Completed step: ${stepConfig.name}`);
    }

    // Calculate duration
    const endTime = new Date();
    const duration = endTime.getTime() - new Date(state.startTime).getTime();

    // Return the final state
    return {
      status: "completed",
      requestId: state.requestId,
      duration: `${duration}ms`,
      output: state
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
    const workflowBinding = "{{ project_name | upper | replace('-', '_') }}_WORKFLOW";

    try {
      console.log(`Processing workflow request: ${url.pathname}`);
      console.log(`Available env bindings: ${Object.keys(env).join(", ")}`);

      // Add workflow_type to the request based on URL path
      let handler;
      let workflowType;

      if (url.pathname === '/generate_video_stream' || url.pathname.startsWith('/job_status/')) {
        handler = globalThis.videoWorkflowHandler;
        workflowType = 'video';
      } else if (url.pathname.startsWith('/workflow')) {
        handler = globalThis.apiWorkflowHandler;
        workflowType = 'api';
      }

      // Process the request using the handler
      if (handler && handler.processWorkflowRequest) {
        return await handler.processWorkflowRequest(
          request,
          env,
          WORKFLOW_CONFIG,
          workflowBinding,
          workflowType
        );
      }

      // Fall back to default processing
      return await defaultWorkflowRequestHandler(request, env, workflowBinding, workflowType);
    } catch (error) {
      console.error('Workflow error:', error, 'Available bindings:', Object.keys(env));
      return Response.json({
        success: false,
        error: 'Workflow error',
        message: String(error),
        availableBindings: Object.keys(env)
      }, { status: 500 });
    }
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
