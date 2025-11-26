import os

_ENV_TARGETS = {
    "demo": {
        "datagouv_api": "https://demo.data.gouv.fr/api/",
        "site": "https://demo.data.gouv.fr/",
        "tabular_api": "https://tabular-api.preprod.data.gouv.fr/api/",
        "metrics_api": "https://metric-api.data.gouv.fr/api/",  # No demo/preprod for Metrics API
    },
    "prod": {
        "datagouv_api": "https://www.data.gouv.fr/api/",
        "site": "https://www.data.gouv.fr/",
        "tabular_api": "https://tabular-api.data.gouv.fr/api/",
        "metrics_api": "https://metric-api.data.gouv.fr/api/",
    },
}


def get_base_url(api_name: str) -> str:
    """
    Get the base URL for a specific API in the current environment.

    Reads DATAGOUV_ENV environment variable (demo|prod). Defaults to prod if not set or invalid.

    Args:
        api_name: API name to get the endpoint for.
                  Valid values: "datagouv_api", "site", "tabular_api", "metrics_api"

    Returns:
        The API endpoint URL as a string.

    Raises:
        KeyError: If api_name is not a valid API name.
    """
    env_name: str = os.getenv("DATAGOUV_ENV", "prod").strip().lower()
    if env_name not in _ENV_TARGETS:
        env_name = "prod"
    config: dict = _ENV_TARGETS[env_name]
    if api_name not in config:
        raise KeyError(
            f"Invalid api_name: {api_name}. "
            f"Valid values are: {', '.join(config.keys())}"
        )
    return config[api_name]
