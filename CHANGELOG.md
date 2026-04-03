# Changelog

## 0.2.22 (2026-04-02)

- chore: update dependencies to fix dependabot alerts ([#79](https://github.com/datagouv/datagouv-mcp/pull/79))
- chore(logging): add structured logging for MCP tool calls
- chore(logging): add unit test
- ci: run workflow on all branches; align Ruff imports with CI ([#81](https://github.com/datagouv/datagouv-mcp/pull/81))
- docs: improve contributing guidelines ([#82](https://github.com/datagouv/datagouv-mcp/pull/82))
- feat(matomo): read base URL from env and skip tracking when unset ([#89](https://github.com/datagouv/datagouv-mcp/pull/89))
- fix: get_metrics limit exceeds API maximum ([#75](https://github.com/datagouv/datagouv-mcp/pull/75))
- fix: handle None values in metrics to prevent TypeError ([#78](https://github.com/datagouv/datagouv-mcp/pull/78))
- fix: typo
- fix(logging): import logger name var ([#80](https://github.com/datagouv/datagouv-mcp/pull/80))
- fix(matomo): use shared httpx client instead of per-request client ([#88](https://github.com/datagouv/datagouv-mcp/pull/88))
- test: add stress test for client disconnect handling ([#83](https://github.com/datagouv/datagouv-mcp/pull/83))


## 0.2.20 (2026-03-04)

- feat: better health check ([#64](https://github.com/datagouv/datagouv-mcp/pull/64))
- feat: remove download_and_parse_resource tool ([#66](https://github.com/datagouv/datagouv-mcp/pull/66))


## 0.2.19 (2026-03-04)

- docs: add TODO
- docs: improve README for instructions about chatbots
- feat: include version in user-agent
- feat: mcp sends a specific user agent to datagouv service
- fix: allow localhost with port in allowed_hosts for local MCP clients
- fix: fix wrong max value
- fix: remove slicing in _parse_json response
- fix(download): harden RAM limits in download_and_parse_resource
- tests: test user-agent


## 0.2.18 (2026-03-03)

- docs: update README with IBM Bob server type from 'http' to 'streamable-http'
- chore: remove unused import in list_dataset_resources
- clean: remove non-IDE-agnostic skills
- docs: add kiro IDE instructions
- docs: add Mistral instructions to README
- docs: fix minor issue in ordering
- docs: fix minor issue in ordering in README
- docs: fix minor ordering issue in README
- docs: fix minor README indentation typo
- docs: fix typo
- docs: improve contributing guidelines in README
- docs: improve README
- docs: minor README indentation fix
- docs: reorder env vars to keep LOG_LEVEL last
- docs: update README.md
- docs: enhance README with image cover
- feat: add LOG_LEVEL support in main logging config
- feat(monitoring): add Sentry error and performance tracking
- fix: address review feedback for LOG_LEVEL
- fix: align docker-compose env with DATAGOUV_ENV
- fix: enable stateless HTTP to fix "Session not found" for most MCP clients
- fix: normalize env var name
- fix: normalize env var names
- fix: Remove 'transport' field for the Gemini CLI configuration
- fix: safer default for MCP_ENV
- fix: use /health for docker compose healthcheck
- fix: validate filter and sort options in query_resource_data
- perf: remove N+1 calls in list_dataset_resources
- perf: use bytearray buffering in resource downloader
- refactor: rename DATAGOUV_ENV to DATAGOUV_API_ENV
- docs: update README with HuggingChat server setup instructions
- docs: update README with IBM Bob MCP configuration details
## 0.2.17 (2026-02-26)

- docs: reformat ChatGPT section
- docs: update README
- feat: add matomo tracking
- fix: fix matomo tracking


## 0.2.16 (2026-02-23)

- chore: update dependency for security
- docs: improve README for contributing section
- feat: add type checking


## 0.2.15 (2026-02-23)

- docs: add disambiguation about dataservices
- docs: update README
- feat: add 3 dataservices tools


## 0.2.14 (2026-01-27)

- fix: upgrade dependencies to fix security issue related to python-multipart


## 0.2.13 (2026-01-23)

- feat: query_resource_data and download_and_parse_data now returns everything as requested by the LLM
- feat(query_resource_data): add filtering and sorting parameters


## 0.2.12 (2026-01-23)

- docs: update Cursor .md docs
- feat: add allowed_origins and MCP_HOST local var to comply with official MCP specs
- feat: upgrade mcp to 1.25 with DNS rebinding protection config
- Revise ChatGPT connection instructions in README


## 0.2.11 (2026-01-13)

- docs: streamline tool docstrings for better LLM efficiency
- fix: add page_size argument for query_resource_data tool with 20 as a default, so that the LLM can preview the resource


## 0.2.10 (2026-01-13)

- chore: revert mcp to 1.22 and update other dependencies
- Revert "fix(server): allow all hosts to prevent 421 Invalid Host header errors"


## 0.2.9 (2026-01-12)

- fix: adapt to new headers in tabular-api which fix tests
- fix: fix issue [#2](https://github.com/datagouv/datagouv-mcp/pull/2): use tabular-api anyway when it's a resource exception
- fix(server): allow all hosts to prevent 421 Invalid Host header errors


## 0.2.8 (2026-01-07)

- chore: fix tag_version.sh for trailing slashes in CHANGELOG
- docs: add Mistral Vibe CLI in README
- docs: update README
- feat: add version in health check


## 0.2.7 (2025-12-09)

- build: use Python 3.14 instead of 3.13 in docker container
- chore: remove wrong logs for tag_version.sh
- chore: update dependencies
- chore: use [dependency-groups] for dev dependencies
- docs: clarify dataset search stop-word handling
- docs: improve README
- docs: improve README
- docs: update README
- feat: search_datasets cleans query and removes stop words before querying API
- fix: fix tag_version.sh for MacOS


## 0.2.6 (2025-12-04)

- fix: fix tag_version.sh to work with MacOS
- docs: improve docstrings

- refactor!: add page parameter and remove limit from query_resource_data
  Add page parameter to enable pagination through large datasets. Remove
  limit parameter and always use maximum page size (200 rows) for better
  efficiency. This simplifies the API and reduces the number of calls
  needed to explore datasets.

  BREAKING CHANGE: limit parameter removed, page parameter added.
  Always returns up to 200 rows per page.

- **refactor!: rename query_dataset_data to query_resource_data, require resource_id
  Rename query_dataset_data to query_resource_data and change parameter
  from dataset_id to resource_id. This enforces a clearer workflow where
  the LLM must explicitly:
  1. Use search_datasets to find datasets
  2. Use list_dataset_resources to explore available resources
  3. Use query_resource_data with a specific resource_id

  This improves separation of concerns and forces better decision-making
  by the LLM when selecting which resource to query.

  BREAKING CHANGE: query_dataset_data renamed to query_resource_data.
  Parameter changed from dataset_id to resource_id. Use list_dataset_resources
  first to find resource IDs.

- refactor!: remove dataset_query parameter from query_dataset_data
  Remove the dataset_query parameter to enforce a two-step workflow:
  1. Use search_datasets to find and compare datasets
  2. Use query_dataset_data with the chosen dataset_id

  This improves separation of concerns and gives LLMs better control
  over dataset selection by allowing them to compare multiple options
  before querying data.

  BREAKING CHANGE: dataset_query parameter removed. dataset_id is now
  required. Use search_datasets tool first to find the appropriate
  dataset ID.

- docs: add doc for AnythingLLM
- docs: update README.md

## 0.2.5 (2025-12-01)

- build: fix optional dependencies
- chore: update packages
- ci: use CircleCI instead of GitHub Actions
- docs: add LICENSE
- docs: update LLM docs
- docs: update README
- docs: update README
- feat: add /health health check endpoint


## 0.2.4 (2025-11-27)

- chore: stop tracking .python-version file
- chore: update dependencies
- clean: use absolute imports
- docs: add docs for Claude code
- docs: minor README improvements
- docs: update README
- fix: fix docker-compose.yaml file for default DATAGOUV_API_ENV
- fix: fix get_metrics get_env logic
- refactor: merge branch related to refactor into separate files for each mcp tool
- refactor: one single logegr instance for the whole codebase
- refactor: replace aiohttp with httpx, which supports HTTP/2 and simplifies the code
- refactor: simplify get_env logic


## 0.2.3 (2025-11-26)

- docs: fix README to add "get_metrics in tools list
- feat: add automatic CSV delimiter detection


## 0.2.2 (2025-11-26)

- docs: update README
- feat: add "get_metrics" MCP tool
- feat: add metrics api client
- feat: default DATAGOUV_API_ENV to prod and update README
- refactor: refactor API clients to share a common env_config


## 0.2.1 (2025-11-26)

- docs: improve docs
- feat: remove edition tool "create_dataset" which needs API key auth
- Revert "ci: separate CI into parallel jobs"
- feat: default DATAGOUV_API_ENV to prod and update README


## 0.2.0 (2025-11-25)

- build: add a Dockerfile and docker compose file
- chore: add logs to tabular_api_client
- ci: add CI file
- ci: separate CI into parallel jobs
- docs: add CHANGELOG
- docs: fix docs for tests
- docs: fix README
- docs: update README
- docs: update README and add tag_version.sh
- feat: add logging configuration
- feat: add MCP tools "get_dataset_info", "list_dataset_resources", "get_resource_info" and "download_and_parse_resource"


## 0.1.0 (2025-11-25)

Initial commit
