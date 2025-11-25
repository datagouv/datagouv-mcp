# MCP Client Configuration Guide

Use this guide to wire the data.gouv.fr MCP server into popular MCP-aware clients. The examples assume the server runs on `http://127.0.0.1:8000/mcp`; adjust host/port accordingly. Make sure your `.env` selects the same environment (`DATAGOUV_ENV=demo|prod`) that matches the API key you provide below.

## API Key Policy

- Keys must be generated from **https://demo.data.gouv.fr/fr/account/** or **https://www.data.gouv.fr/fr/account/** (match the host to your `DATAGOUV_ENV`).
- The API key must be passed via HTTP headers in the MCP client configuration.
- The server extracts the API key from HTTP headers (supports `API_KEY`, `Authorization: Bearer <token>`, or `X-API-Key` headers).
- The key can also be passed as the `api_key` parameter in tool calls, but using headers is recommended for security.

If the API responds with `401 Invalid API Key`, double-check that the key belongs to the correct environment—demo keys work with `DATAGOUV_ENV=demo`, production keys with `DATAGOUV_ENV=prod`.

## Cursor

```json
{
  "mcpServers": {
    "data-gouv": {
      "url": "http://127.0.0.1:8000/mcp",
      "transport": "http",
      "headers": {
        "API_KEY": "YOUR_DEMO_API_KEY"
      }
    }
  }
}
```

The server extracts the API key from the `API_KEY` header and makes it available to tools.

## Gemini CLI

Add to `~/.gemini/settings.json`:

```json
{
  "mcpServers": {
    "data-gouv": {
      "transport": "http",
      "httpUrl": "http://127.0.0.1:8000/mcp",
      "headers": {
        "Authorization": "Bearer YOUR_DEMO_API_KEY"
      }
    }
  }
}
```

## Claude Desktop

Claude supports running MCP servers through `mcp-remote`:

```json
{
  "mcpServers": {
    "data-gouv": {
      "command": "npx",
      "args": [
        "mcp-remote",
        "http://127.0.0.1:8000/mcp",
        "--header",
        "Authorization: Bearer YOUR_DEMO_API_KEY"
      ]
    }
  }
}
```

## VS Code MCP extension

Add to `settings.json`:

```json
{
  "servers": {
    "data-gouv": {
      "url": "http://127.0.0.1:8000/mcp",
      "type": "http",
      "headers": {
        "authorization": "Bearer YOUR_DEMO_API_KEY"
      }
    }
  }
}
```

## Windsurf / Codeium MCP

Edit `~/.codeium/mcp_config.json`:

```json
{
  "mcpServers": {
    "data-gouv": {
      "command": "npx",
      "args": [
        "-y",
        "mcp-remote",
        "http://127.0.0.1:8000/mcp",
        "--header",
        "Authorization: Bearer YOUR_DEMO_API_KEY"
      ]
    }
  }
}
```

## Notes

- If a client repeatedly shows the old API key, restart it so it reloads the MCP config (Cursor caches configs until restart).
- For production deployments, use HTTPS, set `DATAGOUV_ENV=prod`, and configure the reverse proxy to forward the same headers; nothing changes server-side.
- `search_datasets` does not need an API key, so read-only workflows work without configuration.
- The server supports multiple header formats: `API_KEY`, `Authorization: Bearer <token>`, or `X-API-Key`.
