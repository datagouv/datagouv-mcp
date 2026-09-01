import os

from helpers.ssrf import SSRFPolicy, ssrf_policy_for

_ENV_TARGETS = {
    "demo": {
        "datagouv_api": "https://demo.data.gouv.fr/api/",
        "site": "https://demo.data.gouv.fr/",
        "tabular_api": "https://tabular-api.preprod.data.gouv.fr/api/",
        "metrics_api": "https://metric-api.data.gouv.fr/api/",  # No demo/preprod for Metrics API
        "crawler_api": "https://demo-crawler.data.gouv.fr/api/",
    },
    "prod": {
        "datagouv_api": "https://www.data.gouv.fr/api/",
        "site": "https://www.data.gouv.fr/",
        "tabular_api": "https://tabular-api.data.gouv.fr/api/",
        "metrics_api": "https://metric-api.data.gouv.fr/api/",
        "crawler_api": "https://crawler.data.gouv.fr/api/",
    },
}


def get_base_url(api_name: str) -> str:
    """
    Get the base URL for a specific API in the current environment.

    Reads DATAGOUV_API_ENV environment variable (demo|prod). Defaults to prod if not set or invalid.

    Args:
        api_name: API name to get the endpoint for.
                  Valid values: "datagouv_api", "site", "tabular_api", "metrics_api", "crawler_api"

    Returns:
        The API endpoint URL as a string.

    Raises:
        KeyError: If api_name is not a valid API name.
    """
    env_name: str = os.getenv("DATAGOUV_API_ENV", "prod").strip().lower()
    if env_name not in _ENV_TARGETS:
        env_name = "prod"
    config: dict = _ENV_TARGETS[env_name]
    if api_name not in config:
        raise KeyError(
            f"Invalid api_name: {api_name}. "
            f"Valid values are: {', '.join(config.keys())}"
        )
    return config[api_name]


def _env_flag(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}


def get_ssrf_policy() -> SSRFPolicy:
    """
    Operator SSRF policy, matching udata ``URLS_ALLOW_*`` (prod = no local/private).

    Set ``URLS_ALLOW_LOCAL`` / ``URLS_ALLOW_PRIVATE`` to true only for trusted
    local tooling. Hosted MCP must keep the defaults.
    """
    private = _env_flag("URLS_ALLOW_PRIVATE")
    return ssrf_policy_for(
        local=_env_flag("URLS_ALLOW_LOCAL"),
        private=private,
    )
