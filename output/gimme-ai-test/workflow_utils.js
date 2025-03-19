/**
 * Workflow utilities for gimme-ai-test
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
  const pollingName = `polling_${Date.now()}`;

  return await step.loop(pollingName, {
    maxAttempts: maxAttempts,
  }, async (attempt) => {
    // Format the endpoint URL with state variables
    const formattedEndpoint = formatEndpoint(endpoint, state);

    // Make the API call
    const response = await fetch(formattedEndpoint, {
      method: 'GET',
      headers: getDefaultHeaders()
    });

    if (!response.ok) {
      // If the API returns an error, we'll throw to retry the polling
      throw new Error(`Polling failed (${response.status}): ${await response.text()}`);
    }

    const result = await response.json();

    // Check if the job is complete or failed
    if (result.status === 'completed' || result.status === 'success') {
      // Job is complete, return the result and stop polling
      return { status: 'completed', result };
    } else if (result.status === 'failed' || result.status === 'error') {
      // Job failed, throw an error to stop polling
      throw new Error(`Job failed: ${JSON.stringify(result)}`);
    }

    // Sleep before the next polling attempt
    const sleepTime = parseTimeString(interval);
    await new Promise(resolve => setTimeout(resolve, sleepTime));

    // Return a value to continue the loop
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