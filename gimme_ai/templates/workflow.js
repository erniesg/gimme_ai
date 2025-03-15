// Workflow template for {{ project_name }}
import { WorkflowEntrypoint, WorkflowStep, WorkflowEvent } from 'cloudflare:workers';

type Env = {
  // Add your bindings here
  {{ project_name | upper }}_WORKFLOW: Workflow;
  {% if has_r2_bucket %}
  VIDEO_BUCKET: R2Bucket;
  {% endif %}
  {% for key in required_keys %}
  {{ key }}: string;
  {% endfor %}
};

// User-defined params passed to your workflow
type Params = {
  // Add your parameters here
  requestId: string;
  {% if workflow_params %}
  {% for param in workflow_params %}
  {{ param.name }}: {{ param.type }};
  {% endfor %}
  {% endif %}
};

export class {{ workflow_class_name }} extends WorkflowEntrypoint<Env, Params> {
  async run(event: WorkflowEvent<Params>, step: WorkflowStep) {
    // Access parameters via event.payload
    const requestId = event.payload.requestId;

    // First step - initialization
    const initResult = await step.do('initialization', async () => {
      console.log(`Starting workflow for request ${requestId}`);
      return {
        startTime: new Date().toISOString(),
        requestId: requestId
      };
    });

    {% if has_r2_bucket %}
    // Example step for R2 operations
    const storageResult = await step.do(
      'storage_operations',
      {
        retries: {
          limit: 3,
          delay: '2 seconds',
          backoff: 'exponential',
        },
        timeout: '5 minutes'
      },
      async () => {
        // Example R2 operation
        const bucketObjects = await this.env.VIDEO_BUCKET.list();
        return {
          objectCount: bucketObjects.objects.length,
          objects: bucketObjects.objects.map(obj => obj.key).slice(0, 10) // First 10 objects
        };
      }
    );
    {% endif %}

    // Add your custom workflow steps here

    // Final step - completion
    await step.do('completion', async () => {
      const duration = new Date().getTime() - new Date(initResult.startTime).getTime();
      console.log(`Workflow for request ${requestId} completed in ${duration}ms`);
      return {
        status: 'completed',
        duration: `${duration}ms`
      };
    });
  }
}

// Optional HTTP handler to trigger the workflow
export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const url = new URL(request.url);

    // Check for instance status requests
    const instanceId = url.searchParams.get('instanceId');
    if (instanceId) {
      try {
        const instance = await env.{{ project_name | upper }}_WORKFLOW.get(instanceId);
        const status = await instance.status();
        return Response.json({ status });
      } catch (error) {
        return Response.json({ error: 'Invalid workflow instance ID' }, { status: 404 });
      }
    }

    // Create a new workflow instance
    try {
      // Parse request body for parameters
      let params: Params = { requestId: crypto.randomUUID() };

      if (request.method === 'POST') {
        try {
          const body = await request.json();
          params = { ...params, ...body };
        } catch (e) {
          // If JSON parsing fails, continue with default params
        }
      }

      const instance = await env.{{ project_name | upper }}_WORKFLOW.create(params);

      return Response.json({
        success: true,
        message: 'Workflow started',
        instanceId: instance.id
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
