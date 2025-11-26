"""Tests for the datagouv_api_client helper."""

import os

import pytest

from helpers import datagouv_api_client


@pytest.fixture
def known_dataset_id() -> str:
    """Fixture providing a known dataset ID for testing."""
    # Dataset ID for "Transports" (known to exist in demo)
    return os.getenv("TEST_DATASET_ID", "55e4129788ee386899a46ec1")


@pytest.fixture
def known_resource_id() -> str:
    """Fixture providing a known resource ID for testing."""
    # Resource ID from the "Élus locaux" dataset
    return "3b6b2281-b9d9-4959-ae9d-c2c166dff118"


class TestEnvironmentFunctions:
    """Tests for environment-related utility functions."""

    def test_get_current_environment_default(self, monkeypatch):
        """Test that get_current_environment defaults to demo."""
        monkeypatch.delenv("DATAGOUV_ENV", raising=False)
        assert datagouv_api_client.get_current_environment() == "demo"

    def test_get_current_environment_demo(self, monkeypatch):
        """Test that get_current_environment returns demo when set."""
        monkeypatch.setenv("DATAGOUV_ENV", "demo")
        assert datagouv_api_client.get_current_environment() == "demo"

    def test_get_current_environment_prod(self, monkeypatch):
        """Test that get_current_environment returns prod when set."""
        monkeypatch.setenv("DATAGOUV_ENV", "prod")
        assert datagouv_api_client.get_current_environment() == "prod"

    def test_get_current_environment_case_insensitive(self, monkeypatch):
        """Test that get_current_environment is case insensitive."""
        monkeypatch.setenv("DATAGOUV_ENV", "PROD")
        assert datagouv_api_client.get_current_environment() == "prod"

    def test_get_current_environment_invalid_defaults_to_demo(self, monkeypatch):
        """Test that invalid environment defaults to demo."""
        monkeypatch.setenv("DATAGOUV_ENV", "invalid")
        assert datagouv_api_client.get_current_environment() == "demo"


class TestURLFunctions:
    """Tests for URL generation functions."""

    def test_api_base_url_demo(self, monkeypatch):
        """Test api_base_url returns demo URL."""
        monkeypatch.setenv("DATAGOUV_ENV", "demo")
        url = datagouv_api_client.api_base_url()
        assert url == "https://demo.data.gouv.fr/api/"

    def test_api_base_url_prod(self, monkeypatch):
        """Test api_base_url returns prod URL."""
        monkeypatch.setenv("DATAGOUV_ENV", "prod")
        url = datagouv_api_client.api_base_url()
        assert url == "https://www.data.gouv.fr/api/"

    def test_frontend_base_url_demo(self, monkeypatch):
        """Test frontend_base_url returns demo URL."""
        monkeypatch.setenv("DATAGOUV_ENV", "demo")
        url = datagouv_api_client.frontend_base_url()
        assert url == "https://demo.data.gouv.fr/"

    def test_frontend_base_url_prod(self, monkeypatch):
        """Test frontend_base_url returns prod URL."""
        monkeypatch.setenv("DATAGOUV_ENV", "prod")
        url = datagouv_api_client.frontend_base_url()
        assert url == "https://www.data.gouv.fr/"

    def test_tabular_api_base_url_demo(self, monkeypatch):
        """Test tabular_api_base_url returns demo URL."""
        monkeypatch.setenv("DATAGOUV_ENV", "demo")
        url = datagouv_api_client.tabular_api_base_url()
        assert url == "https://tabular-api.preprod.data.gouv.fr/api/"

    def test_tabular_api_base_url_prod(self, monkeypatch):
        """Test tabular_api_base_url returns prod URL."""
        monkeypatch.setenv("DATAGOUV_ENV", "prod")
        url = datagouv_api_client.tabular_api_base_url()
        assert url == "https://tabular-api.data.gouv.fr/api/"


@pytest.mark.asyncio
class TestAsyncFunctions:
    """Tests for async API functions."""

    async def test_get_dataset_metadata(self, known_dataset_id):
        """Test fetching dataset metadata."""
        metadata = await datagouv_api_client.get_dataset_metadata(known_dataset_id)

        assert "id" in metadata
        assert metadata["id"] == known_dataset_id
        assert "title" in metadata
        assert metadata["title"] is not None

    async def test_get_resource_metadata(self, known_resource_id):
        """Test fetching resource metadata."""
        metadata = await datagouv_api_client.get_resource_metadata(known_resource_id)

        assert "id" in metadata
        assert metadata["id"] == known_resource_id
        assert "title" in metadata

    async def test_get_resource_and_dataset_metadata(self, known_resource_id):
        """Test fetching both resource and dataset metadata."""
        result = await datagouv_api_client.get_resource_and_dataset_metadata(
            known_resource_id
        )

        assert "resource" in result
        assert "dataset" in result
        assert result["resource"]["id"] == known_resource_id
        if result["dataset"]:
            assert "id" in result["dataset"]

    async def test_get_resources_for_dataset(self, known_dataset_id):
        """Test fetching resources for a dataset."""
        result = await datagouv_api_client.get_resources_for_dataset(known_dataset_id)

        assert "dataset" in result
        assert "resources" in result
        assert isinstance(result["resources"], list)
        assert result["dataset"]["id"] == known_dataset_id

        # Check resources structure
        if result["resources"]:
            resource_id, resource_title = result["resources"][0]
            assert isinstance(resource_id, str)
            assert len(resource_id) > 0

    async def test_search_datasets_basic(self):
        """Test basic dataset search."""
        result = await datagouv_api_client.search_datasets(
            "transports", page=1, page_size=5
        )

        assert "data" in result
        assert "page" in result
        assert "page_size" in result
        assert "total" in result
        assert result["page"] == 1
        assert isinstance(result["data"], list)

    async def test_search_datasets_pagination(self):
        """Test dataset search pagination."""
        page1 = await datagouv_api_client.search_datasets(
            "transports", page=1, page_size=3
        )
        page2 = await datagouv_api_client.search_datasets(
            "transports", page=2, page_size=3
        )

        assert page1["page"] == 1
        assert page2["page"] == 2
        assert len(page1["data"]) <= 3
        assert len(page2["data"]) <= 3

    async def test_search_datasets_structure(self):
        """Test that search results have correct structure."""
        result = await datagouv_api_client.search_datasets("transports", page_size=2)

        if result["data"]:
            dataset = result["data"][0]
            assert "id" in dataset
            assert "title" in dataset
            assert "url" in dataset
            assert "tags" in dataset
            assert isinstance(dataset["tags"], list)

    async def test_search_datasets_page_size_limit(self):
        """Test that page_size is limited to 100."""
        result = await datagouv_api_client.search_datasets("transports", page_size=200)

        # Should be capped at 100
        assert len(result["data"]) <= 100

    async def test_get_dataset_metadata_invalid_id(self):
        """Test that invalid dataset ID raises error."""
        invalid_id = "000000000000000000000000"
        with pytest.raises(Exception):  # Should raise HTTP error
            await datagouv_api_client.get_dataset_metadata(invalid_id)

    async def test_get_resource_metadata_invalid_id(self):
        """Test that invalid resource ID raises error."""
        invalid_id = "00000000-0000-0000-0000-000000000000"
        with pytest.raises(Exception):  # Should raise HTTP error
            await datagouv_api_client.get_resource_metadata(invalid_id)

    async def test_search_datasets_empty_query(self):
        """Test search with empty query."""
        result = await datagouv_api_client.search_datasets("", page_size=1)
        # Should not crash, may return empty or some results
        assert "data" in result
        assert isinstance(result["data"], list)
