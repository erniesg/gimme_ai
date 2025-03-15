// Main entry point for the gimme-ai-test project
import { handleGenerateVideoStream, handleStreamLogs, handleJobStatus,
         handleGetVideo, handleVideosByFilename, handleCleanup } from './handlers.js';
import { VideoGenerationWorkflow } from './workflow.js';

// Export the workflow class for registration
export { VideoGenerationWorkflow };

// Main handler that will be called by the worker
export default {
  // This function will be called by the main worker after auth and rate limiting
  async handleRequest(request, env, ctx, { isAdmin, backendUrl, clientIP }) {
    const url = new URL(request.url);
    const path = url.pathname;

    // Log environment variables at the entry point
    console.log({
      event: "project_index_called",
      path: path,
      isAdmin: isAdmin,
      backendUrl: backendUrl,
      modalEndpoint: env.MODAL_ENDPOINT
    });

    // Handle root path - forward to Modal endpoint
    if (path === "/" || path === "") {
      return handleRootPath(request, env, backendUrl, isAdmin);
    }

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

    // If no specific handler matches, return null to let the main worker handle it
    return null;
  }
};

// Handle the root path by forwarding to Modal endpoint
async function handleRootPath(request, env, backendUrl, isAdmin) {
  try {
    console.log({
      event: "handle_root_path",
      backendUrl: backendUrl,
      modalEndpoint: env.MODAL_ENDPOINT,
      isAdmin: isAdmin
    });

    // Ensure Modal endpoint is set
    const modalEndpoint = env.MODAL_ENDPOINT || backendUrl || "https://berlayar-ai--wanx-backend-app-function.modal.run";

    // Create a new headers object and copy all existing headers
    const headers = new Headers();
    for (const [key, value] of request.headers.entries()) {
      headers.set(key, value);
    }

    // Add auth state to headers
    headers.set('X-Auth-Mode', isAdmin ? 'admin' : 'free');
    headers.set('X-Auth-Source', 'gimme-ai-gateway');

    // Add Modal credentials explicitly
    if (env.MODAL_TOKEN_ID) {
      headers.set('Modal-Key', env.MODAL_TOKEN_ID);
    }
    if (env.MODAL_TOKEN_SECRET) {
      headers.set('Modal-Secret', env.MODAL_TOKEN_SECRET);
    }

    // Create new request to backend
    const backendRequest = new Request(`${modalEndpoint}/`, {
      method: request.method,
      headers: headers,
      body: request.body
    });

    console.log({
      event: "root_path_forwarding",
      url: `${modalEndpoint}/`,
      method: request.method
    });

    // Forward to backend and return response
    const response = await fetch(backendRequest);

    console.log({
      event: "root_path_response",
      status: response.status,
      statusText: response.statusText
    });

    // Clone the response to add CORS headers
    const corsResponse = new Response(response.body, response);
    corsResponse.headers.set('Access-Control-Allow-Origin', '*');
    corsResponse.headers.set('X-Powered-By', 'Gimme-AI Gateway');

    return corsResponse;
  } catch (error) {
    console.error({
      event: "root_path_error",
      error: error.message,
      stack: error.stack
    });

    return new Response(JSON.stringify({
      error: "Gateway error",
      message: "Error forwarding request to Modal endpoint",
      details: error.message
    }), {
      status: 502,
      headers: {
        "Content-Type": "application/json",
        "Access-Control-Allow-Origin": "*"
      }
    });
  }
}

// Helper function to forward requests to the backend
async function forwardToBackend(request, backendUrl, env, isAdmin) {
  try {
    // Clone the request
    const url = new URL(request.url);

    // Log that we're forwarding the request with more details
    console.log({
      event: "index_forwardToBackend_start",
      path: url.pathname,
      backendUrl: backendUrl,
      modalEndpoint: env.MODAL_ENDPOINT
    });

    // Create a new headers object and copy all existing headers
    const headers = new Headers();
    for (const [key, value] of request.headers.entries()) {
      headers.set(key, value);
      console.log({
        event: "index_copying_header",
        header: key,
        valueLength: value ? value.length : 0
      });
    }

    // Add auth state to headers
    headers.set('X-Auth-Mode', isAdmin ? 'admin' : 'free');
    headers.set('X-Auth-Source', 'gimme-ai');

    // Create new request to backend
    const backendRequest = new Request(`${backendUrl}${url.pathname}${url.search}`, {
      method: request.method,
      headers: headers,
      body: request.body
    });

    // Log the headers we're sending
    console.log({
      event: "index_backend_request_headers",
      headers: [...backendRequest.headers.keys()]
    });

    // Forward to backend and return response
    console.log({
      event: "index_before_fetch",
      url: `${backendUrl}${url.pathname}${url.search}`,
      method: backendRequest.method
    });

    const response = await fetch(backendRequest);

    // Log the response status
    console.log({
      event: "backend_response",
      status: response.status,
      statusText: response.statusText
    });

    // Clone the response to add CORS headers
    const corsResponse = new Response(response.body, response);
    corsResponse.headers.set('Access-Control-Allow-Origin', '*');
    corsResponse.headers.set('X-Powered-By', 'Gimme-AI');

    return corsResponse;
  } catch (error) {
    console.error({
      event: "forwarding_error",
      error: error.message,
      stack: error.stack
    });

    return new Response(JSON.stringify({
      error: "Gateway error",
      message: "Error forwarding request to backend",
      details: error.message
    }), {
      status: 502,
      headers: {
        "Content-Type": "application/json",
        "Access-Control-Allow-Origin": "*"
      }
    });
  }
}
