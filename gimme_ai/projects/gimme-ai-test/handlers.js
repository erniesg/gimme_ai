// API handlers for the video gateway project

// Handle video generation request
export async function handleGenerateVideoStream(request, env, isAdmin) {
  try {
    const data = await request.json();
    const content = data.content;

    // Forward to Modal backend
    const response = await fetch(`${env.MODAL_ENDPOINT || "https://gimme-ai-test.modal.run"}/generate_video_stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Modal-Key': env.MODAL_TOKEN_ID,
        'Modal-Secret': env.MODAL_TOKEN_SECRET
      },
      body: JSON.stringify({ content })
    });

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`Backend error: ${response.status} - ${errorText}`);
    }

    // Return the response from Modal
    const responseData = await response.json();

    return Response.json(responseData);
  } catch (error) {
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
    // Create a streaming response that proxies to Modal
    const modalUrl = `${env.MODAL_ENDPOINT || "https://gimme-ai-test.modal.run"}/stream_logs/${jobId}`;

    // Create a fetch request to the Modal endpoint
    const modalResponse = await fetch(modalUrl, {
      headers: {
        'Modal-Key': env.MODAL_TOKEN_ID,
        'Modal-Secret': env.MODAL_TOKEN_SECRET
      }
    });

    if (!modalResponse.ok) {
      throw new Error(`Backend error: ${modalResponse.status}`);
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
    // Forward to Modal backend
    const response = await fetch(`${env.MODAL_ENDPOINT || "https://gimme-ai-test.modal.run"}/job_status/${jobId}`, {
      headers: {
        'Modal-Key': env.MODAL_TOKEN_ID,
        'Modal-Secret': env.MODAL_TOKEN_SECRET
      }
    });

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`Backend error: ${response.status} - ${errorText}`);
    }

    // Return the response from Modal
    const responseData = await response.json();

    return Response.json(responseData);
  } catch (error) {
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
    // Forward to Modal backend
    const response = await fetch(`${env.MODAL_ENDPOINT || backendUrl}/get_video/${jobId}`, {
      headers: {
        'Modal-Key': env.MODAL_TOKEN_ID,
        'Modal-Secret': env.MODAL_TOKEN_SECRET
      }
    });

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`Backend error: ${response.status} - ${errorText}`);
    }

    // Check content type to determine how to handle the response
    const contentType = response.headers.get('content-type');

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
    // Forward to Modal backend
    const response = await fetch(`${env.MODAL_ENDPOINT || backendUrl}/videos/${filename}`, {
      method: request.method, // Support both GET and HEAD
      headers: {
        'Modal-Key': env.MODAL_TOKEN_ID,
        'Modal-Secret': env.MODAL_TOKEN_SECRET
      }
    });

    if (!response.ok) {
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
    // Call Modal cleanup endpoint
    await fetch(`${env.MODAL_ENDPOINT || backendUrl}/cleanup/${jobId}`, {
      method: 'DELETE',
      headers: {
        'Modal-Key': env.MODAL_TOKEN_ID,
        'Modal-Secret': env.MODAL_TOKEN_SECRET
      }
    });

    return Response.json({
      status: "success",
      message: `Cleaned up resources for job ${jobId}`
    });
  } catch (error) {
    // Non-critical error, return success anyway
    return Response.json({
      status: "success",
      message: `Attempted cleanup for job ${jobId}`
    });
  }
}
