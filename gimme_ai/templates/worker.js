// Main Worker Script for API Gateway
// Handles authentication, rate limiting, and request forwarding

// Configuration
const DEV_ENDPOINT = "{{ dev_endpoint }}";
const PROD_ENDPOINT = "{{ prod_endpoint }}";
const ADMIN_PASSWORD_ENV = "{{ admin_password_env }}";
const PROJECT_NAME = "{{ project_name }}";

// Required API Keys - these will be available in the worker environment:
{% for key in required_keys %}
// - {{ key }}
{% endfor %}

export default {
  async fetch(request, env, ctx) {
    // Handle CORS preflight requests
    if (request.method === "OPTIONS") {
      return handleCorsRequest();
    }

    // Extract request details
    const url = new URL(request.url);
    const path = url.pathname;

    // Determine environment (dev/prod)
    const isDev = url.hostname.includes('localhost') || url.hostname.includes('127.0.0.1');
    const backendUrl = isDev ? DEV_ENDPOINT : PROD_ENDPOINT;

    // Extract client IP
    const clientIP = request.headers.get('CF-Connecting-IP') || '127.0.0.1';

    // Check authentication mode
    const authHeader = request.headers.get('Authorization') || '';
    const isAdmin = authHeader.startsWith('Bearer ') &&
                    authHeader.substring(7) === env[ADMIN_PASSWORD_ENV];

    // Handle status endpoint
    if (path === "/status" || path === "/api/status") {
      return handleStatusRequest(env, clientIP, isAdmin);
    }

    // For admin mode, bypass rate limiting
    if (isAdmin) {
      return handleAdminRequest(request, backendUrl, env);
    }

    // For free tier, apply rate limiting
    try {
      // Check IP-specific rate limit
      const ipLimiterObj = env.IP_LIMITER.get(env.IP_LIMITER.idFromName(clientIP));
      const ipLimiterResp = await ipLimiterObj.fetch(request.url);

      if (!ipLimiterResp.ok) {
        return ipLimiterResp; // Return rate limit exceeded error
      }

      // Check global rate limit
      const globalLimiterObj = env.GLOBAL_LIMITER.get(env.GLOBAL_LIMITER.idFromName('global'));
      const globalLimiterResp = await globalLimiterObj.fetch(request.url);

      if (!globalLimiterResp.ok) {
        return globalLimiterResp; // Return rate limit exceeded error
      }

      // If we passed rate limiting, forward request to backend
      return handleFreeRequest(request, backendUrl, env);
    } catch (error) {
      return new Response(JSON.stringify({
        error: "Gateway error",
        message: "An error occurred processing your request",
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
};

// Handle requests with admin privileges
async function handleAdminRequest(request, backendUrl, env) {
  try {
    // Clone the request to modify it
    const url = new URL(request.url);

    // Create new request to backend
    const backendRequest = new Request(`${backendUrl}${url.pathname}${url.search}`, {
      method: request.method,
      headers: request.headers,
      body: request.body
    });

    // Add auth state to headers
    backendRequest.headers.set('X-Auth-Mode', 'admin');

    // Add API keys as headers - they are pulled from the env
    {% for key in required_keys %}
    backendRequest.headers.set('{{ key }}', env['{{ key }}']);
    {% endfor %}

    // Forward to backend and return response
    const response = await fetch(backendRequest);

    // Clone the response to add CORS headers
    const corsResponse = new Response(response.body, response);
    corsResponse.headers.set('Access-Control-Allow-Origin', '*');

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

// Handle requests with free tier access
async function handleFreeRequest(request, backendUrl, env) {
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
    backendRequest.headers.set('X-Auth-Mode', 'free');

    // Add API keys as headers - they are pulled from the env
    {% for key in required_keys %}
    backendRequest.headers.set('{{ key }}', env['{{ key }}']);
    {% endfor %}

    // Forward to backend and return response
    const response = await fetch(backendRequest);

    // Clone the response to add CORS headers
    const corsResponse = new Response(response.body, response);
    corsResponse.headers.set('Access-Control-Allow-Origin', '*');

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
    project: "{{ project_name }}",
    mode: mode,
    rate_limit: limit,
    client_ip: clientIP,
    timestamp: new Date().toISOString()
  }), {
    status: 200,
    headers: {
      "Content-Type": "application/json",
      "Access-Control-Allow-Origin": "*"
    }
  });
}
