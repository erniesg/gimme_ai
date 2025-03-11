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

5. Deploy your gateway (coming in future releases):

```bash
gimme-ai deploy
```

## License

MIT
