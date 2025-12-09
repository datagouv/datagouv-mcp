# Changelog

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
