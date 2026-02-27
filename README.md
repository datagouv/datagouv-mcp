# data.gouv.fr MCP Server

[![CircleCI](https://circleci.com/gh/datagouv/datagouv-mcp.svg?style=svg)](https://circleci.com/gh/datagouv/datagouv-mcp)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Model Context Protocol (MCP) server that allows AI chatbots (Claude, ChatGPT, Gemini, etc.) to search, explore, and analyze datasets from [data.gouv.fr](https://www.data.gouv.fr), the French national Open Data platform, directly through conversation.

Instead of manually browsing the website, you can simply ask questions like "Quels jeux de données sont disponibles sur les prix de l'immobilier ?" or "Montre-moi les dernières données de population pour Paris" and get instant answers.

> [!TIP]
> Use it now: A public instance is available for everyone at https://mcp.data.gouv.fr/mcp with no access restrictions.
> To connect your favorite chatbot, simply follow [the connection instructions below](#-connect-your-chatbot-to-the-mcp-server).

## 🌐 Connect your chatbot to the MCP server

Use the hosted endpoint `https://mcp.data.gouv.fr/mcp` (recommended). If you self-host, swap in your own URL.

The MCP server configuration depends on your client. Use the appropriate configuration format for your client:

### ChatGPT

*Available for paid plans only (Plus, Pro, Team, and Enterprise).*

1. **Access Settings**: Open ChatGPT in your browser, go to `Settings`, then `Apps and connectors`.
2. **Enable Dev Mode**: Open `Advanced settings` and enable **Developer mode**.
3. **Add Connector**: Return to `Settings` > `Connectors` > `Browse connectors` and click **Add a new connector**.
4. **Configure the connector**: Set the URL to `https://mcp.data.gouv.fr/mcp` and save to activate the tools.

### Claude Desktop

Add the following to your Claude Desktop configuration file (typically `~/Library/Application Support/Claude/claude_desktop_config.json` on MacOS, or `%APPDATA%\Claude\claude_desktop_config.json` on Windows):

```json
{
  "mcpServers": {
    "datagouv": {
      "command": "npx",
      "args": [
        "mcp-remote",
        "https://mcp.data.gouv.fr/mcp"
      ]
    }
  }
}
```

### Claude Code

Use the `claude mcp` command to add the MCP server:

```shell
claude mcp add --transport http datagouv https://mcp.data.gouv.fr/mcp
```

### Gemini CLI

Add the following to your `~/.gemini/settings.json` file:

```json
{
  "mcpServers": {
    "datagouv": {
      "transport": "http",
      "httpUrl": "https://mcp.data.gouv.fr/mcp"
    }
  }
}
```

### Mistral Vibe CLI

Edit your Vibe config (default `~/.vibe/config.toml`) and add the MCP server:

```toml
[[mcp_servers]]
name = "datagouv"
transport = "streamable-http"
url = "https://mcp.data.gouv.fr/mcp"
```

See the full Vibe MCP options in the official docs: [MCP server configuration](https://github.com/mistralai/mistral-vibe?tab=readme-ov-file#mcp-server-configuration).

### AnythingLLM

1. Locate the `anythingllm_mcp_servers.json` file in your AnythingLLM storage plugins directory:
   - **Mac**: `~/Library/Application Support/anythingllm-desktop/storage/plugins/anythingllm_mcp_servers.json`
   - **Linux**: `~/.config/anythingllm-desktop/storage/plugins/anythingllm_mcp_servers.json`
   - **Windows**: `C:\Users\<username>\AppData\Roaming\anythingllm-desktop\storage\plugins\anythingllm_mcp_servers.json`

2. Add the following configuration:

```json
{
  "mcpServers": {
    "datagouv": {
      "type": "streamable",
      "url": "https://mcp.data.gouv.fr/mcp"
    }
  }
}
```

For more details, see the [AnythingLLM MCP documentation](https://docs.anythingllm.com/mcp-compatibility/overview).

### VS Code

Add the following to your VS Code `settings.json`:

```json
{
  "servers": {
    "datagouv": {
      "url": "https://mcp.data.gouv.fr/mcp",
      "type": "http"
    }
  }
}
```

### Cursor

Cursor supports MCP servers through its settings. To configure the server:

1. Open Cursor Settings
2. Search for "MCP" or "Model Context Protocol"
3. Add a new MCP server with the following configuration:

```json
{
  "mcpServers": {
    "datagouv": {
      "url": "https://mcp.data.gouv.fr/mcp",
      "transport": "http"
    }
  }
}
```

### IBM Bob

IBM Bob supports MCP servers through its settings. To configure the server:

1. Click the setting icon in the Bob panel.
2. Select the MCP tab.
3. Click the appropriate button:
  - Edit Global MCP: Opens the global `mcp_settings.json` file
  - Edit Project MCP: Opens the project-specific `.bob/mcp.json` file (Bob creates it if it does not exist)

Both files use JSON format with an mcpServers object containing named server configurations.

```json
{
  "mcpServers": {
    "datagouv": {
      "url": "https://mcp.data.gouv.fr/mcp",
      "type": "streamable-http"
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
        "https://mcp.data.gouv.fr/mcp"
      ]
    }
  }
}
```

**Note:**
- The hosted endpoint is `https://mcp.data.gouv.fr/mcp`. If you run the server yourself, replace it with your own URL (see “Run locally” below for the default local endpoint).
- This MCP server only exposes read-only tools for now, so no API key is required.

## 🖥️ Run locally

### 1. Run the MCP server

Before starting, clone this repository and browse into it:

```shell
git clone git@github.com:datagouv/datagouv-mcp.git
cd datagouv-mcp
```

Docker is required for the recommended setup. Install it via [Docker Desktop](https://www.docker.com/products/docker-desktop/) or any compatible Docker Engine before continuing.

#### 🐳 With Docker (Recommended)

```shell
# With default settings (port 8000, prod environment)
docker compose up -d

# With custom environment variables
MCP_PORT=8007 DATAGOUV_ENV=demo docker compose up -d

# Stop
docker compose down
```

**Environment variables:**
- `MCP_HOST`: host to bind to (defaults to `0.0.0.0`). Set to `127.0.0.1` for local development to follow MCP security best practices.
- `MCP_PORT`: port for the MCP HTTP server (defaults to `8000` when unset).
- `DATAGOUV_ENV`: `prod` (default) or `demo`. This controls which data.gouv.fr environement it uses the data from (https://www.data.gouv.fr or https://demo.data.gouv.fr). By default the MCP server talks to the production data.gouv.fr. Set `DATAGOUV_ENV=demo` if you specifically need the demo environment.

#### ⚙️ Manual Installation

You will need [uv](https://github.com/astral-sh/uv) to install dependencies and run the server.

1. **Install dependencies**
  ```shell
  uv sync
  ```

2. **Prepare the environment file**

  Copy the [example environment file](.env.example) to create your own `.env` file:
  ```shell
  cp .env.example .env
  ```

  Then optionally edit `.env` and set the variables that matter for your run:
  ```
  MCP_HOST=127.0.0.1  # (defaults to 0.0.0.0, use 127.0.0.1 for local dev)
  MCP_PORT=8007  # (defaults to 8000 when unset)
  DATAGOUV_ENV=prod  # Allowed values: demo | prod (defaults to prod when unset)
  ```

  Load the variables with your preferred method, e.g.:
  ```shell
  set -a && source .env && set +a
  ```

3. **Start the HTTP MCP server**
  ```shell
  uv run main.py
  ```

### 2. Connect your chatbot to the local MCP server

Follow the steps in [Connect your chatbot to the MCP server](#-connect-your-chatbot-to-the-mcp-server) and simply swap the hosted URL for your local endpoint (default: `http://127.0.0.1:${MCP_PORT:-8000}/mcp`).

## 🚚 Transport support

The MCP server is built using the [official Python SDK for MCP servers and clients](https://github.com/modelcontextprotocol/python-sdk) and uses the **Streamable HTTP transport only**.

**STDIO and SSE are not supported**.

## 📋 Available Endpoints

**Streamable HTTP transport (standards-compliant):**
- `POST /mcp` - JSON-RPC messages (client → server)
- `GET /health` - Simple JSON health probe (`{"status":"ok","timestamp":"..."}`)

## 🛠️ Available Tools

The MCP server provides tools to interact with data.gouv.fr datasets and dataservices.

**Note:** "Dataservices" are external third-party APIs (e.g., Adresse API, Sirene API) registered in the data.gouv.fr catalog. They are distinct from data.gouv.fr's own internal APIs (Main/Tabular/Metrics) which power this MCP server.

### Datasets (static data files)

- **`search_datasets`** - Search for datasets by keywords. Returns datasets with metadata (title, description, organization, tags, resource count).

  Parameters: `query` (required), `page` (optional, default: 1), `page_size` (optional, default: 20, max: 100)

- **`get_dataset_info`** - Get detailed information about a specific dataset (metadata, organization, tags, dates, license, etc.).

  Parameters: `dataset_id` (required)

- **`list_dataset_resources`** - List all resources (files) in a dataset with their metadata (format, size, type, URL).

  Parameters: `dataset_id` (required)

- **`get_resource_info`** - Get detailed information about a specific resource (format, size, MIME type, URL, dataset association, Tabular API availability).

  Parameters: `resource_id` (required)

- **`query_resource_data`** - Query data from a specific resource via the Tabular API. Fetches rows from a resource to answer questions.

  Parameters: `question` (required), `resource_id` (required), `page` (optional, default: 1), `page_size` (optional, default: 20, max: 200)

  Note: Recommended workflow: 1) Use `search_datasets` to find the dataset, 2) Use `list_dataset_resources` to see available resources, 3) Use `query_resource_data` with default `page_size` (20) to preview data structure. For small datasets (<500 rows), increase `page_size` or paginate. For large datasets (>1000 rows), use `download_and_parse_resource` instead. Works for CSV/XLS resources within Tabular API size limits (CSV ≤ 100 MB, XLSX ≤ 12.5 MB).

- **`download_and_parse_resource`** - Download and parse a resource that is not accessible via Tabular API (files too large, formats not supported, external URLs).

  Parameters: `resource_id` (required), `max_rows` (optional, default: 20), `max_size_mb` (optional, default: 500)

  Supported formats: CSV, CSV.GZ, JSON, JSONL. Useful for files exceeding Tabular API limits or formats not supported by Tabular API. Start with default max_rows (20) to preview, then call again with higher max_rows if you need all data.

### Dataservices (external APIs)

- **`search_dataservices`** - Search for dataservices (APIs) registered on data.gouv.fr by keywords. Returns dataservices with metadata (title, description, organization, base API URL, tags).

  Parameters: `query` (required), `page` (optional, default: 1), `page_size` (optional, default: 20, max: 100)

- **`get_dataservice_info`** - Get detailed metadata about a specific dataservice (title, description, organization, base API URL, OpenAPI spec URL, license, dates, related datasets).

  Parameters: `dataservice_id` (required)

- **`get_dataservice_openapi_spec`** - Fetch and summarize the OpenAPI/Swagger specification for a dataservice. Returns a concise overview of available endpoints with their parameters.

  Parameters: `dataservice_id` (required)

  Note: Recommended workflow: 1) Use `search_dataservices` to find the API, 2) Use `get_dataservice_info` to get its metadata and documentation URL, 3) Use `get_dataservice_openapi_spec` to understand available endpoints and parameters, 4) Call the API using the `base_api_url` per the spec.

### Metrics

- **`get_metrics`** - Get metrics (visits, downloads) for a dataset and/or a resource.

  Parameters: `dataset_id` (optional), `resource_id` (optional), `limit` (optional, default: 12, max: 100)

  Returns monthly statistics including visits and downloads, sorted by month in descending order (most recent first). At least one of `dataset_id` or `resource_id` must be provided. **Note:** This tool only works with the production environment (`DATAGOUV_ENV=prod`). The Metrics API does not have a demo/preprod environment.

## 🧪 Tests

### ✅ Automated Tests with pytest

Run the tests with pytest (these cover helper modules; the MCP server wiring is best exercised via the MCP Inspector):

```shell
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

### 🔍 Interactive Testing with MCP Inspector

Use the official [MCP Inspector](https://modelcontextprotocol.io/docs/tools/inspector) to interactively test the server tools and resources.

Prerequisites:
- Node.js with `npx` available

Steps:
1. Start the MCP server (see above)
2. In another terminal, launch the inspector:
   ```shell
   npx @modelcontextprotocol/inspector --http-url "http://127.0.0.1:${MCP_PORT}/mcp"
   ```
   Adjust the URL if you exposed the server on another host/port.

## 🤝 Contributing

We welcome contributions! To keep the project stable, we use a standard review-and-deploy process:

1. **Submit a PR:** Propose your changes via a Pull Request against the `main` branch.
2. **Review:** All PRs must be reviewed and approved by a maintainer before merging.
3. **Automated Deployment:** Once merged into `main`, changes are automatically deployed to:
   * **[Pre-production](https://mcp.preprod.data.gouv.fr/)** for final validation
   * **Production** (the official endpoint)

### 🧹 Code Linting and Formatting

This project follows PEP 8 style guidelines using [Ruff](https://astral.sh/ruff/) for linting and formatting, and [ty](https://docs.astral.sh/ty/) for type checking.

**Either running these commands manually or [installing the pre-commit hook](#-pre-commit-hooks) is required before submitting contributions.**

```shell
# Lint (including import sorting) and format code
uv run ruff check --fix && uv run ruff format

# Type check (ty)
uv run ty check
```

### 🔗 Pre-commit Hooks

This repository uses a [pre-commit](https://pre-commit.com/) hook which lint and format code before each commit. Installing the pre-commit hook is strongly recommended so the checks run automatically.

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

```shell
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
