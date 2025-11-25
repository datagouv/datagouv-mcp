Model Context Protocol (MCP) for interacting with data.gouv.fr datasets and resources via LLM chatbots, built using the [the official Python SDK for MCP servers and clients](https://github.com/modelcontextprotocol/python-sdk) and the Streamable HTTP transport protocol.

## Setup and Configuration

1. **Install dependencies**
  ```bash
  uv sync
  ```

2. **Prepare the environment file**

  Copy the example environment file to create your own `.env` file:
  ```bash
  cp .env.example .env
  ```

  Then optionnaly edit `.env` and set the variables that matter for your run:
  ```
  MCP_PORT=8007
  # Allowed values: demo | prod (defaults to demo when unset)
  DATAGOUV_ENV=demo
  ```

  - `MCP_PORT`: port for the FastMCP HTTP server (defaults to `8000` when unset).
  - `DATAGOUV_ENV`: `demo` (default) or `prod`. This controls which data.gouv.fr API/website the helpers call and automatically picks the appropriate Tabular API endpoint (`https://tabular-api.preprod.data.gouv.fr/api/` for demo, `https://tabular-api.data.gouv.fr/api/` for prod).

  Load the variables with your preferred method, e.g.:
  ```bash
  set -a && source .env && set +a
  ```

3. **Start the HTTP MCP server**
   ```bash
   uv run main.py
   ```

## 🚀 Quick Start

1. **Test the server:**
   ```bash
   curl -X POST http://127.0.0.1:8000/mcp -H "Accept: application/json" -H "Content-Type: application/json" -d '{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}'
   ```

## 🔧 MCP client configuration

The MCP server configuration depends on your client. Use the appropriate configuration format for your client:

> **Note:** If you want to create or modify data.gouv.fr datasets/resources, you'll need a data.gouv.fr API key. You can get one from your [production profile settings](https://www.data.gouv.fr/fr/account/) or your [demo profile settings](https://demo.data.gouv.fr/fr/account/). The API key must be passed via HTTP headers in your MCP client configuration.

### Cursor

Cursor supports MCP servers through its settings. To configure the server:

1. Open Cursor Settings (Cmd/Ctrl + ,)
2. Search for "MCP" or "Model Context Protocol"
3. Add a new MCP server with the following configuration:

```json
{
  "mcpServers": {
    "data-gouv": {
      "url": "http://127.0.0.1:8000/mcp",
      "transport": "http",
      "headers": {
        "API_KEY": "your-data-gouv-api-key-here"
      }
    }
  }
}
```

### Gemini CLI

Add the following to your `~/.gemini/settings.json` file:

```json
{
  "mcpServers": {
    "data-gouv": {
      "transport": "http",
      "httpUrl": "http://127.0.0.1:8000/mcp",
      "headers": {
        "Authorization": "Bearer your-data-gouv-api-key-here"
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
        "http://127.0.0.1:8000/mcp",
        "--header",
        "Authorization: Bearer your-data-gouv-api-key-here"
      ]
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
      "url": "http://127.0.0.1:8000/mcp",
      "type": "http",
      "headers": {
        "authorization": "Bearer your-data-gouv-api-key-here"
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
      "command": "npx",
      "args": [
        "-y",
        "mcp-remote",
        "http://127.0.0.1:8000/mcp",
        "--header",
        "Authorization: Bearer your-data-gouv-api-key-here"
      ]
    }
  }
}
```

**Note:**
- Replace `http://127.0.0.1:8000/mcp` with your actual server URL if running on a different host or port. For production deployments, use `https://` and configure the appropriate hostname.
- Replace `your-data-gouv-api-key-here` with your actual API key from [data.gouv.fr account settings](https://www.data.gouv.fr/fr/account/).
- The API key is only required for tools that create or modify datasets/resources. Read-only operations (like `search_datasets`) work without an API key.
- For Cursor, use the `API_KEY` header name. For other clients, you can use either `Authorization: Bearer <token>` or `API_KEY: <token>` format.

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

- **`create_dataset`** - Create a new dataset on data.gouv.fr. Requires a data.gouv.fr API key supplied by the MCP client via the `api_key` parameter. Configure your MCP client to pass the key automatically (e.g., Cursor's `config.apiKey`). By default, datasets created via the API are public. Set `private=True` to create a draft.

  Parameters:
  - `title` (required): Dataset title
  - `description` (required): Dataset description
  - `organization` (optional): Optional organization ID or slug
  - `private` (optional, default: False): If True, create as draft (private). Default: False (public)
  - `api_key` (optional): API key forwarded by the MCP client (required for creating datasets)

- **`query_dataset_data`** - Query data from a dataset by exploring its resources via the data.gouv.fr Tabular API. This tool finds a dataset (by ID or by searching), retrieves its resources, and fetches rows directly from the Tabular API to answer questions about the data (no local database required).

  Parameters:
  - `question` (required): The question or description of what data you're looking for
  - `dataset_id` (optional): Dataset ID if you already know which dataset to query
  - `dataset_query` (optional): Search query to find the dataset if `dataset_id` is not provided
  - `limit_per_resource` (optional, default: 100): Maximum number of rows to retrieve per resource table

  Note: Either `dataset_id` or `dataset_query` must be provided. Data availability depends on whether the resource is ingested in the Tabular API (CSV/XLS resources within the documented size limits).

## 🧪 Tests

Run tests with pytest:

```bash
# Run all tests
uv run pytest

# Run with verbose output
uv run pytest -v

# Run specific test file
uv run pytest tests/test_tabular_api.py

# Run with custom resource ID
RESOURCE_ID=3b6b2281-b9d9-4959-ae9d-c2c166dff118 uv run pytest tests/test_tabular_api.py

# Run with prod environment
DATAGOUV_ENV=prod uv run pytest
```

## 🤝 Contributing

### 🧹 Code Linting and Formatting

This project follows PEP 8 style guidelines using [Ruff](https://astral.sh/ruff/) for linting and formatting. **Either running these commands manually or installing the pre-commit hook is required before submitting contributions.**

```shell
# Lint and sort imports, and format code
uv run ruff check  --select I --fix && uv run ruff format
```

### 🔗 Pre-commit Hooks

This repository uses a [pre-commit](https://pre-commit.com/) hook which lint and format code before each commit. **Installing the pre-commit hook is required for contributions.**

**Install pre-commit hooks:**
```shell
uv run pre-commit install
```
The pre-commit hook that automatically:
- Check YAML syntax
- Fix end-of-file issues
- Remove trailing whitespace
- Check for large files
- Run Ruff linting and formatting
