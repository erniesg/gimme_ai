// Minimal workflow template for {{ project_name }}
import { WorkflowEntrypoint } from 'cloudflare:workers';

// Simple workflow class with minimal functionality
export class VideoGenerationWorkflow extends WorkflowEntrypoint {
  async run(event, step) {
    // Get request ID from payload or generate a new one
    const requestId = event.payload.requestId || crypto.randomUUID();

    // Simple initialization step
    const initResult = await step.do('initialization', async () => {
      return {
        startTime: new Date().toISOString(),
        requestId: requestId
      };
    });

    // Add a delay to simulate processing
    await step.sleep('processing', '3 seconds');

    // Return a simple result
    return await step.do('completion', async () => {
      return {
        status: 'completed',
        requestId: requestId,
        startTime: initResult.startTime,
        endTime: new Date().toISOString(),
        message: 'Workflow completed successfully'
      };
    });
  }
}

// Simple handler for workflow HTTP requests
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
      let params = { requestId: crypto.randomUUID() };
      if (request.method === 'POST') {
        try {
          const body = await request.json();
          params = { ...params, ...body };
        } catch (e) {
          // Continue with default params if JSON parsing fails
        }
      }

      // Create the workflow instance
      const instance = await env.{{ project_name | upper | replace('-', '_') }}_WORKFLOW.create(params);

      return Response.json({
        success: true,
        message: 'Simple workflow started',
        instanceId: instance.id
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
