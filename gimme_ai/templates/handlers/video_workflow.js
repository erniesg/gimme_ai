/**
 * Video Workflow Handler
 * Orchestrates stepwise video generation workflow based on config
 */

/**
 * Helper function to make authenticated API calls to the backend
 * @param {string} endpoint - API endpoint to call
 * @param {Object} options - Fetch options
 * @param {Request} request - Original request for auth headers
 * @returns {Promise<Response>} - API response
 */
async function callBackendAPI(endpoint, options = {}, request) {
  try {
    // Initialize headers if not provided
    if (!options.headers) {
      options.headers = new Headers();
    }

    // Copy authentication headers from the original request
    const headersToForward = [
      'authorization',
      'x-auth-source',
      'x-auth-mode',
      'x-project-name',
      'modal-key',
      'modal-secret',
      'content-type',
    ];

    headersToForward.forEach(header => {
      const value = request.headers.get(header);
      if (value) {
        options.headers.set(header, value);
      }
    });

    // Always set content type if not already set and we have a body
    if (options.body && !options.headers.get('content-type')) {
      options.headers.set('content-type', 'application/json');
    }

    // Make the API call
    console.log(`Calling backend API: ${endpoint}`);
    const response = await fetch(endpoint, options);

    // Log response status
    console.log(`API response status: ${response.status}`);

    return response;
  } catch (error) {
    console.error(`API call error: ${error.message}`);
    throw error;
  }
}

/**
 * Handle the initial video generation request
 * Creates a workflow instance for tracking the process
 */
async function handleGenerateVideo(request, env, workflowClass, apiBaseUrl) {
  try {
    console.log("Starting video generation process");
    console.log(`API Base URL: ${apiBaseUrl}`);
    console.log(`Workflow class: ${workflowClass}`);
    console.log(`Available env bindings: ${Object.keys(env)}`);

    // Parse the request body
    const body = await request.json();
    const { content, options = {} } = body;

    if (!content) {
      return new Response(JSON.stringify({
        error: "Missing required content field"
      }), {
        status: 400,
        headers: { "Content-Type": "application/json" }
      });
    }

    // Initialize the workflow on the backend using the first step from config: /workflow/init
    const initResponse = await callBackendAPI(
      `${apiBaseUrl}/workflow/init`,
      {
        method: 'POST',
        body: JSON.stringify({ content, options })
      },
      request
    );

    if (!initResponse.ok) {
      const errorText = await initResponse.text();
      console.error(`Failed to initialize workflow: ${errorText}`);
      return new Response(JSON.stringify({
        error: "Failed to initialize workflow",
        details: errorText
      }), {
        status: initResponse.status,
        headers: { "Content-Type": "application/json" }
      });
    }

    // Parse the response to get the job_id
    const initData = await initResponse.json();
    const jobId = initData.job_id;

    console.log(`Workflow initialized with job_id: ${jobId}`);

    // Create a workflow instance to track the progress
    let workflowInstance;
    try {
      if (env[workflowClass]) {
        console.log(`Creating workflow instance with class: ${workflowClass}`);
        workflowInstance = await env[workflowClass].create({
          requestId: jobId,
          job_id: jobId,
          workflow_type: 'video',
          content,
          options
        });

        console.log(`Workflow instance created: ${workflowInstance.id}`);
      } else {
        console.warn(`Workflow class ${workflowClass} not found in environment, using direct API mode`);
      }
    } catch (error) {
      console.error(`Error creating workflow instance: ${error.message}`);
      // Continue without a workflow instance - we'll use the job_id directly
    }

    // Start the first step in the workflow - generate script
    const generateScriptResponse = await callBackendAPI(
      `${apiBaseUrl}/workflow/generate_script/${jobId}`,
      { method: 'POST' },
      request
    );

    // Check if the first step was started successfully
    if (!generateScriptResponse.ok) {
      const errorText = await generateScriptResponse.text();
      console.error(`Failed to start script generation: ${errorText}`);

      // We'll still return success with the job_id since the workflow was initialized
      return new Response(JSON.stringify({
        job_id: jobId,
        workflow_id: workflowInstance ? workflowInstance.id : null,
        status: "initialized",
        warning: "Failed to start script generation automatically"
      }), {
        status: 200,
        headers: { "Content-Type": "application/json" }
      });
    }

    // Return success response with job_id and workflow_id
    return new Response(JSON.stringify({
      job_id: jobId,
      workflow_id: workflowInstance ? workflowInstance.id : null,
      status: "processing",
      message: "Video generation workflow started"
    }), {
      status: 200,
      headers: { "Content-Type": "application/json" }
    });
  } catch (error) {
    console.error(`Error in handleGenerateVideo: ${error.message}`);
    return new Response(JSON.stringify({
      error: "Failed to start video generation",
      message: error.message
    }), {
      status: 500,
      headers: { "Content-Type": "application/json" }
    });
  }
}

/**
 * Handle checking the job status
 */
async function handleJobStatus(request, env, path, apiBaseUrl) {
  try {
    // Extract job_id from path
    const pathParts = path.split('/');
    const jobId = pathParts[pathParts.length - 1];

    if (!jobId) {
      return new Response(JSON.stringify({
        error: "Missing job_id in request path"
      }), {
        status: 400,
        headers: { "Content-Type": "application/json" }
      });
    }

    console.log(`Checking status for job: ${jobId}`);

    // Call backend API to get job status
    const statusResponse = await callBackendAPI(
      `${apiBaseUrl}/workflow/status/${jobId}`,
      { method: 'GET' },
      request
    );

    if (!statusResponse.ok) {
      const errorText = await statusResponse.text();
      console.error(`Failed to get job status: ${statusResponse.status} - ${errorText}`);
      return new Response(JSON.stringify({
        error: "Failed to get job status",
        details: errorText
      }), {
        status: statusResponse.status,
        headers: { "Content-Type": "application/json" }
      });
    }

    // Parse status response
    const statusData = await statusResponse.json();
    console.log(`Job status: ${JSON.stringify(statusData)}`);

    // Auto-advance workflow if a step is completed
    if (statusData.status === "processing") {
      await tryAdvanceWorkflow(jobId, statusData, apiBaseUrl, request);
    }

    // Return the status information
    return new Response(JSON.stringify(statusData), {
      status: 200,
      headers: { "Content-Type": "application/json" }
    });
  } catch (error) {
    console.error(`Error in handleJobStatus: ${error.message}`);
    return new Response(JSON.stringify({
      error: "Failed to check job status",
      message: error.message
    }), {
      status: 500,
      headers: { "Content-Type": "application/json" }
    });
  }
}

/**
 * Handle retrieving the completed video
 */
async function handleGetVideo(request, env, path, apiBaseUrl) {
  try {
    // Extract job_id from path
    const pathParts = path.split('/');
    const jobId = pathParts[pathParts.length - 1];

    if (!jobId) {
      return new Response(JSON.stringify({
        error: "Missing job_id in request path"
      }), {
        status: 400,
        headers: { "Content-Type": "application/json" }
      });
    }

    console.log(`Getting video for job: ${jobId}`);

    // First, check job status to see if video is ready
    const statusResponse = await callBackendAPI(
      `${apiBaseUrl}/workflow/status/${jobId}`,
      { method: 'GET' },
      request
    );

    if (!statusResponse.ok) {
      return new Response(JSON.stringify({
        error: "Failed to check job status",
        details: await statusResponse.text()
      }), {
        status: statusResponse.status,
        headers: { "Content-Type": "application/json" }
      });
    }

    const statusData = await statusResponse.json();

    // Check if the video is ready
    if (statusData.status !== "completed") {
      return new Response(JSON.stringify({
        error: "Video not ready",
        status: statusData.status,
        steps: statusData.steps,
        progress: statusData.progress
      }), {
        status: 400,
        headers: { "Content-Type": "application/json" }
      });
    }

    // Get the video metadata
    const videoFilename = statusData.final_video_details?.filename;
    if (!videoFilename) {
      return new Response(JSON.stringify({
        error: "Video filename not found in status",
        status: statusData
      }), {
        status: 404,
        headers: { "Content-Type": "application/json" }
      });
    }

    // Redirect to video file endpoint
    return new Response(JSON.stringify({
      status: "completed",
      video_url: `${apiBaseUrl}/videos/${videoFilename}`,
      filename: videoFilename
    }), {
      status: 200,
      headers: { "Content-Type": "application/json" }
    });
  } catch (error) {
    console.error(`Error in handleGetVideo: ${error.message}`);
    return new Response(JSON.stringify({
      error: "Failed to get video",
      message: error.message
    }), {
      status: 500,
      headers: { "Content-Type": "application/json" }
    });
  }
}

/**
 * Handle retrieving a video file directly
 */
async function handleVideoFile(request, env, path, apiBaseUrl) {
  try {
    // Extract filename from path
    const pathParts = path.split('/');
    const filename = pathParts[pathParts.length - 1];

    if (!filename) {
      return new Response(JSON.stringify({
        error: "Missing filename in request path"
      }), {
        status: 400,
        headers: { "Content-Type": "application/json" }
      });
    }

    console.log(`Getting video file: ${filename}`);

    // Call backend API to get the video file
    const videoResponse = await callBackendAPI(
      `${apiBaseUrl}/videos/${filename}`,
      { method: 'GET' },
      request
    );

    if (!videoResponse.ok) {
      return new Response(JSON.stringify({
        error: "Failed to get video file",
        details: await videoResponse.text()
      }), {
        status: videoResponse.status,
        headers: { "Content-Type": "application/json" }
      });
    }

    // Return the video file as a streaming response
    const headers = new Headers();
    headers.set('Content-Type', 'video/mp4');
    headers.set('Content-Disposition', `attachment; filename="${filename}"`);

    // Copy relevant headers from backend response
    ['content-length', 'last-modified', 'etag'].forEach(header => {
      const value = videoResponse.headers.get(header);
      if (value) {
        headers.set(header, value);
      }
    });

    return new Response(videoResponse.body, {
      status: 200,
      headers: headers
    });
  } catch (error) {
    console.error(`Error in handleVideoFile: ${error.message}`);
    return new Response(JSON.stringify({
      error: "Failed to get video file",
      message: error.message
    }), {
      status: 500,
      headers: { "Content-Type": "application/json" }
    });
  }
}

/**
 * Handle cleaning up resources for a job
 */
async function handleCleanup(request, env, path, apiBaseUrl) {
  try {
    // Extract job_id from path
    const pathParts = path.split('/');
    const jobId = pathParts[pathParts.length - 1];

    if (!jobId) {
      return new Response(JSON.stringify({
        error: "Missing job_id in request path"
      }), {
        status: 400,
        headers: { "Content-Type": "application/json" }
      });
    }

    console.log(`Cleaning up resources for job: ${jobId}`);

    // Call backend API to cleanup resources
    const cleanupResponse = await callBackendAPI(
      `${apiBaseUrl}/cleanup/${jobId}`,
      { method: 'DELETE' },
      request
    );

    if (!cleanupResponse.ok) {
      return new Response(JSON.stringify({
        error: "Failed to cleanup resources",
        details: await cleanupResponse.text()
      }), {
        status: cleanupResponse.status,
        headers: { "Content-Type": "application/json" }
      });
    }

    // Parse cleanup response
    const cleanupData = await cleanupResponse.json();

    // Return the cleanup status
    return new Response(JSON.stringify(cleanupData), {
      status: 200,
      headers: { "Content-Type": "application/json" }
    });
  } catch (error) {
    console.error(`Error in handleCleanup: ${error.message}`);
    return new Response(JSON.stringify({
      error: "Failed to cleanup resources",
      message: error.message
    }), {
      status: 500,
      headers: { "Content-Type": "application/json" }
    });
  }
}

/**
 * Try to automatically advance the workflow based on current status
 */
async function tryAdvanceWorkflow(jobId, statusData, apiBaseUrl, request) {
  try {
    const steps = statusData.steps;

    // Define the workflow steps from config
    const workflowSteps = [
      {
        name: 'init',
        endpoint: `/workflow/init`,
        dependencies: []
      },
      {
        name: 'generate_script',
        endpoint: `/workflow/generate_script/${jobId}`,
        dependencies: ['init']
      },
      {
        name: 'generate_audio',
        endpoint: `/workflow/generate_audio/${jobId}`,
        dependencies: ['generate_script']
      },
      {
        name: 'generate_base_video',
        endpoint: `/workflow/generate_base_video/${jobId}`,
        dependencies: ['generate_script']
      },
      {
        name: 'generate_captions',
        endpoint: `/workflow/generate_captions/${jobId}`,
        dependencies: ['generate_audio']
      },
      {
        name: 'combine_final_video',
        endpoint: `/workflow/combine_final_video/${jobId}`,
        dependencies: ['generate_base_video', 'generate_audio', 'generate_captions']
      }
    ];

    // Map the steps from the backend to our workflow steps
    const stepStatus = {
      'init': 'completed', // Init is always completed at this point
      'generate_script': steps.script,
      'generate_audio': steps.audio,
      'generate_base_video': steps.base_video,
      'generate_captions': steps.captions,
      'combine_final_video': steps.final_video
    };

    // Check each step to see if it should be started
    for (const step of workflowSteps) {
      // If this step is already completed or processing, skip it
      if (stepStatus[step.name] === 'completed' || stepStatus[step.name] === 'processing') {
        continue;
      }

      // Check if all dependencies are completed
      const allDependenciesMet = step.dependencies.every(dep => stepStatus[dep] === 'completed');

      if (allDependenciesMet) {
        console.log(`Starting step: ${step.name}`);

        // Start this step
        const response = await callBackendAPI(
          `${apiBaseUrl}${step.endpoint}`,
          { method: 'POST' },
          request
        );

        if (response.ok) {
          console.log(`Successfully started step: ${step.name}`);
        } else {
          console.error(`Failed to start step ${step.name}: ${await response.text()}`);
        }

        // Only start one step at a time
        break;
      }
    }
  } catch (error) {
    console.error(`Error in tryAdvanceWorkflow: ${error.message}`);
  }
}

/**
 * Manually advance the workflow to the next step
 */
async function advanceWorkflow(jobId, apiBaseUrl, request) {
  try {
    // Get current status
    const statusResponse = await callBackendAPI(
      `${apiBaseUrl}/workflow/status/${jobId}`,
      { method: 'GET' },
      request
    );

    if (!statusResponse.ok) {
      return new Response(JSON.stringify({
        error: "Failed to get workflow status",
        details: await statusResponse.text()
      }), {
        status: statusResponse.status,
        headers: { "Content-Type": "application/json" }
      });
    }

    const statusData = await statusResponse.json();

    // Try to advance the workflow
    await tryAdvanceWorkflow(jobId, statusData, apiBaseUrl, request);

    // Get updated status
    const updatedStatusResponse = await callBackendAPI(
      `${apiBaseUrl}/workflow/status/${jobId}`,
      { method: 'GET' },
      request
    );

    if (!updatedStatusResponse.ok) {
      return new Response(JSON.stringify({
        error: "Failed to get updated workflow status",
        details: await updatedStatusResponse.text()
      }), {
        status: updatedStatusResponse.status,
        headers: { "Content-Type": "application/json" }
      });
    }

    const updatedStatusData = await updatedStatusResponse.json();

    return new Response(JSON.stringify({
      message: "Workflow advancement attempted",
      success: true,
      status: updatedStatusData
    }), {
      status: 200,
      headers: { "Content-Type": "application/json" }
    });
  } catch (error) {
    console.error(`Error in advanceWorkflow: ${error.message}`);
    return new Response(JSON.stringify({
      error: "Failed to advance workflow",
      message: error.message
    }), {
      status: 500,
      headers: { "Content-Type": "application/json" }
    });
  }
}

/**
 * Utility function to check backend health and debug API paths
 */
async function checkBackendHealth(apiBaseUrl) {
  try {
    console.log("Checking backend health at:", apiBaseUrl);
    const endpoints = [
      "/",
      "/api",
      "/api/video",
      "/api/video/generate"
    ];

    const results = {};

    for (const endpoint of endpoints) {
      try {
        const url = `${apiBaseUrl}${endpoint}`;
        console.log(`Checking endpoint: ${url}`);
        const response = await fetch(url, {
          method: 'GET',
          headers: {
            'Accept': 'application/json'
          }
        });

        results[endpoint] = {
          status: response.status,
          ok: response.ok
        };

        // Try to get content type
        try {
          const contentType = response.headers.get('Content-Type');
          if (contentType) {
            results[endpoint].contentType = contentType;
          }
        } catch (e) {}

      } catch (error) {
        results[endpoint] = {
          error: error.message
        };
      }
    }

    return results;
  } catch (error) {
    console.error("Error in health check:", error);
    return { error: error.message };
  }
}

// Export the handler to make it available
export default {
  /**
   * Handle video workflow requests
   */
  fetch: async (request, env) => {
    const url = new URL(request.url);
    const path = url.pathname;

    // Determine the API base URL from environment or query parameter
    const apiBaseUrl = env.MODAL_ENDPOINT ||
                        (url.hostname.includes('localhost') ? 'http://localhost:8000' :
                         'https://berlayar-ai--wanx-backend-app-function.modal.run');

    // Derive the workflow class name from the project name
    const workflowClass = `${env.PROJECT_NAME || "GIMME_AI_TEST"}`.toUpperCase().replace(/-/g, '_') + "_WORKFLOW";

    console.log(`Video workflow request to ${path}`);
    console.log(`Using API Base URL: ${apiBaseUrl}`);
    console.log(`Using workflow class: ${workflowClass}`);

    // Route to the appropriate handler based on the path
    if (path.startsWith('/generate_video_stream')) {
      return handleGenerateVideo(request, env, workflowClass, apiBaseUrl);
    } else if (path.startsWith('/job_status/')) {
      return handleJobStatus(request, env, path, apiBaseUrl);
    } else if (path.startsWith('/get_video/')) {
      return handleGetVideo(request, env, path, apiBaseUrl);
    } else if (path.startsWith('/videos/')) {
      return handleVideoFile(request, env, path, apiBaseUrl);
    } else if (path.startsWith('/cleanup/')) {
      return handleCleanup(request, env, path, apiBaseUrl);
    } else if (path.startsWith('/advance_workflow/')) {
      const pathParts = path.split('/');
      const jobId = pathParts[pathParts.length - 1];
      return advanceWorkflow(jobId, apiBaseUrl, request);
    } else if (path === '/debug') {
      // Debug endpoint to help with troubleshooting
      return new Response(JSON.stringify({
        apiBaseUrl,
        workflowClass,
        availableBindings: Object.keys(env),
        path,
        healthCheck: await checkBackendHealth(apiBaseUrl)
      }), {
        status: 200,
        headers: { "Content-Type": "application/json" }
      });
    }

    // Default response for unsupported paths
    return new Response(JSON.stringify({
      error: 'Unsupported video workflow endpoint',
      path: path
    }), {
      status: 404,
      headers: { 'Content-Type': 'application/json' }
    });
  }
};
