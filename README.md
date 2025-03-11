# gimme_ai

Secure API gateway management for AI services.

## Installation

```bash
pip install gimme_ai
```

### Additional Dependencies

To deploy your gateway to Cloudflare, you need to install the `wrangler` CLI tool:

```bash
npm install -g wrangler
```

## Quick Start

1. Initialize a new project:

```bash
gimme-ai init --project-name my-project
```

2. Edit the generated `.env` file to add your API keys.

3. Customize your configuration in `.gimme-config.json` if needed.

4. Validate your configuration:

```bash
gimme-ai validate
```

5. Deploy your gateway:

```bash
gimme-ai deploy
```

### Cloudflare API Token

To deploy your gateway to Cloudflare, you must set a `CLOUDFLARE_API_TOKEN` environment variable. This token is used to authenticate with Cloudflare's API.

#### Creating a Cloudflare API Token

1. Log in to the [Cloudflare dashboard](https://dash.cloudflare.com/).
2. Navigate to "My Profile" and then to the "API Tokens" section.
3. Click on "Create Token" and select the "Edit Cloudflare Workers" template or customize the permissions as needed.
4. Generate the token and copy it.

#### Setting the API Token

Add the token to your `.env` file:

```plaintext
CLOUDFLARE_API_TOKEN=your-generated-token
```

Alternatively, set it in your shell session before running the deploy command:

```bash
export CLOUDFLARE_API_TOKEN=your-generated-token
```

## License

MIT
