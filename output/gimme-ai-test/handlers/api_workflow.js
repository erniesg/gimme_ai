/**
 * Simple API Workflow Handler
 * Provides basic API orchestration for simpler workflows
 */
import * as WorkflowUtils from '../workflow_utils.js';

// Expose the handler to the global scope
globalThis.apiWorkflowHandler = {
  /**
   * Process workflow-related requests
   * @param {Request} request - The incoming HTTP request
   * @param {Object} env - Environment variables and bindings
   * @param {Object} workflowConfig - Configuration for this workflow
   * @param {string} workflowClass - Cloudflare workflow class name
   * @returns {Response} - HTTP response
   */
  processWorkflowRequest: async (request, env, workflowConfig, workflowClass) => {
    const url = new URL(request.url);
    const path = url.pathname;

    console.log(`Simple API workflow request to ${path}`);

    // Only handle /workflow requests
    if (!path.startsWith('/workflow')) {
      return new Response('Not found', { status: 404 });
    }

    // Handle workflow creation
    if (path === '/workflow' && request.method === 'POST') {
      return await handleCreateWorkflow(request, env, workflowClass);
    }

    // Handle workflow status
    const instanceId = url.searchParams.get('instanceId');
    if (instanceId) {
      return await handleWorkflowStatus(request, env, workflowClass, instanceId);
    }

    // Default response for unsupported paths
    return new Response(JSON.stringify({
      error: 'Unsupported API workflow endpoint',
      path: path
    }), {
      status: 404,
      headers: { 'Content-Type': 'application/json' }
    });
  }
};

/**
 * Handle creating a new workflow instance
 */
async function handleCreateWorkflow(request, env, workflowClass) {
  try {
    // Parse request body
    const body = await request.json();

    // Generate a request ID if not provided
    const requestId = body.requestId || crypto.randomUUID();

    console.log(`Starting simple API workflow for request ${requestId}`);

    // Create workflow instance
    const workflowInstance = await env[workflowClass].create({
      ...body,
      requestId: requestId
    });

    return new Response(JSON.stringify({
      success: true,
      instanceId: workflowInstance.id,
      requestId: requestId,
      message: 'Workflow started'
    }), {
      status: 200,
      headers: { 'Content-Type': 'application/json' }
    });
  } catch (error) {
    console.error('Error starting workflow:', error);
    return new Response(JSON.stringify({
      error: 'Failed to start workflow',
      message: error.message
    }), {
      status: 500,
      headers: { 'Content-Type': 'application/json' }
    });
  }
}

/**
 * Handle checking workflow status
 */
async function handleWorkflowStatus(request, env, workflowClass, instanceId) {
  try {
    console.log(`Checking workflow status for ${instanceId}`);

    // Get workflow instance
    const instance = await env[workflowClass].get(instanceId);
    const status = await instance.status();

    return new Response(JSON.stringify({
      status: status
    }), {
      status: 200,
      headers: { 'Content-Type': 'application/json' }
    });
  } catch (error) {
    console.error('Error checking workflow status:', error);
    return new Response(JSON.stringify({
      error: 'Failed to check workflow status',
      message: error.message
    }), {
      status: 500,
      headers: { 'Content-Type': 'application/json' }
    });
  }
}

// Export the handler
export default {
  fetch: async (request, env) => {
    const workflowClass = `${env.PROJECT_NAME || "{{ project_name }}"}`.toUpperCase().replace(/-/g, '_') + "_WORKFLOW";
    return apiWorkflowHandler.processWorkflowRequest(request, env, null, workflowClass);
  }
};
