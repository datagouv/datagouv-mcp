Model Context Protocol (MCP) for interacting with data.gouv.fr datasets and resources via LLM chatbots, built using the [the official Python SDK for MCP servers and clients](https://github.com/modelcontextprotocol/python-sdk) and the Streamable HTTP transport protocol.

## I don't understand. What is this?

The datagouv MCP is a tool that allows AI chatbots (like Claude, Gemini, or Cursor) to search, explore, and analyze datasets from data.gouv.fr directly through conversation. Instead of manually browsing the website, you can simply ask questions like "Quels jeux de données sont disponibles sur les prix de l'immobilier ?" or "Montre-moi les dernières données de population pour Paris" and get instant answers. This is currently a **proof of concept (POC)** and is meant to be run **locally on your machine** for now, until it is put into production later. Since it runs locally, you'll need a few basic tech skills to set it up, but Docker makes the process straightforward.

## 1. Run the MCP server

Before starting, clone the repository and browse into it:

```bash
git clone git@github.com:datagouv/datagouv-mcp.git
cd datagouv_mcp
```

Docker is required for the recommended setup. Install it via [Docker Desktop](https://www.docker.com/products/docker-desktop/) or any compatible Docker Engine before continuing.

### 🐳 With Docker (Recommended)

```bash
# With default settings (port 8000, prod environment)
docker compose up -d

# With custom environment variables
MCP_PORT=8007 DATAGOUV_ENV=demo docker compose up -d

# Stop
docker compose down
```

**Environment variables:**
- `MCP_PORT`: port for the FastMCP HTTP server (defaults to `8000` when unset).
- `DATAGOUV_ENV`: `prod` (default) or `demo`. This controls which data.gouv.fr API/website the helpers call and automatically picks the appropriate Tabular API endpoint (`https://tabular-api.data.gouv.fr/api/` for prod, `https://tabular-api.preprod.data.gouv.fr/api/` for demo).

By default the MCP server talks to the production data.gouv.fr API and Tabular API. Set `DATAGOUV_ENV=demo` if you specifically need the demo environment.

### Manual Installation

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
  # Allowed values: demo | prod (defaults to prod when unset)
  DATAGOUV_ENV=prod
  ```

  Load the variables with your preferred method, e.g.:
  ```bash
  set -a && source .env && set +a
  ```

3. **Start the HTTP MCP server**
   ```bash
   uv run main.py
   ```

## 2. Connect your chatbot to the MCP server

The MCP server configuration depends on your client. Use the appropriate configuration format for your client:

### Cursor

Cursor supports MCP servers through its settings. To configure the server:

1. Open Cursor Settings
2. Search for "MCP" or "Model Context Protocol"
3. Add a new MCP server with the following configuration:

```json
{
  "mcpServers": {
    "datagouv": {
      "url": "http://127.0.0.1:8000/mcp",
      "transport": "http"
    }
  }
}
```

### Gemini CLI

Add the following to your `~/.gemini/settings.json` file:

```json
{
  "mcpServers": {
    "datagouv": {
      "transport": "http",
      "httpUrl": "http://127.0.0.1:8000/mcp"
    }
  }
}
```

### Claude Desktop

Add the following to your Claude Desktop configuration file (typically `~/Library/Application Support/Claude/claude_desktop_config.json` on MacOS, or `%APPDATA%\Claude\claude_desktop_config.json` on Windows):

```json
{
  "mcpServers": {
    "datagouv": {
      "command": "npx",
      "args": [
        "mcp-remote",
        "http://127.0.0.1:8000/mcp"
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
    "datagouv": {
      "url": "http://127.0.0.1:8000/mcp",
      "type": "http"
    }
  }
}
```

### Windsurf

Add the following to your `~/.codeium/mcp_config.json`:

```json
{
  "mcpServers": {
    "datagouv": {
      "command": "npx",
      "args": [
        "-y",
        "mcp-remote",
        "http://127.0.0.1:8000/mcp"
      ]
    }
  }
}
```

**Note:**
- Replace `http://127.0.0.1:8000/mcp` with your actual server URL if running on a different host or port. For production deployments, use `https://` and configure the appropriate hostname.
- This MCP server only exposes read-only tools for now, so no API key is required.

## 🧭 Test with MCP Inspector

Use the official MCP Inspector to interactively test the server tools and resources.

Prerequisites:
- Node.js with `npx` available

Steps:
1. Start the MCP server (see above)
2. In another terminal, launch the inspector:
   ```bash
   npx @modelcontextprotocol/inspector --http-url "http://127.0.0.1:${MCP_PORT}/mcp"
   ```
   Adjust the URL if you exposed the server on another host/port.

## 🚚 Transport support

This MCP server uses FastMCP and implements the **Streamable HTTP transport only**.
**STDIO and SSE are not supported**.

## 📋 Available Endpoints

**Streamable HTTP transport (standards-compliant):**
- `POST /mcp` - JSON-RPC messages (client → server)

## 🛠️ Available Tools

The MCP server provides tools to interact with data.gouv.fr datasets:

- **`search_datasets`** - Search for datasets by keywords. Returns datasets with metadata (title, description, organization, tags, resource count).

  Parameters: `query` (required), `page` (optional, default: 1), `page_size` (optional, default: 20, max: 100)

- **`get_dataset_info`** - Get detailed information about a specific dataset (metadata, organization, tags, dates, license, etc.).

  Parameters: `dataset_id` (required)

- **`list_dataset_resources`** - List all resources (files) in a dataset with their metadata (format, size, type, URL).

  Parameters: `dataset_id` (required)

- **`get_resource_info`** - Get detailed information about a specific resource (format, size, MIME type, URL, dataset association, Tabular API availability).

  Parameters: `resource_id` (required)

- **`query_dataset_data`** - Query data from a dataset via the Tabular API. Finds a dataset, retrieves its resources, and fetches rows to answer questions.

  Parameters: `question` (required), `dataset_id` (optional), `dataset_query` (optional), `limit_per_resource` (optional, default: 100)

  Note: Either `dataset_id` or `dataset_query` must be provided. Works for CSV/XLS resources within Tabular API size limits (CSV ≤ 100 MB, XLSX ≤ 12.5 MB).

- **`download_and_parse_resource`** - Download and parse a resource that is not accessible via Tabular API (files too large, formats not supported, external URLs).

  Parameters: `resource_id` (required), `max_rows` (optional, default: 1000), `max_size_mb` (optional, default: 500)

  Supported formats: CSV, CSV.GZ, JSON, JSONL. Useful for files exceeding Tabular API limits or formats not supported by Tabular API.

## 🧪 Tests

Run the tests with pytest:

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

### 🏷️ Releases and versioning

The release process uses the [`tag_version.sh`](tag_version.sh) script to create git tags, GitHub releases and update [CHANGELOG.md](CHANGELOG.md) automatically. Package version numbers are automatically derived from git tags using [setuptools_scm](https://github.com/pypa/setuptools_scm), so no manual version updates are needed in `pyproject.toml`.

**Prerequisites**: [GitHub CLI](https://cli.github.com/) must be installed and authenticated, and you must be on the main branch with a clean working directory.

```bash
# Create a new release
./tag_version.sh <version>

# Example
./tag_version.sh 2.5.0

# Dry run to see what would happen
./tag_version.sh 2.5.0 --dry-run
```

The script automatically:
- Extracts commits since the last tag and formats them for CHANGELOG.md
- Identifies breaking changes (commits with `!:` in the subject)
- Creates a git tag and pushes it to the remote repository
- Creates a GitHub release with the changelog content

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
