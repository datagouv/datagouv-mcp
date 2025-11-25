 Model Context Protocol (MCP) for interacting with data.gouv.fr datasets and resources with LLM chatbots, built using the [the official Python SDK for MCP servers and clients](https://github.com/modelcontextprotocol/python-sdk) and the Streamable HTTP transport protocol.

## Setup and Configuration

1. **Start the real Hydra CSV database locally**

   Make sure the Hydra CSV database is running on your machine. Follow the [Hydra repository](https://github.com/datagouv/hydra) instructions so the database is accessible on `localhost:5434`. The MCP server relies on these tables for some workflows.

2. **Start PostgREST pointing to Hydra**
   ```shell
   docker compose --profile hydra up -d
   ```
   The `--profile hydra` target from this repo spins up PostgREST on port 8080 and connects it to your Hydra CSV database.

3. **Install dependencies**
   ```bash
   uv sync
   ```

4. **Prepare the environment file**

   ```bash
   cp .env.example .env
   ```

   Then edit `.env` and set the variables that matter for your run:

   ```
   MCP_PORT=8007
   # Allowed values: demo | prod (defaults to demo when unset)
   DATAGOUV_API_ENV=demo
   ```

   - `MCP_PORT`: port for the FastMCP HTTP server (defaults to `8000` when unset).
   - `DATAGOUV_API_ENV`: `demo` (default) or `prod`. This controls which data.gouv.fr API/website the helpers call and the URLs returned by the tools.

   Load the variables with your preferred method, e.g.:
   ```bash
   set -a && source .env && set +a
   ```

5. **Start the HTTP MCP server**
   ```bash
   uv run main.py
   ```

## 🚀 Quick Start

1. **Test the server:**
   ```bash
   curl -X POST http://127.0.0.1:8007/mcp -H "Accept: application/json" -H "Content-Type: application/json" -d '{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}'
   ```

## 🔧 MCP client configuration

The MCP server configuration depends on your client. Use the appropriate configuration format for your client:

> **Note:** If you want to create or modify data.gouv.fr datasets/resources, you'll need a data.gouv.fr API key. You can get one from your [production profile settings](https://www.data.gouv.fr/fr/account/) or your [demo profile settings](https://demo.data.gouv.fr/fr/account/). Add it to your client configuration as shown in the examples below.

### Gemini CLI

```bash
gemini mcp add --transport http api-tabular http://127.0.0.1:8007/mcp
```

Alternatively, add the following to your `~/.gemini/settings.json` file:

```json
{
  "mcpServers": {
    "api-tabular": {
      "httpUrl": "http://127.0.0.1:8007/mcp",
      "args": {
        "apiKey": "your-data-gouv-api-key-here"
      }
    }
  }
}
```

### Claude Desktop

Add the following to your Claude Desktop configuration file (typically `~/Library/Application Support/Claude/claude_desktop_config.json` on macOS, or `%APPDATA%\Claude\claude_desktop_config.json` on Windows):

```json
{
  "mcpServers": {
    "data-gouv": {
      "command": "npx",
      "args": [
        "mcp-remote",
        "http://127.0.0.1:8007/mcp",
        "--header",
        "X-MCP-Config: {\"apiKey\":\"your-data-gouv-api-key-here\"}"
      ]
    }
  }
}
```

Or if your client supports direct configuration:

```json
{
  "mcpServers": {
    "data-gouv": {
      "command": "npx",
      "args": [
        "mcp-remote",
        "http://127.0.0.1:8007/mcp"
      ],
      "config": {
        "apiKey": "your-data-gouv-api-key-here"
      }
    }
  }
}
```

### VS Code

Add the following to your VS Code `settings.json`:

```json
{
  "servers": {
    "data-gouv": {
      "url": "http://127.0.0.1:8007/mcp",
      "type": "http",
      "config": {
        "apiKey": "your-data-gouv-api-key-here"
      }
    }
  }
}
```

### Windsurf

Add the following to your `~/.codeium/mcp_config.json`:

```json
{
  "mcpServers": {
    "data-gouv": {
      "serverUrl": "http://127.0.0.1:8007/mcp",
      "config": {
        "apiKey": "your-data-gouv-api-key-here"
      }
    }
  }
}
```

### Cursor

Cursor supports MCP servers through its settings. To configure the server:

1. Open Cursor Settings (Cmd/Ctrl + ,)
2. Search for "MCP" or "Model Context Protocol"
3. Add a new MCP server with the following configuration:

```json
{
  "mcpServers": {
    "data-gouv": {
      "url": "http://127.0.0.1:8007/mcp",
      "transport": "http",
      "config": {
        "apiKey": "your-data-gouv-api-key-here"
      }
    }
  }
}
```

**Note:**
- Replace `http://127.0.0.1:8007/mcp` with your actual server URL if running on a different host or port. For production deployments, use `https://` and configure the appropriate hostname.
- Replace `your-data-gouv-api-key-here` with your actual API key from [data.gouv.fr account settings](https://www.data.gouv.fr/fr/account/).
- The API key is only required for tools that create or modify datasets/resources. Read-only operations (like `search_datasets`) work without an API key.

## 🧭 Test with MCP Inspector

Use the official MCP Inspector to interactively test the server tools and resources.

Prerequisites:
- Node.js with `npx` available

Steps:
1. Start the MCP server (see above):
   ```bash
   uv run main.py
   ```
2. In another terminal, launch the inspector:
   ```bash
   npx @modelcontextprotocol/inspector --http-url "http://127.0.0.1:${MCP_PORT}/mcp"
   ```
   Adjust the URL if you exposed the server on another host/port.

## 🚚 Transport support

This MCP server uses FastMCP and implements the Streamable HTTP transport only.
STDIO and SSE are not supported.

Use Streamable HTTP at `http://127.0.0.1:8007/mcp` in clients (e.g. MCP Inspector).

## 📋 Available Endpoints

**Streamable HTTP transport (standards-compliant):**
- `POST /mcp` - JSON-RPC messages (client → server)

## 🛠️ Available Tools

The MCP server provides tools to interact with data.gouv.fr datasets:

- **`search_datasets`** - Search for datasets on data.gouv.fr by keywords. Returns a list of datasets matching the search query with their metadata, including title, description, organization, tags, and resource count. Use this to discover datasets before querying their data.

  Parameters:
  - `query` (required): Search query string (searches in title, description, tags)
  - `page` (optional, default: 1): Page number
  - `page_size` (optional, default: 20, max: 100): Number of results per page

## 🧪 Tests

TODO
