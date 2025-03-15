// Main Worker Script for API Gateway
// Handles authentication, rate limiting, and request forwarding
import { IPRateLimiter, GlobalRateLimiter } from './durable_objects.js';
import { VideoGenerationWorkflow } from './workflow.js';

{% if workflow and workflow.enabled %}
// Export the workflow class to make it available to the runtime
export { VideoGenerationWorkflow };
{% endif %}

// Configuration
const DEV_ENDPOINT = "{{ dev_endpoint }}";
const PROD_ENDPOINT = "{{ prod_endpoint }}";
const ADMIN_PASSWORD_ENV = "{{ admin_password_env }}";
const PROJECT_NAME = "{{ project_name }}";

// Required API Keys - these will be available in the worker environment:
{% for key in required_keys %}
// - {{ key }}
{% endfor %}

// Try to import project-specific handlers if they exist
let projectHandlers = null;
try {
  projectHandlers = await import('./projects/{{ project_name }}/index.js');
  console.log(`Successfully loaded project-specific handlers for ${PROJECT_NAME}`);
} catch (e) {
  console.log(`No project-specific handlers found for ${PROJECT_NAME}: ${e.message}`);
}

// Add this JWT utility function at the top of your file
async function createJWT(payload, secret) {
  // Create the parts of the JWT
  const header = { alg: "HS256", typ: "JWT" };

  // Base64 encode the header and payload
  const encodedHeader = btoa(JSON.stringify(header));
  const encodedPayload = btoa(JSON.stringify(payload));

  // Create the data to sign
  const dataToSign = `${encodedHeader}.${encodedPayload}`;

  // Convert secret to a key
  const encoder = new TextEncoder();
  const keyData = encoder.encode(secret);
  const key = await crypto.subtle.importKey(
    "raw", keyData, { name: "HMAC", hash: "SHA-256" }, false, ["sign"]
  );

  // Sign the data
  const signature = await crypto.subtle.sign(
    "HMAC", key, encoder.encode(dataToSign)
  );

  // Convert signature to base64
  const signatureBase64 = btoa(String.fromCharCode(...new Uint8Array(signature)));

  // Return the complete JWT
  return `${encodedHeader}.${encodedPayload}.${signatureBase64}`;
}

export default {
  async fetch(request, env, ctx) {
    // Handle CORS preflight requests
    if (request.method === "OPTIONS") {
      return handleCorsRequest();
    }

    // Extract request details
    const url = new URL(request.url);
    const path = url.pathname;
    const clientIP = request.headers.get('CF-Connecting-IP') || '127.0.0.1';

    // Determine environment (dev/prod)
    const isDev = url.hostname.includes('localhost') || url.hostname.includes('127.0.0.1');
    const backendUrl = isDev ? DEV_ENDPOINT : PROD_ENDPOINT;

    if (!env.MODAL_ENDPOINT) {
      env.MODAL_ENDPOINT = backendUrl;
    }

    // Step 1: Authentication check
    const isAdmin = checkAdminAuth(request, env);

    // Step 2: Handle special endpoints
    const specialResponse = await handleSpecialEndpoints(request, env, path, isAdmin, clientIP);
    if (specialResponse) {
      return specialResponse;
    }

    // Step 3: Rate limiting check (skip for admin)
    if (!isAdmin) {
      const rateLimitResponse = await checkRateLimits(request, env, clientIP);
      if (rateLimitResponse) {
        return rateLimitResponse;
      }
    }

    // Handle workflow requests
    if (path.startsWith('/workflow')) {
      // Import the workflowHandler from workflow.js
      const { workflowHandler } = await import('./workflow.js');
      return workflowHandler.fetch(request, env);
    }

    // Step 4: Request handling - either project-specific or default
    if (projectHandlers && projectHandlers.default && typeof projectHandlers.default.handleRequest === 'function') {
      // Use project-specific handler
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
      // Use default handler
      return isAdmin ?
        handleAdminRequest(request, backendUrl, env) :
        handleFreeRequest(request, backendUrl, env);
    }
  }
};

// Check if request has admin authentication
function checkAdminAuth(request, env) {
  const authHeader = request.headers.get('Authorization') || '';

  if (authHeader.startsWith('Bearer ')) {
    const token = authHeader.substring(7);
    if (token === env[ADMIN_PASSWORD_ENV]) {
      return true;
    } else {
      // Invalid token provided, but we'll handle this in special endpoints
      return false;
    }
  }

  return false;
}

// Handle special endpoints like status, test, auth errors
async function handleSpecialEndpoints(request, env, path, isAdmin, clientIP) {
  const authHeader = request.headers.get('Authorization') || '';

  // Handle auth errors
  if (authHeader.startsWith('Bearer ') && !isAdmin) {
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

  // Handle status endpoint
  if (path === "/status" || path === "/api/status") {
    return handleStatusRequest(env, clientIP, isAdmin);
  }

  // Handle test endpoint
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
      // For free tier, we'll check rate limits later and then return this
      // We don't return here so rate limiting can be applied
    }
  }

  // Handle admin reset endpoint
  if (path === "/admin/reset-limits" && isAdmin) {
    try {
      // Reset IP limiter for the current IP
      const ipLimiterObj = env.IP_LIMITER.get(env.IP_LIMITER.idFromName(clientIP));
      await ipLimiterObj.fetch(new URL("/reset", request.url));

      // Reset global limiter
      const globalLimiterObj = env.GLOBAL_LIMITER.get(env.GLOBAL_LIMITER.idFromName('global'));
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

  // No special endpoint matched
  return null;
}

// Check rate limits for free tier
async function checkRateLimits(request, env, clientIP) {
  try {
    const url = new URL(request.url);
    const path = url.pathname;
    const testIP = request.headers.get('X-Test-IP');
    const effectiveIP = testIP || clientIP;

    // Log request information
    console.log({
      event: "rate_limit_check",
      client_ip: clientIP,
      effective_ip: effectiveIP,
      path: path,
      method: request.method,
      timestamp: new Date().toISOString()
    });

    // Check IP-specific rate limit
    const ipLimiterObj = env.IP_LIMITER.get(env.IP_LIMITER.idFromName(effectiveIP));
    const ipLimiterResp = await ipLimiterObj.fetch(request.url);

    if (!ipLimiterResp.ok) {
      console.log({
        event: "rate_limit_exceeded",
        limit_type: "per_ip",
        client_ip: effectiveIP,
        path: path,
        timestamp: new Date().toISOString()
      });
      return ipLimiterResp; // Return rate limit exceeded error
    }

    // Check global rate limit
    const globalLimiterObj = env.GLOBAL_LIMITER.get(env.GLOBAL_LIMITER.idFromName('global'));
    const globalLimiterResp = await globalLimiterObj.fetch(request.url);

    if (!globalLimiterResp.ok) {
      console.log({
        event: "rate_limit_exceeded",
        limit_type: "global",
        client_ip: effectiveIP,
        path: path,
        timestamp: new Date().toISOString()
      });
      return globalLimiterResp; // Return rate limit exceeded error
    }

    // Handle test endpoint response after rate limiting
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

    // Rate limits passed, no response needed
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

// Handle requests with admin privileges
async function handleAdminRequest(request, backendUrl, env) {
  try {
    // Clone the request to modify it
    const url = new URL(request.url);

    // Log the environment variables for debugging
    console.log({
      event: "admin_request",
      modal_endpoint: env.MODAL_ENDPOINT || backendUrl,
      jwt_secret_present: !!env.SHARED_JWT_SECRET
    });

    // Create new request to backend
    const backendRequest = new Request(`${env.MODAL_ENDPOINT || backendUrl}${url.pathname}${url.search}`, {
      method: request.method,
      headers: new Headers(request.headers),
      body: request.body
    });

    // Create JWT payload
    const jwtPayload = {
      iss: "gimme-ai-gateway",
      sub: PROJECT_NAME,
      exp: Math.floor(Date.now() / 1000) + 300, // 5 minutes expiration
      iat: Math.floor(Date.now() / 1000),
      mode: "admin",
      jti: crypto.randomUUID() // Unique token ID to prevent replay
    };

    // Sign the JWT
    const jwt = await createJWT(jwtPayload, env.SHARED_JWT_SECRET);

    // Add JWT to Authorization header
    backendRequest.headers.set('Authorization', `Bearer ${jwt}`);

    // Add auth state to headers (for backward compatibility)
    backendRequest.headers.set('X-Auth-Mode', 'admin');
    backendRequest.headers.set('X-Auth-Source', 'gimme-ai-gateway');
    backendRequest.headers.set('X-Project-Name', PROJECT_NAME);

    // Add API keys as headers - they are pulled from the env
    {% for key in required_keys %}
    backendRequest.headers.set('{{ key }}', env['{{ key }}']);
    {% endfor %}

    // Log the headers for debugging
    console.log({
      event: "request_headers",
      headers: Object.fromEntries([...backendRequest.headers.entries()])
    });

    // Forward to backend and return response
    const response = await fetch(backendRequest);

    // Log the response status for debugging
    console.log({
      event: "response_received",
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

// Handle requests with free tier access
async function handleFreeRequest(request, backendUrl, env) {
  try {
    // Clone the request
    const url = new URL(request.url);

    // Create new request to backend
    const backendRequest = new Request(`${backendUrl}${url.pathname}${url.search}`, {
      method: request.method,
      headers: new Headers(request.headers),
      body: request.body
    });

    // Create JWT payload
    const jwtPayload = {
      iss: "gimme-ai-gateway",
      sub: PROJECT_NAME,
      exp: Math.floor(Date.now() / 1000) + 300, // 5 minutes expiration
      iat: Math.floor(Date.now() / 1000),
      mode: "free",
      jti: crypto.randomUUID() // Unique token ID to prevent replay
    };

    // Sign the JWT
    const jwt = await createJWT(jwtPayload, env.SHARED_JWT_SECRET);

    // Add JWT to Authorization header
    backendRequest.headers.set('Authorization', `Bearer ${jwt}`);

    // Add auth state to headers (for backward compatibility)
    backendRequest.headers.set('X-Auth-Mode', 'free');
    backendRequest.headers.set('X-Auth-Source', 'gimme-ai-gateway');
    backendRequest.headers.set('X-Project-Name', PROJECT_NAME);

    // Add API keys as headers - they are pulled from the env
    {% for key in required_keys %}
    backendRequest.headers.set('{{ key }}', env['{{ key }}']);
    {% endfor %}

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

// Handle CORS preflight requests
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

// Handle status requests
function handleStatusRequest(env, clientIP, isAdmin) {
  const mode = isAdmin ? "admin" : "free";
  const limit = isAdmin ? "unlimited" : "{{ limits.free_tier.per_ip }}";

  return new Response(JSON.stringify({
    status: "online",
    project: PROJECT_NAME,
    mode: mode,
    rate_limit: limit,
    client_ip: clientIP,
    timestamp: new Date().toISOString()
  }), {
    status: 200,
    headers: {
      "Content-Type": "application/json",
      "Access-Control-Allow-Origin": "*",
      "X-Powered-By": "Gimme-AI Gateway"
    }
  });
}

// IMPORTANT: Export the workflow class
export { VideoGenerationWorkflow };

// Export the rate limiters
export { IPRateLimiter, GlobalRateLimiter };
