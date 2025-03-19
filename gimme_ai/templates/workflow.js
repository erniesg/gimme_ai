// Workflow template for {{ project_name }}
import { WorkflowEntrypoint } from 'cloudflare:workers';
import * as WorkflowUtils from './workflow_utils.js';

// Workflow configuration - this will be replaced with actual config during deployment
const WORKFLOW_CONFIG = {
  steps: [],
  defaults: {
    retry_limit: 3,
    timeout: "5m",
    polling_interval: "5s",
    method: "POST"
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
          // Format the endpoint URL
          const endpoint = WorkflowUtils.formatEndpoint(stepConfig.endpoint, state);

          // Determine method
          const method = stepConfig.method || WORKFLOW_CONFIG.defaults.method || 'POST';

          // Prepare request body
          const body = this.getRequestBody(stepConfig.name, state);

          // Make the API call
          console.log(`Executing step: ${stepConfig.name}, endpoint: ${endpoint}`);

          const response = await fetch(endpoint, {
            method: method,
            headers: WorkflowUtils.getDefaultHeaders(),
            body: method !== 'GET' ? JSON.stringify(body) : undefined
          });

          if (!response.ok) {
            throw new Error(`Step ${stepConfig.name} failed (${response.status}): ${await response.text()}`);
          }

          const result = await response.json();

          // If this step has polling configured, poll until complete
          if (stepConfig.poll) {
            return await WorkflowUtils.pollUntilComplete(
              step,
              stepConfig.poll.endpoint,
              {...state, ...result},
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
      ...state
    };
  }

  /**
   * Get request body for a step
   */
  getRequestBody(stepName, state) {
    // For the first step, include the full payload
    if (stepName === WORKFLOW_CONFIG.steps[0]?.name) {
      return {
        content: state.content,
        options: state.options || {}
      };
    }

    // For subsequent steps, include minimal information
    return {
      requestId: state.requestId,
      job_id: state.job_id
    };
  }
}

/**
 * HTTP handler for workflow requests
 */
export const workflowHandler = {
  async fetch(request, env) {
    const url = new URL(request.url);

    // Only handle /workflow requests
    if (!url.pathname.startsWith('/workflow')) {
      return new Response('Not found', { status: 404 });
    }

    try {
      // Check for status requests
      const instanceId = url.searchParams.get('instanceId');
      if (instanceId) {
        try {
          const instance = await env.{{ project_name | upper | replace('-', '_') }}_WORKFLOW.get(instanceId);
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

      // Create the workflow instance
      const instance = await env.{{ project_name | upper | replace('-', '_') }}_WORKFLOW.create(params);

      // Store the mapping between requestId and instanceId in Durable Storage if available
      if (env.DURABLE_STORAGE && params.requestId) {
        try {
          await env.DURABLE_STORAGE.put(`workflow:${params.requestId}`, instance.id);
          console.log(`Stored workflow mapping: ${params.requestId} -> ${instance.id}`);
        } catch (error) {
          console.error("Failed to store workflow mapping:", error);
        }
      }

      return Response.json({
        success: true,
        message: 'Workflow started',
        instanceId: instance.id,
        requestId: params.requestId
      });
    } catch (error) {
      // Log the full error for debugging
      console.error('Workflow error:', error);

      return Response.json({
        success: false,
        error: 'Workflow error',
        message: String(error)
      }, { status: 500 });
    }
  }
};
