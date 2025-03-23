/**
 * Workflow utilities for test-project
 * Contains helper functions for API calls, polling, and error handling
 */

/**
 * Format an endpoint URL by replacing placeholders with state values
 * @param {string} endpoint - Endpoint URL with placeholders like {job_id}
 * @param {Object} state - State object containing values to inject
 * @returns {string} - Formatted endpoint URL
 */
export function formatEndpoint(endpoint, state) {
  // Replace all {variable} placeholders with values from state
  return endpoint.replace(/\{([^}]+)\}/g, (match, key) => {
    if (state[key] !== undefined) {
      return state[key];
    }
    console.warn(`Missing value for ${key} in endpoint: ${endpoint}`);
    return match; // Keep original placeholder if value is missing
  });
}

/**
 * Get default headers for API requests
 * @returns {Object} - Headers object
 */
export function getDefaultHeaders() {
  return {
    'Content-Type': 'application/json',
    'Accept': 'application/json'
  };
}

/**
 * Parse a time string into milliseconds
 * @param {string} timeStr - Time string like "5s", "2m", "1h"
 * @returns {number} - Time in milliseconds
 */
export function parseTimeString(timeStr) {
  const match = timeStr.match(/^(\d+)([smh])$/);
  if (!match) {
    return 5000; // Default to 5 seconds if format is invalid
  }

  const [_, value, unit] = match;
  const numValue = parseInt(value, 10);

  switch (unit) {
    case 's': return numValue * 1000;
    case 'm': return numValue * 60 * 1000;
    case 'h': return numValue * 60 * 60 * 1000;
    default: return 5000;
  }
}

/**
 * Poll an endpoint until a condition is met
 * @param {Object} step - Workflow step object
 * @param {string} endpoint - Endpoint to poll (can contain placeholders)
 * @param {Object} state - Current workflow state
 * @param {string} interval - Polling interval as string (e.g., "5s")
 * @param {number} maxAttempts - Maximum polling attempts
 * @returns {Promise<Object>} - Final response from the endpoint
 */
export async function pollUntilComplete(step, endpoint, state, interval = "5s", maxAttempts = 60) {
  const pollingName = `polling_${state.step}_${state.job_id}`;
  console.log(`[ID Tracking] Starting polling: ${pollingName} for job_id: ${state.job_id}`);

  return await step.loop(pollingName, {
    maxAttempts: maxAttempts,
  }, async (attempt) => {
    // Don't format the endpoint - it's already complete
    console.log(`[ID Tracking] Polling attempt ${attempt} for job_id ${state.job_id}`);
    console.log(`[ID Tracking] Using endpoint: ${endpoint}`);

    const response = await fetch(endpoint, {
      method: 'GET',  // Always use GET for polling
      headers: {
        ...getDefaultHeaders(),
        'X-Auth-Source': 'gimme-ai-gateway',
        'X-Auth-Mode': 'admin'
      }
    });

    if (!response.ok) {
      console.error(`[ID Tracking] Polling failed for job_id ${state.job_id}:`, await response.text());
      throw new Error(`Polling failed (${response.status}): ${await response.text()}`);
    }

    const result = await response.json();
    console.log(`[ID Tracking] Poll response for job_id ${state.job_id}:`, result);

    if (result.status === 'completed' || result.status === 'success') {
      console.log(`[ID Tracking] Job ${state.job_id} completed successfully`);
      return { status: 'completed', result };
    } else if (result.status === 'failed' || result.status === 'error') {
      console.error(`[ID Tracking] Job ${state.job_id} failed:`, result);
      throw new Error(`Job failed: ${JSON.stringify(result)}`);
    }

    await step.sleep(`${pollingName}_sleep_${attempt}`, interval);
    return { status: 'pending', attempt, result };
  });
}

/**
 * Execute an API call with retry support
 * @param {Object} config - API call configuration
 * @param {string} config.endpoint - Endpoint URL
 * @param {string} config.method - HTTP method
 * @param {Object} config.headers - Request headers
 * @param {Object} config.body - Request body
 * @param {number} config.retries - Number of retries
 * @param {string} config.retryInterval - Interval between retries
 * @returns {Promise<Object>} - API response
 */
export async function executeApiCall(config) {
  const {
    endpoint,
    method = 'POST',
    headers = getDefaultHeaders(),
    body = {},
    retries = 3,
    retryInterval = '5s'
  } = config;

  let lastError;

  for (let attempt = 0; attempt <= retries; attempt++) {
    try {
      const response = await fetch(endpoint, {
        method,
        headers,
        body: method !== 'GET' ? JSON.stringify(body) : undefined
      });

      if (!response.ok) {
        throw new Error(`Request failed (${response.status}): ${await response.text()}`);
      }

      return await response.json();
    } catch (error) {
      lastError = error;

      if (attempt < retries) {
        // Sleep before retrying
        const sleepTime = parseTimeString(retryInterval);
        await new Promise(resolve => setTimeout(resolve, sleepTime));
      }
    }
  }

  // If we've exhausted all retries, throw the last error
  throw lastError;
}
