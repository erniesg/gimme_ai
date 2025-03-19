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

// workflow.js
var WORKFLOW_CONFIG = {
  type: "api",
  steps: [],
  defaults: {
    retry_limit: 3,
    timeout: "5m",
    polling_interval: "5s",
    method: "POST"
  },
  endpoints: {
    dev: "http://localhost:8000",
    prod: "https://berlayar-ai--wanx-backend-app-function.modal.run"
  }
};
var GimmeAiTestWorkflow = class extends WorkflowEntrypoint {
  static {
    __name(this, "GimmeAiTestWorkflow");
  }
  /**
   * Run the workflow
   */
  async run(event, step) {
    console.log("==================== DEBUG START ====================");
    console.log("WORKFLOW RUN STARTED");
    console.log("Full payload:", JSON.stringify(event.payload));
    console.log("Workflow config:", JSON.stringify(WORKFLOW_CONFIG));
    const state = {
      ...event.payload,
      requestId: event.payload.requestId || crypto.randomUUID(),
      startTime: (/* @__PURE__ */ new Date()).toISOString()
    };
    console.log(`Starting workflow: ${state.requestId} (type: ${state.workflow_type || "unknown"})`);
    console.log("Available environment variables:", Object.keys(this.env));
    try {
      console.log("Attempting to execute a test step...");
      const testResult = await step.do(
        "test_step",
        { timeout: "30s" },
        async () => {
          console.log("Inside test step - sleeping for 5 seconds to test timing");
          await new Promise((resolve) => setTimeout(resolve, 5e3));
          console.log("Test step completed");
          return { status: "test_completed" };
        }
      );
      console.log("Test step result:", JSON.stringify(testResult));
    } catch (error) {
      console.error("Error in test step:", error);
    }
    console.log("==================== DEBUG END ====================");
    return {
      status: "debug_completed",
      workflow_type: state.workflow_type,
      requestId: state.requestId,
      config_steps: WORKFLOW_CONFIG.steps ? WORKFLOW_CONFIG.steps.map((s) => s.name) : [],
      debug_time: (/* @__PURE__ */ new Date()).toISOString()
    };
  }
  /**
   * Get request body for a step
   */
  getRequestBody(stepName, state) {
    const isVideoWorkflow = state.workflow_type === "video" || state.content && state.options && !state.instanceId;
    if (stepName === WORKFLOW_CONFIG.steps[0]?.name) {
      if (isVideoWorkflow) {
        return {
          content: state.content,
          options: state.options || {}
        };
      }
      return {
        ...state
      };
    }
    return {
      requestId: state.requestId,
      job_id: state.job_id || state.instanceId
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
      return videoWorkflowHandler.fetch(request, env);
    }
    return new Response(JSON.stringify({
      error: "Workflow endpoint not found",
      path
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
