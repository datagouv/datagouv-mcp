"""Tests for the datagouv_api_client helper."""

import os

import pytest

from helpers import datagouv_api_client

pytestmark = pytest.mark.integration


@pytest.fixture
def known_dataset_id() -> str:
    """Fixture providing a known dataset ID for testing."""
    # Dataset ID for "Transports" (known to exist in demo and prod)
    return os.getenv("TEST_DATASET_ID", "55e4129788ee386899a46ec1")


@pytest.fixture
def known_resource_id() -> str:
    """Fixture providing a known resource ID for testing."""
    # Resource ID from the "Élus locaux" dataset
    return "3b6b2281-b9d9-4959-ae9d-c2c166dff118"


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
            resource = result["resources"][0]
            assert isinstance(resource, dict)
            assert isinstance(resource.get("id"), str)
            assert resource.get("id")
            assert "title" in resource

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

    async def test_get_resource_details(self, known_resource_id):
        """Test fetching full resource details payload."""
        details = await datagouv_api_client.get_resource_details(known_resource_id)

        assert "resource" in details
        assert details.get("dataset_id") is not None
        resource = details["resource"]
        assert resource.get("id") == known_resource_id
        assert resource.get("title") or resource.get("name")

    async def test_get_dataset_details(self, known_dataset_id):
        """Test fetching full dataset details payload."""
        details = await datagouv_api_client.get_dataset_details(known_dataset_id)

        assert details.get("id") == known_dataset_id
        assert details.get("title") or details.get("name")
        assert isinstance(details.get("resources", []), list)

    async def test_search_dataservices_basic(self):
        """Test basic dataservice search."""
        result = await datagouv_api_client.search_dataservices(
            "adresse", page=1, page_size=5
        )

        assert "data" in result
        assert "page" in result
        assert "page_size" in result
        assert "total" in result
        assert result["page"] == 1
        assert isinstance(result["data"], list)

    async def test_search_dataservices_structure(self):
        """Test that dataservice search results have correct structure."""
        result = await datagouv_api_client.search_dataservices("adresse", page_size=2)

        if result["data"]:
            ds = result["data"][0]
            assert "id" in ds
            assert "title" in ds
            assert "url" in ds
            assert "tags" in ds
            assert isinstance(ds["tags"], list)
            # Dataservice-specific fields
            assert "base_api_url" in ds
            assert "machine_documentation_url" in ds

    async def test_search_dataservices_empty_query(self):
        """Test dataservice search with empty query."""
        result = await datagouv_api_client.search_dataservices("", page_size=1)
        assert "data" in result
        assert isinstance(result["data"], list)

    async def test_get_dataservice_details(self):
        """Test fetching full dataservice details payload."""
        # API Adresse (BAN) — known to have base_api_url and machine_documentation_url
        dataservice_id = "672cf67802ef6b1be63b8975"
        details = await datagouv_api_client.get_dataservice_details(dataservice_id)

        assert details.get("id") == dataservice_id
        assert details.get("title")
        assert details.get("base_api_url")
        assert details.get("machine_documentation_url")

    async def test_get_dataservice_details_invalid_id(self):
        """Test that invalid dataservice ID raises error."""
        invalid_id = "000000000000000000000000"
        with pytest.raises(Exception):
            await datagouv_api_client.get_dataservice_details(invalid_id)

    async def test_fetch_openapi_spec_yaml(self):
        """Test fetching an OpenAPI spec in YAML format."""
        # API Adresse (BAN) — YAML spec
        url = "https://data.geopf.fr/geocodage/openapi.yaml"
        spec = await datagouv_api_client.fetch_openapi_spec(url)

        assert isinstance(spec, dict)
        # Should have standard OpenAPI fields
        assert "info" in spec or "swagger" in spec or "openapi" in spec
        assert "paths" in spec

    async def test_fetch_openapi_spec_invalid_url(self):
        """Test that fetching from an invalid URL raises error."""
        with pytest.raises(Exception):
            await datagouv_api_client.fetch_openapi_spec(
                "https://example.com/nonexistent-spec.json"
            )
