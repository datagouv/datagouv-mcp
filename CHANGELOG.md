# Changelog

## 0.2.4 (2025-11-27)

- chore: stop tracking .python-version file
- chore: update dependencies
- clean: use absolute imports
- docs: add docs for Claude code
- docs: minor README improvements
- docs: update README
- fix: fix docker-compose.yaml file for default DATAGOUV_ENV
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
- feat: default DATAGOUV_ENV to prod and update README
- refactor: refactor API clients to share a common env_config


## 0.2.1 (2025-11-26)

- docs: improve docs
- feat: remove edition tool "create_dataset" which needs API key auth
- Revert "ci: separate CI into parallel jobs"
- feat: default DATAGOUV_ENV to prod and update README


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
