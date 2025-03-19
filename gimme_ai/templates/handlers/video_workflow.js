/**
 * Video Generation Workflow Handler
 * Provides specialized endpoints and logic for video generation workflows
 */
import * as WorkflowUtils from '../workflow_utils.js';

// Expose the handler to the global scope for access by the main workflow
globalThis.videoWorkflowHandler = {
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

    // Get backend API URL from config
    const apiBaseUrl = env.MODAL_ENDPOINT || workflowConfig.endpoints?.prod || '';

    console.log(`Video workflow request to ${path} (backend: ${apiBaseUrl})`);

    // Handle different endpoints based on path
    if (path === '/workflow' || path === '/generate_video_stream') {
      return await handleGenerateVideo(request, env, workflowClass, apiBaseUrl);
    } else if (path.startsWith('/job_status/')) {
      return await handleJobStatus(request, env, path, apiBaseUrl);
    } else if (path.startsWith('/get_video/')) {
      return await handleGetVideo(request, env, path, apiBaseUrl);
    } else if (path.startsWith('/videos/')) {
      return await handleVideoFile(request, env, path, apiBaseUrl);
    } else if (path.startsWith('/cleanup/')) {
      return await handleCleanup(request, env, path, apiBaseUrl);
    } else {
      // Unrecognized path
      return new Response(JSON.stringify({
        error: 'Unsupported video workflow endpoint',
        path: path
      }), {
        status: 404,
        headers: { 'Content-Type': 'application/json' }
      });
    }
  }
};

/**
 * Handle the generate_video_stream endpoint to start video generation
 */
async function handleGenerateVideo(request, env, workflowClass, apiBaseUrl) {
  try {
    // Parse request body
    const body = await request.json();

    // Validate request
    if (!body.content) {
      return new Response(JSON.stringify({
        error: 'Missing required field: content'
      }), {
        status: 400,
        headers: { 'Content-Type': 'application/json' }
      });
    }

    // Generate a request ID if not provided
    const requestId = body.requestId || crypto.randomUUID();

    console.log(`Starting video generation workflow for request ${requestId} using class: ${workflowClass}`);
    console.log(`Available environment bindings: ${Object.keys(env).join(", ")}`);

    // Create workflow instance
    const workflowInstance = await env[workflowClass].create({
      content: body.content,
      options: body.options || {},
      requestId: requestId,
      apiBaseUrl: apiBaseUrl,
      workflow_type: 'video'  // Explicitly set type
    });

    return new Response(JSON.stringify({
      job_id: workflowInstance.id,
      requestId: requestId,
      status: 'started'
    }), {
      status: 200,
      headers: { 'Content-Type': 'application/json' }
    });
  } catch (error) {
    console.error('Error starting video generation:', error, 'Available bindings:', Object.keys(env));
    return new Response(JSON.stringify({
      error: 'Failed to start video generation',
      message: error.message,
      availableBindings: Object.keys(env)
    }), {
      status: 500,
      headers: { 'Content-Type': 'application/json' }
    });
  }
}

/**
 * Handle the job_status endpoint to check workflow status
 */
async function handleJobStatus(request, env, path, apiBaseUrl) {
  try {
    // Extract job ID from path
    const jobId = path.split('/').pop();
    if (!jobId) {
      return new Response(JSON.stringify({
        error: 'Missing job ID'
      }), {
        status: 400,
        headers: { 'Content-Type': 'application/json' }
      });
    }

    console.log(`Checking job status for ${jobId}`);

    // First, check if this is a workflow job
    try {
      const instance = await env.VIDEOWORKFLOW.get(jobId);
      const status = await instance.status();

      // Convert workflow status to frontend format
      let progress = 0;
      let statusText = 'processing';
      let videoPath = null;
      let logs = [];

      if (status.state === 'completed') {
        statusText = 'complete';
        progress = 100;
        videoPath = status.output?.video_path;
      } else if (status.state === 'failed') {
        statusText = 'failed';
      } else if (status.steps) {
        // Calculate progress based on completed steps
        const totalSteps = status.steps.length;
        const completedSteps = status.steps.filter(s => s.state === 'completed').length;
        progress = Math.floor((completedSteps / totalSteps) * 100);

        // Collect logs from steps
        logs = status.steps.map(s => `${s.name}: ${s.state}`);
      }

      return new Response(JSON.stringify({
        status: statusText,
        progress: progress,
        logs: logs,
        video_path: videoPath
      }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' }
      });

    } catch (error) {
      // If not a workflow job, try checking with the backend
      console.log(`Job ${jobId} not found in workflow, checking backend`);

      // Format the status endpoint
      const statusEndpoint = `${apiBaseUrl}/api/video/job_status/${jobId}`;

      // Call the backend status endpoint
      const response = await fetch(statusEndpoint, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json'
        }
      });

      if (!response.ok) {
        throw new Error(`Backend status check failed: ${response.status}`);
      }

      // Return the status from the backend
      const result = await response.json();
      return new Response(JSON.stringify(result), {
        status: 200,
        headers: { 'Content-Type': 'application/json' }
      });
    }
  } catch (error) {
    console.error('Error checking job status:', error);
    return new Response(JSON.stringify({
      error: 'Failed to check job status',
      message: error.message
    }), {
      status: 500,
      headers: { 'Content-Type': 'application/json' }
    });
  }
}

/**
 * Handle the get_video endpoint to retrieve the generated video
 */
async function handleGetVideo(request, env, path, apiBaseUrl) {
  try {
    // Extract job ID from path
    const jobId = path.split('/').pop();
    if (!jobId) {
      return new Response(JSON.stringify({
        error: 'Missing job ID'
      }), {
        status: 400,
        headers: { 'Content-Type': 'application/json' }
      });
    }

    console.log(`Getting video for job ${jobId}`);

    // Format the video endpoint
    const videoEndpoint = `${apiBaseUrl}/api/video/get_video/${jobId}`;

    // Call the backend video endpoint
    const response = await fetch(videoEndpoint, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json'
      }
    });

    if (!response.ok) {
      return new Response(JSON.stringify({
        error: 'Video not available',
        status: response.status
      }), {
        status: response.status,
        headers: { 'Content-Type': 'application/json' }
      });
    }

    // Return the video info from the backend
    const result = await response.json();
    return new Response(JSON.stringify(result), {
      status: 200,
      headers: { 'Content-Type': 'application/json' }
    });
  } catch (error) {
    console.error('Error getting video:', error);
    return new Response(JSON.stringify({
      error: 'Failed to get video',
      message: error.message
    }), {
      status: 500,
      headers: { 'Content-Type': 'application/json' }
    });
  }
}

/**
 * Handle video file retrieval - acts as a proxy to the backend
 */
async function handleVideoFile(request, env, path, apiBaseUrl) {
  try {
    // Extract filename from path
    const filename = path.split('/').pop();
    if (!filename) {
      return new Response(JSON.stringify({
        error: 'Missing filename'
      }), {
        status: 400,
        headers: { 'Content-Type': 'application/json' }
      });
    }

    console.log(`Retrieving video file: ${filename}`);

    // Proxy request to backend
    const videoUrl = `${apiBaseUrl}/videos/${filename}`;
    const response = await fetch(videoUrl);

    if (!response.ok) {
      return new Response(JSON.stringify({
        error: 'Video not found',
        status: response.status
      }), {
        status: response.status,
        headers: { 'Content-Type': 'application/json' }
      });
    }

    // Return the video data with appropriate headers
    return new Response(response.body, {
      status: 200,
      headers: {
        'Content-Type': response.headers.get('Content-Type') || 'video/mp4',
        'Content-Disposition': `inline; filename="${filename}"`
      }
    });
  } catch (error) {
    console.error('Error retrieving video file:', error);
    return new Response(JSON.stringify({
      error: 'Failed to retrieve video',
      message: error.message
    }), {
      status: 500,
      headers: { 'Content-Type': 'application/json' }
    });
  }
}

/**
 * Handle cleanup endpoint
 */
async function handleCleanup(request, env, path, apiBaseUrl) {
  try {
    // Extract job ID from path
    const jobId = path.split('/').pop();
    if (!jobId) {
      return new Response(JSON.stringify({
        error: 'Missing job ID'
      }), {
        status: 400,
        headers: { 'Content-Type': 'application/json' }
      });
    }

    console.log(`Cleaning up job ${jobId}`);

    // Format the cleanup endpoint
    const cleanupEndpoint = `${apiBaseUrl}/api/video/cleanup/${jobId}`;

    // Call the backend cleanup endpoint
    const response = await fetch(cleanupEndpoint, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json'
      }
    });

    if (!response.ok) {
      return new Response(JSON.stringify({
        error: 'Cleanup failed',
        status: response.status
      }), {
        status: response.status,
        headers: { 'Content-Type': 'application/json' }
      });
    }

    // Return the cleanup result from the backend
    const result = await response.json();
    return new Response(JSON.stringify(result), {
      status: 200,
      headers: { 'Content-Type': 'application/json' }
    });
  } catch (error) {
    console.error('Error cleaning up job:', error);
    return new Response(JSON.stringify({
      error: 'Failed to clean up job',
      message: error.message
    }), {
      status: 500,
      headers: { 'Content-Type': 'application/json' }
    });
  }
}
