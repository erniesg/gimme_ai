// API handlers for the video gateway project

// Handle video generation request
export async function handleGenerateVideoStream(request, env, isAdmin) {
  try {
    const data = await request.json();
    const content = data.content;

    // Log environment variables for debugging
    console.log({
      event: "handlers_generate_video_stream_start",
      modal_endpoint: env.MODAL_ENDPOINT,
      is_admin: isAdmin
    });

    // Ensure Modal endpoint is set
    const modalEndpoint = env.MODAL_ENDPOINT || "https://berlayar-ai--wanx-backend-app-function.modal.run";

    const response = await fetch(`${modalEndpoint}/generate_video_stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ content })
    });

    // Log response status for debugging
    console.log({
      event: "modal_response",
      status: response.status,
      statusText: response.statusText
    });

    if (!response.ok) {
      const errorText = await response.text();
      console.error({
        event: "modal_error",
        status: response.status,
        error: errorText
      });
      throw new Error(`Backend error: ${response.status} - ${errorText}`);
    }

    // Return the response from Modal
    const responseData = await response.json();
    console.log({
      event: "modal_success",
      job_id: responseData.job_id
    });

    return Response.json(responseData);
  } catch (error) {
    console.error({
      event: "handler_error",
      error: error.message,
      stack: error.stack
    });

    return Response.json({
      error: "Failed to start video generation",
      message: error.message
    }, { status: 500 });
  }
}

// Handle streaming logs
export async function handleStreamLogs(request, env, path) {
  const jobId = path.split('/').pop();

  try {
    // Ensure Modal endpoint is set
    const modalEndpoint = env.MODAL_ENDPOINT || "https://berlayar-ai--wanx-backend-app-function.modal.run";
    const modalUrl = `${modalEndpoint}/stream_logs/${jobId}`;

    console.log({
      event: "stream_logs",
      job_id: jobId,
      url: modalUrl
    });

    // Create a fetch request to the Modal endpoint
    const modalResponse = await fetch(modalUrl);

    if (!modalResponse.ok) {
      const errorText = await modalResponse.text();
      console.error({
        event: "stream_logs_error",
        status: modalResponse.status,
        error: errorText
      });
      throw new Error(`Backend error: ${modalResponse.status} - ${errorText}`);
    }

    // Return the streaming response
    return new Response(modalResponse.body, {
      headers: {
        'Content-Type': 'text/event-stream',
        'Cache-Control': 'no-cache',
        'Connection': 'keep-alive',
        'Access-Control-Allow-Origin': '*'
      }
    });
  } catch (error) {
    console.error({
      event: "stream_logs_error",
      job_id: jobId,
      error: error.message,
      stack: error.stack
    });

    return Response.json({
      error: "Failed to stream logs",
      message: error.message
    }, { status: 500 });
  }
}

// Handle job status requests
export async function handleJobStatus(request, env, path) {
  const jobId = path.split('/').pop();

  try {
    // Ensure Modal endpoint is set
    const modalEndpoint = env.MODAL_ENDPOINT || "https://berlayar-ai--wanx-backend-app-function.modal.run";

    console.log({
      event: "job_status",
      job_id: jobId,
      modal_endpoint: modalEndpoint
    });

    // Forward to Modal backend
    const response = await fetch(`${modalEndpoint}/job_status/${jobId}`);

    if (!response.ok) {
      const errorText = await response.text();
      console.error({
        event: "job_status_error",
        status: response.status,
        error: errorText
      });
      throw new Error(`Backend error: ${response.status} - ${errorText}`);
    }

    // Return the response from Modal
    const responseData = await response.json();
    console.log({
      event: "job_status_success",
      job_id: jobId,
      status: responseData.status
    });

    return Response.json(responseData);
  } catch (error) {
    console.error({
      event: "job_status_error",
      job_id: jobId,
      error: error.message,
      stack: error.stack
    });

    return Response.json({
      error: "Failed to get job status",
      message: error.message
    }, { status: 500 });
  }
}

// Handle video retrieval
export async function handleGetVideo(request, env, path, backendUrl) {
  const jobId = path.split('/').pop();

  try {
    // Ensure Modal endpoint is set
    const modalEndpoint = env.MODAL_ENDPOINT || backendUrl || "https://berlayar-ai--wanx-backend-app-function.modal.run";

    console.log({
      event: "get_video",
      job_id: jobId,
      modal_endpoint: modalEndpoint
    });

    // Forward to Modal backend
    const response = await fetch(`${modalEndpoint}/get_video/${jobId}`);

    if (!response.ok) {
      const errorText = await response.text();
      console.error({
        event: "get_video_error",
        status: response.status,
        error: errorText
      });
      throw new Error(`Backend error: ${response.status} - ${errorText}`);
    }

    // Check content type to determine how to handle the response
    const contentType = response.headers.get('content-type');
    console.log({
      event: "get_video_response",
      content_type: contentType
    });

    if (contentType && contentType.includes('application/json')) {
      // Handle JSON response (might contain a URL or error)
      const data = await response.json();
      return Response.json(data);
    } else {
      // Return the video with appropriate headers
      return new Response(response.body, {
        status: response.status,
        headers: {
          'Content-Type': contentType || 'video/mp4',
          'Content-Disposition': response.headers.get('Content-Disposition') || 'inline',
          'Access-Control-Allow-Origin': '*'
        }
      });
    }
  } catch (error) {
    console.error({
      event: "get_video_error",
      job_id: jobId,
      error: error.message,
      stack: error.stack
    });

    return Response.json({
      error: "Failed to get video",
      message: error.message
    }, { status: 500 });
  }
}

// Handle videos by filename
export async function handleVideosByFilename(request, env, path, backendUrl) {
  const filename = path.split('/').pop();

  try {
    // Ensure Modal endpoint is set
    const modalEndpoint = env.MODAL_ENDPOINT || backendUrl || "https://berlayar-ai--wanx-backend-app-function.modal.run";

    console.log({
      event: "get_video_by_filename",
      filename: filename,
      modal_endpoint: modalEndpoint
    });

    // Forward to Modal backend
    const response = await fetch(`${modalEndpoint}/videos/${filename}`, {
      method: request.method // Support both GET and HEAD
    });

    if (!response.ok) {
      console.error({
        event: "get_video_by_filename_error",
        status: response.status,
        filename: filename
      });
      return Response.json({
        error: "Video file not found"
      }, { status: 404 });
    }

    // Return the video with appropriate headers
    return new Response(response.body, {
      status: response.status,
      headers: {
        'Content-Type': response.headers.get('Content-Type') || 'video/mp4',
        'Content-Disposition': response.headers.get('Content-Disposition') || 'inline',
        'Access-Control-Allow-Origin': '*'
      }
    });
  } catch (error) {
    console.error({
      event: "get_video_by_filename_error",
      filename: filename,
      error: error.message,
      stack: error.stack
    });

    return Response.json({
      error: "Failed to get video",
      message: error.message
    }, { status: 500 });
  }
}

// Handle cleanup
export async function handleCleanup(request, env, path, backendUrl) {
  const jobId = path.split('/').pop();

  try {
    // Ensure Modal endpoint is set
    const modalEndpoint = env.MODAL_ENDPOINT || backendUrl || "https://berlayar-ai--wanx-backend-app-function.modal.run";

    console.log({
      event: "cleanup",
      job_id: jobId,
      modal_endpoint: modalEndpoint
    });

    // Call Modal cleanup endpoint
    const response = await fetch(`${modalEndpoint}/cleanup/${jobId}`, {
      method: 'DELETE'
    });

    console.log({
      event: "cleanup_response",
      status: response.status,
      job_id: jobId
    });

    return Response.json({
      status: "success",
      message: `Cleaned up resources for job ${jobId}`
    });
  } catch (error) {
    console.error({
      event: "cleanup_error",
      job_id: jobId,
      error: error.message,
      stack: error.stack
    });

    // Non-critical error, return success anyway
    return Response.json({
      status: "success",
      message: `Attempted cleanup for job ${jobId}`
    });
  }
}

// Main handler that will be called by the worker
export default {
  // This function will be called by the main worker after auth and rate limiting
  async handleRequest(request, env, ctx, { isAdmin, backendUrl, clientIP }) {
    const url = new URL(request.url);
    const path = url.pathname;

    // Log environment variables
    console.log({
      event: "project_handler_called",
      path: path,
      isAdmin: isAdmin,
      backendUrl: backendUrl,
      modalEndpoint: env.MODAL_ENDPOINT,
      request_headers: [...request.headers.keys()]
    });

    // Route to the appropriate handler based on the path
    if (path === "/generate_video_stream") {
      return handleGenerateVideoStream(request, env, isAdmin);
    } else if (path.startsWith("/stream_logs/")) {
      return handleStreamLogs(request, env, path);
    } else if (path.startsWith("/job_status/")) {
      return handleJobStatus(request, env, path);
    } else if (path.startsWith("/get_video/")) {
      return handleGetVideo(request, env, path, backendUrl);
    } else if (path.startsWith("/videos/")) {
      return handleVideosByFilename(request, env, path, backendUrl);
    } else if (path.startsWith("/cleanup/")) {
      return handleCleanup(request, env, path, backendUrl);
    }

    // If no specific handler matches, return a 404
    return new Response(JSON.stringify({
      error: "Not Found",
      message: `No handler found for path: ${path}`
    }), {
      status: 404,
      headers: {
        "Content-Type": "application/json",
        "Access-Control-Allow-Origin": "*"
      }
    });
  }
};
