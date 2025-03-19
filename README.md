# 🚀 gimme_ai

Secure API gateway for AI services in minutes, not days.

## 🏎️ Quick Start

```bash
# Install
pip install gimme_ai
npm install -g wrangler

# Deploy
gimme-ai init
gimme-ai deploy

# Test your gateway
gimme-ai test-all
```

## ✨ Why gimme_ai?

- **Zero Configuration**: Works out-of-the-box with sensible defaults
- **API Security**: Keep credentials and manage rate limits behind Cloudflare's edge
- **Instant Auth**: Admin access with zero setup
- **AI-Optimized**: Designed specifically for LLM and AI service patterns
- **Workflow Support**: Orchestrate multi-step API processes with dependency management
- **Production Ready**: CORS, error handling, logging, and global CDN included

No complex setup. No infrastructure headaches. Just secure, scalable API gateways.

## 📋 Usage Guide

### Deployment

```bash
# Initialize with interactive setup
gimme-ai init

# Deploy to Cloudflare
gimme-ai deploy
```

### Testing

```bash
# Run all tests (auto-detects URL from your config)
gimme-ai test-all

# Specify URL explicitly if needed
gimme-ai test-all https://your-project.workers.dev

# Test specific components
gimme-ai test-auth
gimme-ai test-rate-limits
gimme-ai test-workflow
```

⚠️ **Note**: Rate limit tests will reset your gateway's limits before and after testing, which could affect ongoing API usage.

### Advanced Options

```bash
# Skip confirmation prompts
gimme-ai test-all --skip-reset-confirm

# Use a specific admin password
gimme-ai test-all --admin-password=your-password

# Verbose output for troubleshooting
gimme-ai test-all --verbose
```

## 🛠️ Features

### Rate Limit Management

Control API usage with built-in rate limiting:

```bash
# Reset rate limits during development
gimme-ai test-rate-limits https://your-project.workers.dev
```

Default rate limits:
- Per-IP: 10 requests/minute
- Global: 100 requests/minute
- Admin users bypass limits with proper authentication

### Workflow Orchestration

Coordinate complex multi-step processes:
- Define dependencies between API calls
- Automatic polling for job completion
- Error handling and retry logic built-in

### Security

- API keys stored securely in environment variables
- Admin authentication for privileged operations
- Protection from DDoS and other attacks via Cloudflare

## 📖 License

MIT
