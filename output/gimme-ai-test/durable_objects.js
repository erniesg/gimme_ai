// Rate Limiter Durable Object for IP-based and global rate limiting

export class IPRateLimiter {
  constructor(state, env) {
    this.state = state;
    this.storage = state.storage;
    this.env = env;
    this.limit = 5;
    this.rateWindow = "lifetime";
  }

  async fetch(request) {
    const url = new URL(request.url);

    // Add reset functionality
    if (url.pathname === "/reset") {
      await this.storage.delete("count");
      console.log({
        event: "rate_limit_reset",
        type: "per_ip",
        ip: url.hostname,
        timestamp: new Date().toISOString()
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

    // Check if the limit has been reached
    if (count >= this.limit) {
      console.log({
        event: "rate_limit_exceeded",
        type: "per_ip",
        ip: url.hostname,
        count: count,
        limit: this.limit,
        timestamp: new Date().toISOString()
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

    // Increment the counter
    await this.storage.put("count", count + 1);
    console.log({
      event: "rate_limit_increment",
      type: "per_ip",
      ip: url.hostname,
      count: count + 1,
      limit: this.limit,
      remaining: this.limit - (count + 1),
      timestamp: new Date().toISOString()
    });

    // Return success
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
}

export class GlobalRateLimiter {
  constructor(state, env) {
    this.state = state;
    this.storage = state.storage;
    this.env = env;
    this.limit = 10;
    this.rateWindow = "lifetime";
  }

  async fetch(request) {
    const url = new URL(request.url);

    // Add reset functionality
    if (url.pathname === "/reset") {
      await this.storage.delete("count");
      console.log({
        event: "rate_limit_reset",
        type: "global",
        timestamp: new Date().toISOString()
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

    // Check if the limit has been reached
    if (count >= this.limit) {
      console.log({
        event: "rate_limit_exceeded",
        type: "global",
        count: count,
        limit: this.limit,
        timestamp: new Date().toISOString()
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

    // Increment the counter
    await this.storage.put("count", count + 1);
    console.log({
      event: "rate_limit_increment",
      type: "global",
      count: count + 1,
      limit: this.limit,
      remaining: this.limit - (count + 1),
      timestamp: new Date().toISOString()
    });

    // Return success
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
}