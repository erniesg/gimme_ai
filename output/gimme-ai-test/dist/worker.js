var __defProp = Object.defineProperty;
var __name = (target, value) => __defProp(target, "name", { value, configurable: true });

// durable_objects.js
var IPRateLimiter = class {
  static {
    __name(this, "IPRateLimiter");
  }
  constructor(state, env) {
    this.state = state;
    this.storage = state.storage;
    this.env = env;
    this.limit = 5;
    this.rateWindow = "lifetime";
  }
  async fetch(request) {
    const url = new URL(request.url);
    if (url.pathname === "/reset") {
      await this.storage.delete("count");
      console.log({
        event: "rate_limit_reset",
        type: "per_ip",
        ip: url.hostname,
        timestamp: (/* @__PURE__ */ new Date()).toISOString()
      });
      return new Response(JSON.stringify({
        success: true,
        message: "IP rate limiter reset successfully"
      }), {
        status: 200,
        headers: {
          "Content-Type": "application/json",
          "Access-Control-Allow-Origin": "*"
        }
      });
    }
    const count = await this.storage.get("count") || 0;
    if (count >= this.limit) {
      console.log({
        event: "rate_limit_exceeded",
        type: "per_ip",
        ip: url.hostname,
        count,
        limit: this.limit,
        timestamp: (/* @__PURE__ */ new Date()).toISOString()
      });
      return new Response(JSON.stringify({
        error: "Rate limit exceeded",
        limit: this.limit,
        type: "per_ip",
        window: this.rateWindow,
        message: "You have exceeded the per-IP rate limit for the free tier"
      }), {
        status: 429,
        headers: {
          "Content-Type": "application/json",
          "X-RateLimit-Limit": this.limit,
          "X-RateLimit-Remaining": 0,
          "X-RateLimit-Reset": "n/a",
          "X-RateLimit-Window": this.rateWindow,
          "Access-Control-Allow-Origin": "*",
          "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
          "Access-Control-Allow-Headers": "Content-Type, Authorization"
        }
      });
    }
    await this.storage.put("count", count + 1);
    console.log({
      event: "rate_limit_increment",
      type: "per_ip",
      ip: url.hostname,
      count: count + 1,
      limit: this.limit,
      remaining: this.limit - (count + 1),
      timestamp: (/* @__PURE__ */ new Date()).toISOString()
    });
    return new Response(JSON.stringify({
      success: true,
      used: count + 1,
      remaining: this.limit - (count + 1),
      limit: this.limit,
      window: this.rateWindow,
      type: "per_ip"
    }), {
      status: 200,
      headers: {
        "Content-Type": "application/json",
        "X-RateLimit-Limit": this.limit,
        "X-RateLimit-Remaining": this.limit - (count + 1),
        "X-RateLimit-Window": this.rateWindow,
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type, Authorization"
      }
    });
  }
};
var GlobalRateLimiter = class {
  static {
    __name(this, "GlobalRateLimiter");
  }
  constructor(state, env) {
    this.state = state;
    this.storage = state.storage;
    this.env = env;
    this.limit = 10;
    this.rateWindow = "lifetime";
  }
  async fetch(request) {
    const url = new URL(request.url);
    if (url.pathname === "/reset") {
      await this.storage.delete("count");
      console.log({
        event: "rate_limit_reset",
        type: "global",
        timestamp: (/* @__PURE__ */ new Date()).toISOString()
      });
      return new Response(JSON.stringify({
        success: true,
        message: "Global rate limiter reset successfully"
      }), {
        status: 200,
        headers: {
          "Content-Type": "application/json",
          "Access-Control-Allow-Origin": "*"
        }
      });
    }
    const count = await this.storage.get("count") || 0;
    if (count >= this.limit) {
      console.log({
        event: "rate_limit_exceeded",
        type: "global",
        count,
        limit: this.limit,
        timestamp: (/* @__PURE__ */ new Date()).toISOString()
      });
      return new Response(JSON.stringify({
        error: "Global rate limit exceeded",
        limit: this.limit,
        type: "global",
        window: this.rateWindow,
        message: "The free tier global rate limit has been reached"
      }), {
        status: 429,
        headers: {
          "Content-Type": "application/json",
          "X-RateLimit-Limit": this.limit,
          "X-RateLimit-Remaining": 0,
          "X-RateLimit-Reset": "n/a",
          "X-RateLimit-Window": this.rateWindow,
          "Access-Control-Allow-Origin": "*",
          "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
          "Access-Control-Allow-Headers": "Content-Type, Authorization"
        }
      });
    }
    await this.storage.put("count", count + 1);
    console.log({
      event: "rate_limit_increment",
      type: "global",
      count: count + 1,
      limit: this.limit,
      remaining: this.limit - (count + 1),
      timestamp: (/* @__PURE__ */ new Date()).toISOString()
    });
    return new Response(JSON.stringify({
      success: true,
      used: count + 1,
      remaining: this.limit - (count + 1),
      limit: this.limit,
      window: this.rateWindow,
      type: "global"
    }), {
      status: 200,
      headers: {
        "Content-Type": "application/json",
        "X-RateLimit-Limit": this.limit,
        "X-RateLimit-Remaining": this.limit - (count + 1),
        "X-RateLimit-Window": this.rateWindow,
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type, Authorization"
      }
    });
  }
};

// workflow.js
import { WorkflowEntrypoint } from "cloudflare:workers";
import { NonRetryableError } from "cloudflare:workflows";

// handlers/api_workflow.js
globalThis.apiWorkflowHandler = {
  /**
   * Process workflow-related requests
   * @param {Request} request - The incoming HTTP request
   * @param {Object} env - Environment variables and bindings
   * @param {Object} workflowConfig - Configuration for this workflow
   * @param {string} workflowClass - Cloudflare workflow class name
   * @returns {Response} - HTTP response
   */
  processWorkflowRequest: /* @__PURE__ */ __name(async (request, env, workflowConfig, workflowClass) => {
    const url = new URL(request.url);
    const path = url.pathname;
    console.log(`Simple API workflow request to ${path}`);
    if (!path.startsWith("/workflow")) {
      return new Response("Not found", { status: 404 });
    }
    if (path === "/workflow" && request.method === "POST") {
      return await handleCreateWorkflow(request, env, workflowClass);
    }
    const instanceId = url.searchParams.get("instanceId");
    if (instanceId) {
      return await handleWorkflowStatus(request, env, workflowClass, instanceId);
    }
    return new Response(JSON.stringify({
      error: "Unsupported API workflow endpoint",
      path
    }), {
      status: 404,
      headers: { "Content-Type": "application/json" }
    });
  }, "processWorkflowRequest")
};
async function handleCreateWorkflow(request, env, workflowClass) {
  try {
    const body = await request.json();
    const requestId = body.requestId || crypto.randomUUID();
    console.log(`Starting simple API workflow for request ${requestId}`);
    const workflowInstance = await env[workflowClass].create({
      ...body,
      requestId
    });
    return new Response(JSON.stringify({
      success: true,
      instanceId: workflowInstance.id,
      requestId,
      message: "Workflow started"
    }), {
      status: 200,
      headers: { "Content-Type": "application/json" }
    });
  } catch (error) {
    console.error("Error starting workflow:", error);
    return new Response(JSON.stringify({
      error: "Failed to start workflow",
      message: error.message
    }), {
      status: 500,
      headers: { "Content-Type": "application/json" }
    });
  }
}
__name(handleCreateWorkflow, "handleCreateWorkflow");
async function handleWorkflowStatus(request, env, workflowClass, instanceId) {
  try {
    console.log(`Checking workflow status for ${instanceId}`);
    const instance = await env[workflowClass].get(instanceId);
    const status = await instance.status();
    return new Response(JSON.stringify({
      status
    }), {
      status: 200,
      headers: { "Content-Type": "application/json" }
    });
  } catch (error) {
    console.error("Error checking workflow status:", error);
    return new Response(JSON.stringify({
      error: "Failed to check workflow status",
      message: error.message
    }), {
      status: 500,
      headers: { "Content-Type": "application/json" }
    });
  }
}
__name(handleWorkflowStatus, "handleWorkflowStatus");
var api_workflow_default = {
  fetch: /* @__PURE__ */ __name(async (request, env) => {
    const workflowClass = `${env.PROJECT_NAME || "{{ project_name }}"}`.toUpperCase().replace(/-/g, "_") + "_WORKFLOW";
    return apiWorkflowHandler.processWorkflowRequest(request, env, null, workflowClass);
  }, "fetch")
};

// handlers/video_workflow.js
async function callBackendAPI(endpoint, options = {}, request) {
  try {
    if (!options.headers) {
      options.headers = new Headers();
    }
    const headersToForward = [
      "authorization",
      "x-auth-source",
      "x-auth-mode",
      "x-project-name",
      "modal-key",
      "modal-secret",
      "content-type"
    ];
    headersToForward.forEach((header) => {
      const value = request.headers.get(header);
      if (value) {
        options.headers.set(header, value);
      }
    });
    if (options.body && !options.headers.get("content-type")) {
      options.headers.set("content-type", "application/json");
    }
    console.log(`Calling backend API: ${endpoint}`);
    const response = await fetch(endpoint, options);
    console.log(`API response status: ${response.status}`);
    return response;
  } catch (error) {
    console.error(`API call error: ${error.message}`);
    throw error;
  }
}
__name(callBackendAPI, "callBackendAPI");
async function handleGenerateVideo(request, env, workflowClass, apiBaseUrl2) {
  try {
    console.log("Starting video generation process");
    console.log(`API Base URL: ${apiBaseUrl2}`);
    console.log(`Workflow class: ${workflowClass}`);
    console.log(`Available env bindings: ${Object.keys(env)}`);
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
    const initResponse = await callBackendAPI(
      `${apiBaseUrl2}/workflow/init`,
      {
        method: "POST",
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
    const initData = await initResponse.json();
    const jobId = initData.job_id;
    console.log(`Workflow initialized with job_id: ${jobId}`);
    let workflowInstance;
    try {
      if (env[workflowClass]) {
        console.log(`Creating workflow instance with class: ${workflowClass}`);
        workflowInstance = await env[workflowClass].create({
          requestId: jobId,
          job_id: jobId,
          workflow_type: "video",
          content,
          options
        });
        console.log(`Workflow instance created: ${workflowInstance.id}`);
      } else {
        console.warn(`Workflow class ${workflowClass} not found in environment, using direct API mode`);
      }
    } catch (error) {
      console.error(`Error creating workflow instance: ${error.message}`);
    }
    const generateScriptResponse = await callBackendAPI(
      `${apiBaseUrl2}/workflow/generate_script/${jobId}`,
      { method: "POST" },
      request
    );
    if (!generateScriptResponse.ok) {
      const errorText = await generateScriptResponse.text();
      console.error(`Failed to start script generation: ${errorText}`);
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
__name(handleGenerateVideo, "handleGenerateVideo");
async function handleJobStatus(request, env, path, apiBaseUrl2) {
  try {
    const pathParts = path.split("/");
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
    const statusResponse = await callBackendAPI(
      `${apiBaseUrl2}/workflow/status/${jobId}`,
      { method: "GET" },
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
    const statusData = await statusResponse.json();
    console.log(`Job status: ${JSON.stringify(statusData)}`);
    if (statusData.status === "processing") {
      await tryAdvanceWorkflow(jobId, statusData, apiBaseUrl2, request);
    }
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
__name(handleJobStatus, "handleJobStatus");
async function handleGetVideo(request, env, path, apiBaseUrl2) {
  try {
    const pathParts = path.split("/");
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
    const statusResponse = await callBackendAPI(
      `${apiBaseUrl2}/workflow/status/${jobId}`,
      { method: "GET" },
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
    return new Response(JSON.stringify({
      status: "completed",
      video_url: `${apiBaseUrl2}/videos/${videoFilename}`,
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
__name(handleGetVideo, "handleGetVideo");
async function handleVideoFile(request, env, path, apiBaseUrl2) {
  try {
    const pathParts = path.split("/");
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
    const videoResponse = await callBackendAPI(
      `${apiBaseUrl2}/videos/${filename}`,
      { method: "GET" },
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
    const headers = new Headers();
    headers.set("Content-Type", "video/mp4");
    headers.set("Content-Disposition", `attachment; filename="${filename}"`);
    ["content-length", "last-modified", "etag"].forEach((header) => {
      const value = videoResponse.headers.get(header);
      if (value) {
        headers.set(header, value);
      }
    });
    return new Response(videoResponse.body, {
      status: 200,
      headers
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
__name(handleVideoFile, "handleVideoFile");
async function handleCleanup(request, env, path, apiBaseUrl2) {
  try {
    const pathParts = path.split("/");
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
    const cleanupResponse = await callBackendAPI(
      `${apiBaseUrl2}/cleanup/${jobId}`,
      { method: "DELETE" },
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
    const cleanupData = await cleanupResponse.json();
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
__name(handleCleanup, "handleCleanup");
async function tryAdvanceWorkflow(jobId, statusData, apiBaseUrl2, request) {
  try {
    const steps = statusData.steps;
    const workflowSteps2 = [
      {
        name: "init",
        endpoint: `/workflow/init`,
        dependencies: []
      },
      {
        name: "generate_script",
        endpoint: `/workflow/generate_script/${jobId}`,
        dependencies: ["init"]
      },
      {
        name: "generate_audio",
        endpoint: `/workflow/generate_audio/${jobId}`,
        dependencies: ["generate_script"]
      },
      {
        name: "generate_base_video",
        endpoint: `/workflow/generate_base_video/${jobId}`,
        dependencies: ["generate_script"]
      },
      {
        name: "generate_captions",
        endpoint: `/workflow/generate_captions/${jobId}`,
        dependencies: ["generate_audio"]
      },
      {
        name: "combine_final_video",
        endpoint: `/workflow/combine_final_video/${jobId}`,
        dependencies: ["generate_base_video", "generate_audio", "generate_captions"]
      }
    ];
    const stepStatus = {
      "init": "completed",
      // Init is always completed at this point
      "generate_script": steps.script,
      "generate_audio": steps.audio,
      "generate_base_video": steps.base_video,
      "generate_captions": steps.captions,
      "combine_final_video": steps.final_video
    };
    for (const step of workflowSteps2) {
      if (stepStatus[step.name] === "completed" || stepStatus[step.name] === "processing") {
        continue;
      }
      const allDependenciesMet = step.dependencies.every((dep) => stepStatus[dep] === "completed");
      if (allDependenciesMet) {
        console.log(`Starting step: ${step.name}`);
        const response = await callBackendAPI(
          `${apiBaseUrl2}${step.endpoint}`,
          { method: "POST" },
          request
        );
        if (response.ok) {
          console.log(`Successfully started step: ${step.name}`);
        } else {
          console.error(`Failed to start step ${step.name}: ${await response.text()}`);
        }
        break;
      }
    }
  } catch (error) {
    console.error(`Error in tryAdvanceWorkflow: ${error.message}`);
  }
}
__name(tryAdvanceWorkflow, "tryAdvanceWorkflow");
async function advanceWorkflow(jobId, apiBaseUrl2, request) {
  try {
    const statusResponse = await callBackendAPI(
      `${apiBaseUrl2}/workflow/status/${jobId}`,
      { method: "GET" },
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
    await tryAdvanceWorkflow(jobId, statusData, apiBaseUrl2, request);
    const updatedStatusResponse = await callBackendAPI(
      `${apiBaseUrl2}/workflow/status/${jobId}`,
      { method: "GET" },
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
__name(advanceWorkflow, "advanceWorkflow");
async function checkBackendHealth(apiBaseUrl2) {
  try {
    console.log("Checking backend health at:", apiBaseUrl2);
    const endpoints = [
      "/",
      "/api",
      "/api/video",
      "/api/video/generate"
    ];
    const results = {};
    for (const endpoint of endpoints) {
      try {
        const url = `${apiBaseUrl2}${endpoint}`;
        console.log(`Checking endpoint: ${url}`);
        const response = await fetch(url, {
          method: "GET",
          headers: {
            "Accept": "application/json"
          }
        });
        results[endpoint] = {
          status: response.status,
          ok: response.ok
        };
        try {
          const contentType = response.headers.get("Content-Type");
          if (contentType) {
            results[endpoint].contentType = contentType;
          }
        } catch (e) {
        }
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
__name(checkBackendHealth, "checkBackendHealth");
var video_workflow_default = {
  /**
   * Handle video workflow requests
   */
  fetch: /* @__PURE__ */ __name(async (request, env) => {
    const url = new URL(request.url);
    const path = url.pathname;
    const apiBaseUrl2 = env.MODAL_ENDPOINT || (url.hostname.includes("localhost") ? "http://localhost:8000" : "https://berlayar-ai--wanx-backend-app-function.modal.run");
    const workflowClass = `${env.PROJECT_NAME || "GIMME_AI_TEST"}`.toUpperCase().replace(/-/g, "_") + "_WORKFLOW";
    console.log(`Video workflow request to ${path}`);
    console.log(`Using API Base URL: ${apiBaseUrl2}`);
    console.log(`Using workflow class: ${workflowClass}`);
    if (path.startsWith("/generate_video_stream")) {
      return handleGenerateVideo(request, env, workflowClass, apiBaseUrl2);
    } else if (path.startsWith("/job_status/")) {
      return handleJobStatus(request, env, path, apiBaseUrl2);
    } else if (path.startsWith("/get_video/")) {
      return handleGetVideo(request, env, path, apiBaseUrl2);
    } else if (path.startsWith("/videos/")) {
      return handleVideoFile(request, env, path, apiBaseUrl2);
    } else if (path.startsWith("/cleanup/")) {
      return handleCleanup(request, env, path, apiBaseUrl2);
    } else if (path.startsWith("/advance_workflow/")) {
      const pathParts = path.split("/");
      const jobId = pathParts[pathParts.length - 1];
      return advanceWorkflow(jobId, apiBaseUrl2, request);
    } else if (path === "/debug") {
      return new Response(JSON.stringify({
        apiBaseUrl: apiBaseUrl2,
        workflowClass,
        availableBindings: Object.keys(env),
        path,
        healthCheck: await checkBackendHealth(apiBaseUrl2)
      }), {
        status: 200,
        headers: { "Content-Type": "application/json" }
      });
    }
    return new Response(JSON.stringify({
      error: "Unsupported video workflow endpoint",
      path
    }), {
      status: 404,
      headers: { "Content-Type": "application/json" }
    });
  }, "fetch")
};

// workflow.js
var apiBaseUrl = "https://berlayar-ai--wanx-backend-app-function.modal.run";
var workflowSteps = [{ "config": { "retries": 3, "timeout": "30 seconds" }, "endpoint": "/workflow/init", "method": "POST", "name": "init" }, { "config": { "retries": { "backoff": "exponential", "delay": "5s", "limit": 3 }, "timeout": "2m" }, "depends_on": ["init"], "endpoint": "/workflow/generate_script/{job_id}", "method": "POST", "name": "generate_script", "poll": { "endpoint": "/workflow/status/{job_id}", "interval": "5s", "max_attempts": 60 } }, { "config": { "retries": { "backoff": "exponential", "delay": "5s", "limit": 3 }, "timeout": "5m" }, "depends_on": ["generate_script"], "endpoint": "/workflow/generate_audio/{job_id}", "method": "POST", "name": "generate_audio", "poll": { "endpoint": "/workflow/status/{job_id}", "interval": "5s", "max_attempts": 60 } }, { "config": { "retries": { "backoff": "exponential", "delay": "5s", "limit": 3 }, "timeout": "5m" }, "depends_on": ["generate_script"], "endpoint": "/workflow/generate_base_video/{job_id}", "method": "POST", "name": "generate_base_video", "poll": { "endpoint": "/workflow/status/{job_id}", "interval": "5s", "max_attempts": 60 } }, { "config": { "retries": { "backoff": "exponential", "delay": "5s", "limit": 3 }, "timeout": "2m" }, "depends_on": ["generate_audio"], "endpoint": "/workflow/generate_captions/{job_id}", "method": "POST", "name": "generate_captions", "poll": { "endpoint": "/workflow/status/{job_id}", "interval": "5s", "max_attempts": 60 } }, { "config": { "retries": { "backoff": "exponential", "delay": "5s", "limit": 3 }, "timeout": "5m" }, "depends_on": ["generate_base_video", "generate_audio", "generate_captions"], "endpoint": "/workflow/combine_final_video/{job_id}", "method": "POST", "name": "combine_final_video", "poll": { "endpoint": "/workflow/status/{job_id}", "interval": "5s", "max_attempts": 60 } }];
var GimmeAiTestWorkflow = class extends WorkflowEntrypoint {
  static {
    __name(this, "GimmeAiTestWorkflow");
  }
  /**
   * Run the workflow
   */
  async run(event, step) {
    console.log("Event received:", JSON.stringify(event));
    const initResult = await step.do("init_step", async () => {
      const response = await fetch(`${apiBaseUrl}/workflow/init`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Auth-Source": "gimme-ai-gateway",
          "X-Auth-Mode": "admin"
        },
        body: JSON.stringify({
          // Since we don't have content in the event, we'll use a default or fetch from state
          content: "Debug Modal connection",
          options: {}
        })
      });
      if (!response.ok) {
        const errorText = await response.text();
        console.error("Init step failed:", errorText);
        throw new NonRetryableError(`Failed to initialize workflow: ${errorText}`);
      }
      const result = await response.json();
      console.log("Init step result:", result);
      return result;
    });
    const jobId = initResult.job_id;
    console.log("Using job_id:", jobId);
    await step.do("generate_script", async () => {
      const response = await fetch(`${apiBaseUrl}/workflow/generate_script/${jobId}`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Auth-Source": "gimme-ai-gateway",
          "X-Auth-Mode": "admin"
        }
      });
      if (!response.ok) {
        const errorText = await response.text();
        console.error("Generate script step failed:", errorText);
        throw new NonRetryableError(`Failed to generate script: ${errorText}`);
      }
      const result = await response.json();
      console.log("Generate script result:", result);
      return result;
    });
    await step.do("poll_script_generation", async () => {
      let attempts = 0;
      const maxAttempts = 60;
      while (attempts < maxAttempts) {
        const response = await fetch(`${apiBaseUrl}/workflow/status/${jobId}?step=script`, {
          headers: {
            "X-Auth-Source": "gimme-ai-gateway",
            "X-Auth-Mode": "admin"
          }
        });
        if (!response.ok) {
          console.error("Script status check failed:", await response.text());
          await step.sleep("retry_delay", "5 seconds");
          attempts++;
          continue;
        }
        const status = await response.json();
        console.log("Script status:", status);
        if (status.status === "completed") {
          return status;
        } else if (status.status === "failed") {
          throw new NonRetryableError(`Script generation failed: ${status.error || "Unknown error"}`);
        }
        await step.sleep("polling_delay", "5 seconds");
        attempts++;
      }
      throw new NonRetryableError("Timeout waiting for script generation");
    });
    await Promise.all([
      step.do("generate_audio", async () => {
        const response = await fetch(`${apiBaseUrl}/workflow/generate_audio/${jobId}`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-Auth-Source": "gimme-ai-gateway",
            "X-Auth-Mode": "admin"
          }
        });
        if (!response.ok) {
          throw new NonRetryableError(`Failed to start audio generation: ${await response.text()}`);
        }
        return await response.json();
      }),
      step.do("generate_base_video", async () => {
        const response = await fetch(`${apiBaseUrl}/workflow/generate_base_video/${jobId}`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-Auth-Source": "gimme-ai-gateway",
            "X-Auth-Mode": "admin"
          }
        });
        if (!response.ok) {
          throw new NonRetryableError(`Failed to start base video generation: ${await response.text()}`);
        }
        return await response.json();
      })
    ]);
    return { jobId, status: "processing" };
  }
  /**
   * Get request body for a step
   */
  getRequestBody(stepName, state) {
    const isVideoWorkflow = state.workflow_type === "video" || state.content && state.options && !state.instanceId;
    if (stepName === workflowSteps[0]?.name) {
      if (isVideoWorkflow) {
        return {
          content: state.content,
          options: state.options || {},
          apiPrefix: state.apiPrefix || "/api/video"
        };
      }
      return {
        ...state,
        apiPrefix: state.apiPrefix || "/api/video"
      };
    }
    return {
      requestId: state.requestId,
      job_id: state.job_id || state.instanceId,
      apiPrefix: state.apiPrefix || "/api/video"
    };
  }
};
var workflowHandler = {
  async fetch(request, env) {
    const url = new URL(request.url);
    const path = url.pathname;
    console.log("Workflow handler received path:", path);
    env.PROJECT_NAME = "gimme-ai-test";
    if (path.startsWith("/workflow")) {
      return api_workflow_default.fetch(request, env);
    }
    if (path.startsWith("/generate_video_stream") || path.startsWith("/job_status/") || path.startsWith("/get_video/") || path.startsWith("/videos/") || path.startsWith("/cleanup/")) {
      return video_workflow_default.fetch(request, env);
    }
    return new Response(JSON.stringify({
      error: "Workflow endpoint not found",
      path,
      type: "dual"
    }), {
      status: 404,
      headers: { "Content-Type": "application/json" }
    });
  }
};

// worker.js
var DEV_ENDPOINT = "http://localhost:8000";
var PROD_ENDPOINT = "https://berlayar-ai--wanx-backend-app-function.modal.run";
var ADMIN_PASSWORD_ENV = "GIMME_ADMIN_PASSWORD";
var PROJECT_NAME = "gimme-ai-test";
var projectHandlers = null;
try {
  projectHandlers = await import("./projects/gimme-ai-test/index.js");
  console.log(`Successfully loaded project-specific handlers for ${PROJECT_NAME}`);
} catch (e) {
  console.log(`No project-specific handlers found for ${PROJECT_NAME}: ${e.message}`);
}
async function createJWT(payload, secret) {
  const header = { alg: "HS256", typ: "JWT" };
  const encodedHeader = btoa(JSON.stringify(header));
  const encodedPayload = btoa(JSON.stringify(payload));
  const dataToSign = `${encodedHeader}.${encodedPayload}`;
  const encoder = new TextEncoder();
  const keyData = encoder.encode(secret);
  const key = await crypto.subtle.importKey(
    "raw",
    keyData,
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"]
  );
  const signature = await crypto.subtle.sign(
    "HMAC",
    key,
    encoder.encode(dataToSign)
  );
  const signatureBase64 = btoa(String.fromCharCode(...new Uint8Array(signature)));
  return `${encodedHeader}.${encodedPayload}.${signatureBase64}`;
}
__name(createJWT, "createJWT");
var worker_default = {
  async fetch(request, env, ctx) {
    if (request.method === "OPTIONS") {
      return handleCorsRequest();
    }
    const url = new URL(request.url);
    const path = url.pathname;
    const clientIP = request.headers.get("CF-Connecting-IP") || "127.0.0.1";
    const isDev = url.hostname.includes("localhost") || url.hostname.includes("127.0.0.1");
    const backendUrl = isDev ? DEV_ENDPOINT : PROD_ENDPOINT;
    if (!env.MODAL_ENDPOINT) {
      env.MODAL_ENDPOINT = backendUrl;
    }
    const isAdmin = checkAdminAuth(request, env);
    const specialResponse = await handleSpecialEndpoints(request, env, path, isAdmin, clientIP);
    if (specialResponse) {
      return specialResponse;
    }
    if (!isAdmin) {
      const rateLimitResponse = await checkRateLimits(request, env, clientIP);
      if (rateLimitResponse) {
        return rateLimitResponse;
      }
    }
    if (path.startsWith("/workflow") || path.startsWith("/generate_video_stream") || path.startsWith("/job_status/") || path.startsWith("/get_video/")) {
      try {
        const modifiedRequest = new Request(request);
        if (isAdmin) {
          modifiedRequest.headers.set("X-Auth-Mode", "admin");
          modifiedRequest.headers.set("X-Auth-Source", "gimme-ai-gateway");
          modifiedRequest.headers.set("X-Project-Name", PROJECT_NAME);
          modifiedRequest.headers.set("MODAL_TOKEN_ID", env["MODAL_TOKEN_ID"]);
          modifiedRequest.headers.set("MODAL_TOKEN_SECRET", env["MODAL_TOKEN_SECRET"]);
        } else {
          modifiedRequest.headers.set("X-Auth-Mode", "free");
          modifiedRequest.headers.set("X-Auth-Source", "gimme-ai-gateway");
          modifiedRequest.headers.set("X-Project-Name", PROJECT_NAME);
          modifiedRequest.headers.set("MODAL_TOKEN_ID", env["MODAL_TOKEN_ID"]);
          modifiedRequest.headers.set("MODAL_TOKEN_SECRET", env["MODAL_TOKEN_SECRET"]);
        }
        console.log("Routing to workflow handler:", path);
        console.log("Auth mode:", isAdmin ? "admin" : "free");
        return workflowHandler.fetch(modifiedRequest, env);
      } catch (error) {
        console.error("Error handling workflow request:", error);
        return new Response(JSON.stringify({
          error: "Workflow handler error",
          message: String(error)
        }), {
          status: 500,
          headers: {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*"
          }
        });
      }
    }
    if (projectHandlers && projectHandlers.default && typeof projectHandlers.default.handleRequest === "function") {
      try {
        return await projectHandlers.default.handleRequest(request, env, ctx, {
          isAdmin,
          backendUrl,
          clientIP
        });
      } catch (error) {
        return new Response(JSON.stringify({
          error: "Project handler error",
          message: error.message
        }), {
          status: 500,
          headers: {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*"
          }
        });
      }
    } else {
      return isAdmin ? handleAdminRequest(request, backendUrl, env) : handleFreeRequest(request, backendUrl, env);
    }
  }
};
function checkAdminAuth(request, env) {
  const authHeader = request.headers.get("Authorization") || "";
  if (authHeader.startsWith("Bearer ")) {
    const token = authHeader.substring(7);
    if (token === env[ADMIN_PASSWORD_ENV]) {
      return true;
    } else {
      return false;
    }
  }
  return false;
}
__name(checkAdminAuth, "checkAdminAuth");
async function handleSpecialEndpoints(request, env, path, isAdmin, clientIP) {
  const authHeader = request.headers.get("Authorization") || "";
  if (authHeader.startsWith("Bearer ") && !isAdmin) {
    return new Response(JSON.stringify({
      error: "Authentication failed",
      message: "Invalid authentication token",
      status: 401
    }), {
      status: 401,
      headers: {
        "Content-Type": "application/json",
        "Access-Control-Allow-Origin": "*",
        "WWW-Authenticate": "Bearer"
      }
    });
  }
  if (path === "/status" || path === "/api/status") {
    return handleStatusRequest(env, clientIP, isAdmin);
  }
  if (path === "/api/test") {
    if (isAdmin) {
      return new Response(JSON.stringify({
        success: true,
        message: "Test endpoint successful",
        auth: "admin"
      }), {
        status: 200,
        headers: {
          "Content-Type": "application/json",
          "Access-Control-Allow-Origin": "*"
        }
      });
    } else {
    }
  }
  if (path === "/admin/reset-limits" && isAdmin) {
    try {
      const ipLimiterObj = env.IP_LIMITER.get(env.IP_LIMITER.idFromName(clientIP));
      await ipLimiterObj.fetch(new URL("/reset", request.url));
      const globalLimiterObj = env.GLOBAL_LIMITER.get(env.GLOBAL_LIMITER.idFromName("global"));
      await globalLimiterObj.fetch(new URL("/reset", request.url));
      return new Response(JSON.stringify({
        success: true,
        message: "Rate limits reset successfully"
      }), {
        status: 200,
        headers: {
          "Content-Type": "application/json",
          "Access-Control-Allow-Origin": "*"
        }
      });
    } catch (error) {
      return new Response(JSON.stringify({
        error: "Reset failed",
        message: error.message
      }), {
        status: 500,
        headers: {
          "Content-Type": "application/json",
          "Access-Control-Allow-Origin": "*"
        }
      });
    }
  }
  return null;
}
__name(handleSpecialEndpoints, "handleSpecialEndpoints");
async function checkRateLimits(request, env, clientIP) {
  try {
    const url = new URL(request.url);
    const path = url.pathname;
    const testIP = request.headers.get("X-Test-IP");
    const effectiveIP = testIP || clientIP;
    console.log({
      event: "rate_limit_check",
      client_ip: clientIP,
      effective_ip: effectiveIP,
      path,
      method: request.method,
      timestamp: (/* @__PURE__ */ new Date()).toISOString()
    });
    const ipLimiterObj = env.IP_LIMITER.get(env.IP_LIMITER.idFromName(effectiveIP));
    const ipLimiterResp = await ipLimiterObj.fetch(request.url);
    if (!ipLimiterResp.ok) {
      console.log({
        event: "rate_limit_exceeded",
        limit_type: "per_ip",
        client_ip: effectiveIP,
        path,
        timestamp: (/* @__PURE__ */ new Date()).toISOString()
      });
      return ipLimiterResp;
    }
    const globalLimiterObj = env.GLOBAL_LIMITER.get(env.GLOBAL_LIMITER.idFromName("global"));
    const globalLimiterResp = await globalLimiterObj.fetch(request.url);
    if (!globalLimiterResp.ok) {
      console.log({
        event: "rate_limit_exceeded",
        limit_type: "global",
        client_ip: effectiveIP,
        path,
        timestamp: (/* @__PURE__ */ new Date()).toISOString()
      });
      return globalLimiterResp;
    }
    if (url.pathname === "/api/test") {
      return new Response(JSON.stringify({
        success: true,
        message: "Test endpoint successful",
        auth: "free"
      }), {
        status: 200,
        headers: {
          "Content-Type": "application/json",
          "Access-Control-Allow-Origin": "*"
        }
      });
    }
    return null;
  } catch (error) {
    return new Response(JSON.stringify({
      error: "Gateway error",
      message: "An error occurred checking rate limits",
      details: error.message
    }), {
      status: 500,
      headers: {
        "Content-Type": "application/json",
        "Access-Control-Allow-Origin": "*"
      }
    });
  }
}
__name(checkRateLimits, "checkRateLimits");
async function handleAdminRequest(request, backendUrl, env) {
  try {
    const url = new URL(request.url);
    console.log({
      event: "admin_request",
      modal_endpoint: env.MODAL_ENDPOINT || backendUrl,
      jwt_secret_present: !!env.SHARED_JWT_SECRET
    });
    const backendRequest = new Request(`${env.MODAL_ENDPOINT || backendUrl}${url.pathname}${url.search}`, {
      method: request.method,
      headers: new Headers(request.headers),
      body: request.body
    });
    const jwtPayload = {
      iss: "gimme-ai-gateway",
      sub: PROJECT_NAME,
      exp: Math.floor(Date.now() / 1e3) + 300,
      // 5 minutes expiration
      iat: Math.floor(Date.now() / 1e3),
      mode: "admin",
      jti: crypto.randomUUID()
      // Unique token ID to prevent replay
    };
    const jwt = await createJWT(jwtPayload, env.SHARED_JWT_SECRET);
    backendRequest.headers.set("Authorization", `Bearer ${jwt}`);
    backendRequest.headers.set("X-Auth-Mode", "admin");
    backendRequest.headers.set("X-Auth-Source", "gimme-ai-gateway");
    backendRequest.headers.set("X-Project-Name", PROJECT_NAME);
    backendRequest.headers.set("MODAL_TOKEN_ID", env["MODAL_TOKEN_ID"]);
    backendRequest.headers.set("MODAL_TOKEN_SECRET", env["MODAL_TOKEN_SECRET"]);
    console.log({
      event: "request_headers",
      headers: Object.fromEntries([...backendRequest.headers.entries()])
    });
    const response = await fetch(backendRequest);
    console.log({
      event: "response_received",
      status: response.status,
      statusText: response.statusText
    });
    const corsResponse = new Response(response.body, response);
    corsResponse.headers.set("Access-Control-Allow-Origin", "*");
    corsResponse.headers.set("X-Powered-By", "Gimme-AI Gateway");
    return corsResponse;
  } catch (error) {
    console.error({
      event: "request_error",
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
__name(handleAdminRequest, "handleAdminRequest");
async function handleFreeRequest(request, backendUrl, env) {
  try {
    const url = new URL(request.url);
    const backendRequest = new Request(`${backendUrl}${url.pathname}${url.search}`, {
      method: request.method,
      headers: new Headers(request.headers),
      body: request.body
    });
    const jwtPayload = {
      iss: "gimme-ai-gateway",
      sub: PROJECT_NAME,
      exp: Math.floor(Date.now() / 1e3) + 300,
      // 5 minutes expiration
      iat: Math.floor(Date.now() / 1e3),
      mode: "free",
      jti: crypto.randomUUID()
      // Unique token ID to prevent replay
    };
    const jwt = await createJWT(jwtPayload, env.SHARED_JWT_SECRET);
    backendRequest.headers.set("Authorization", `Bearer ${jwt}`);
    backendRequest.headers.set("X-Auth-Mode", "free");
    backendRequest.headers.set("X-Auth-Source", "gimme-ai-gateway");
    backendRequest.headers.set("X-Project-Name", PROJECT_NAME);
    backendRequest.headers.set("MODAL_TOKEN_ID", env["MODAL_TOKEN_ID"]);
    backendRequest.headers.set("MODAL_TOKEN_SECRET", env["MODAL_TOKEN_SECRET"]);
    const response = await fetch(backendRequest);
    const corsResponse = new Response(response.body, response);
    corsResponse.headers.set("Access-Control-Allow-Origin", "*");
    corsResponse.headers.set("X-Powered-By", "Gimme-AI Gateway");
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
__name(handleFreeRequest, "handleFreeRequest");
function handleCorsRequest() {
  return new Response(null, {
    status: 204,
    headers: {
      "Access-Control-Allow-Origin": "*",
      "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
      "Access-Control-Allow-Headers": "Content-Type, Authorization",
      "Access-Control-Max-Age": "86400"
    }
  });
}
__name(handleCorsRequest, "handleCorsRequest");
function handleStatusRequest(env, clientIP, isAdmin) {
  const mode = isAdmin ? "admin" : "free";
  const limit = isAdmin ? "unlimited" : "5";
  return new Response(JSON.stringify({
    status: "online",
    project: PROJECT_NAME,
    mode,
    rate_limit: limit,
    client_ip: clientIP,
    timestamp: (/* @__PURE__ */ new Date()).toISOString()
  }), {
    status: 200,
    headers: {
      "Content-Type": "application/json",
      "Access-Control-Allow-Origin": "*",
      "X-Powered-By": "Gimme-AI Gateway"
    }
  });
}
__name(handleStatusRequest, "handleStatusRequest");
export {
  GimmeAiTestWorkflow,
  GlobalRateLimiter,
  IPRateLimiter,
  worker_default as default
};
//# sourceMappingURL=worker.js.map
