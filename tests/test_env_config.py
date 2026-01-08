"""Tests for the env_config helper."""

import pytest

from helpers import env_config


class TestGetBaseUrl:
    """Tests for get_base_url function."""

    def test_get_base_url_defaults_to_prod(self, monkeypatch):
        """Test that get_base_url defaults to prod when DATAGOUV_ENV is not set."""
        monkeypatch.delenv("DATAGOUV_ENV", raising=False)
        url = env_config.get_base_url("datagouv_api")
        assert url == "https://www.data.gouv.fr/api/"

    def test_get_base_url_case_insensitive(self, monkeypatch):
        """Test that get_base_url is case insensitive for environment."""
        monkeypatch.setenv("DATAGOUV_ENV", "PROD")
        url = env_config.get_base_url("datagouv_api")
        assert url == "https://www.data.gouv.fr/api/"

    def test_get_base_url_invalid_defaults_to_prod(self, monkeypatch):
        """Test that invalid environment defaults to prod."""
        monkeypatch.setenv("DATAGOUV_ENV", "invalid")
        url = env_config.get_base_url("datagouv_api")
        assert url == "https://www.data.gouv.fr/api/"

    @pytest.mark.parametrize(
        "api_name,env,expected_url",
        [
            ("datagouv_api", "demo", "https://demo.data.gouv.fr/api/"),
            ("datagouv_api", "prod", "https://www.data.gouv.fr/api/"),
            ("site", "demo", "https://demo.data.gouv.fr/"),
            ("site", "prod", "https://www.data.gouv.fr/"),
            ("tabular_api", "demo", "https://tabular-api.preprod.data.gouv.fr/api/"),
            ("tabular_api", "prod", "https://tabular-api.data.gouv.fr/api/"),
            ("metrics_api", "demo", "https://metric-api.data.gouv.fr/api/"),
            ("metrics_api", "prod", "https://metric-api.data.gouv.fr/api/"),
            ("crawler_api", "demo", "https://demo-crawler.data.gouv.fr/api/"),
            ("crawler_api", "prod", "https://crawler.data.gouv.fr/api/"),
        ],
    )
    def test_get_base_url_for_api_and_env(
        self, monkeypatch, api_name, env, expected_url
    ):
        """Test get_base_url returns correct URL for each API and environment."""
        monkeypatch.setenv("DATAGOUV_ENV", env)
        url = env_config.get_base_url(api_name)
        assert url == expected_url

    def test_get_base_url_invalid_api_name(self, monkeypatch):
        """Test that invalid api_name raises KeyError."""
        monkeypatch.setenv("DATAGOUV_ENV", "prod")
        with pytest.raises(KeyError, match="Invalid api_name"):
            env_config.get_base_url("invalid_api")
