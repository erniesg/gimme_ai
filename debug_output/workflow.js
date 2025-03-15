// Workflow template for gimme-ai-test2
import { WorkflowEntrypoint } from 'cloudflare:workers';

// Define environment bindings
// export type Env = {
//   // Add your bindings here
//   GIMME-AI-TEST2_WORKFLOW: Workflow,
//   
//   MODAL_TOKEN_ID: string,
//   
//   MODAL_TOKEN_SECRET: string,
//   
//   
// };

// User-defined params passed to your workflow
// export type Params = { ... } becomes just a comment
// Params = {
//   // Parameters that can be passed to the workflow
//   requestId?: string,
//   email?: string,
//   metadata?: Record<string, any>,
//   
// };

export class VideoGenerationWorkflow extends WorkflowEntrypoint {
  async run(event, step) {
    // Access parameters via event.payload
    const requestId = event.payload.requestId || crypto.randomUUID();
    const email = event.payload.email;
    const metadata = event.payload.metadata || {};

    // First step - initialization
    const initResult = await step.do('initialization', async () => {
      console.log(`Starting workflow for request ${requestId}`);
      return {
        startTime: new Date().toISOString(),
        requestId: requestId,
        parameters: {
          email,
          metadata
        }
      };
    });

    // Example step with retry logic
    const processResult = await step.do(
      'process_request',
      {
        retries: {
          limit: 3,
          delay: '2 seconds',
          backoff: 'exponential',
        },
        timeout: '1 minute'
      },
      async () => {
        // Simulate some processing
        console.log(`Processing request ${requestId} for ${email || 'unknown user'}`);

        

        // Simulate API call
        const response = await fetch('https://httpbin.org/anything', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            requestId,
            email,
            metadata,
            timestamp: new Date().toISOString()
          })
        });

        const result = await response.json();

        return {
          status: 'processed',
          httpResponse: result,
          processingTime: new Date().toISOString()
        };
      }
    );

    // Add a delay step
    await step.sleep('waiting_period', '5 seconds');

    // Final step - completion
    return await step.do('completion', async () => {
      const startTime = new Date(initResult.startTime).getTime();
      const endTime = new Date().getTime();
      const duration = endTime - startTime;

      console.log(`Workflow for request ${requestId} completed in ${duration}ms`);

      return {
        status: 'completed',
        requestId,
        email,
        duration: `${duration}ms`,
        startTime: initResult.startTime,
        endTime: new Date().toISOString(),
        processResult
      };
    });
  }
}

// Make sure to export the workflow class directly
export { VideoGenerationWorkflow };

// This is the main worker handler - it will be imported by your main worker.js
// We don't export a default fetch handler to avoid conflicts
export const workflowHandler = {
  async fetch(request, env) {
    const url = new URL(request.url);

    // Only handle requests to /workflow path
    if (!url.pathname.startsWith('/workflow')) {
      return new Response('Not found', { status: 404 });
    }

    // Check for instance status requests
    const instanceId = url.searchParams.get('instanceId');
    if (instanceId) {
      try {
        const instance = await env.GIMME-AI-TEST2_WORKFLOW.get(instanceId);
        const status = await instance.status();
        return Response.json({ status });
      } catch (error) {
        return Response.json({
          error: 'Invalid workflow instance ID',
          message: error instanceof Error ? error.message : String(error)
        }, { status: 404 });
      }
    }

    // Create a new workflow instance
    try {
      // Parse request body for parameters
      let params = { requestId: crypto.randomUUID() };

      if (request.method === 'POST') {
        try {
          const body = await request.json();
          params = { ...params, ...body };
        } catch (e) {
          // If JSON parsing fails, continue with default params
          console.error('Failed to parse request body:', e);
        }
      }

      const instance = await env.GIMME-AI-TEST2_WORKFLOW.create(params);

      return Response.json({
        success: true,
        message: 'Workflow started',
        instanceId: instance.id,
        params
      });
    } catch (error) {
      return Response.json({
        success: false,
        error: 'Failed to start workflow',
        message: error instanceof Error ? error.message : String(error)
      }, { status: 500 });
    }
  }
};