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

    // If no specific handler matches, forward to the backend
    return forwardToBackend(request, backendUrl, env, isAdmin);
  }
};

// Helper function to forward requests to the backend
async function forwardToBackend(request, backendUrl, env, isAdmin) {
  try {
    // Clone the request
    const url = new URL(request.url);

    // Create new request to backend
    const backendRequest = new Request(`${backendUrl}${url.pathname}${url.search}`, {
      method: request.method,
      headers: request.headers,
      body: request.body
    });

    // Add auth state to headers
    backendRequest.headers.set('X-Auth-Mode', isAdmin ? 'admin' : 'free');
    backendRequest.headers.set('X-Auth-Source', 'gimme-ai-gateway');

    // Add Modal credentials
    backendRequest.headers.set('Modal-Key', env.MODAL_TOKEN_ID);
    backendRequest.headers.set('Modal-Secret', env.MODAL_TOKEN_SECRET);

    // Forward to backend and return response
    const response = await fetch(backendRequest);

    // Clone the response to add CORS headers
    const corsResponse = new Response(response.body, response);
    corsResponse.headers.set('Access-Control-Allow-Origin', '*');
    corsResponse.headers.set('X-Powered-By', 'Gimme-AI Gateway');

    return corsResponse;
  } catch (error) {
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
