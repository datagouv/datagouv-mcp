"""Tests for the create_dataset API client function and tool safety logic."""

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from helpers import datagouv_api_client, env_config


class TestGetApiKey:
    """Tests for the get_api_key helper."""

    def test_get_api_key_from_env(self, monkeypatch):
        monkeypatch.setenv("DATAGOUV_API_KEY", "test-key-123")
        assert env_config.get_api_key() == "test-key-123"

    def test_get_api_key_strips_whitespace(self, monkeypatch):
        monkeypatch.setenv("DATAGOUV_API_KEY", "  test-key-123  ")
        assert env_config.get_api_key() == "test-key-123"

    def test_get_api_key_returns_none_when_empty(self, monkeypatch):
        monkeypatch.setenv("DATAGOUV_API_KEY", "")
        assert env_config.get_api_key() is None

    def test_get_api_key_returns_none_when_whitespace_only(self, monkeypatch):
        monkeypatch.setenv("DATAGOUV_API_KEY", "   ")
        assert env_config.get_api_key() is None

    def test_get_api_key_returns_none_when_unset(self, monkeypatch):
        monkeypatch.delenv("DATAGOUV_API_KEY", raising=False)
        assert env_config.get_api_key() is None


@pytest.mark.asyncio
class TestCreateDatasetClient:
    """Tests for the create_dataset API client function."""

    async def test_create_dataset_builds_correct_payload(self):
        """Test that create_dataset sends the right payload to the API."""
        mock_response = httpx.Response(
            status_code=201,
            json={
                "id": "abc123",
                "title": "Test Dataset",
                "slug": "test-dataset",
                "private": True,
                "frequency": "monthly",
                "license": "fr-lo",
            },
            request=httpx.Request("POST", "https://www.data.gouv.fr/api/1/datasets/"),
        )

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.aclose = AsyncMock()

        result = await datagouv_api_client.create_dataset(
            title="Test Dataset",
            description="A test description",
            api_key="fake-key",
            frequency="monthly",
            organization="org-123",
            license_id="fr-lo",
            tags=["test", "example"],
            private=True,
            session=mock_client,
        )

        # Verify the API was called
        mock_client.post.assert_called_once()
        call_kwargs = mock_client.post.call_args

        # Check URL
        assert "/1/datasets/" in call_kwargs.args[0]

        # Check headers contain API key
        assert call_kwargs.kwargs["headers"]["X-API-KEY"] == "fake-key"

        # Check payload
        payload = call_kwargs.kwargs["json"]
        assert payload["title"] == "Test Dataset"
        assert payload["description"] == "A test description"
        assert payload["frequency"] == "monthly"
        assert payload["organization"] == "org-123"
        assert payload["license"] == "fr-lo"
        assert payload["tags"] == ["test", "example"]
        assert payload["private"] is True

        # Check result
        assert result["id"] == "abc123"
        assert result["title"] == "Test Dataset"

    async def test_create_dataset_without_organization(self):
        """Test that organization is omitted from payload when not provided."""
        mock_response = httpx.Response(
            status_code=201,
            json={"id": "abc123", "title": "Personal Dataset"},
            request=httpx.Request("POST", "https://www.data.gouv.fr/api/1/datasets/"),
        )

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.aclose = AsyncMock()

        await datagouv_api_client.create_dataset(
            title="Personal Dataset",
            description="Description",
            api_key="fake-key",
            session=mock_client,
        )

        payload = mock_client.post.call_args.kwargs["json"]
        assert "organization" not in payload

    async def test_create_dataset_without_tags(self):
        """Test that tags are omitted from payload when not provided."""
        mock_response = httpx.Response(
            status_code=201,
            json={"id": "abc123", "title": "No Tags Dataset"},
            request=httpx.Request("POST", "https://www.data.gouv.fr/api/1/datasets/"),
        )

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.aclose = AsyncMock()

        await datagouv_api_client.create_dataset(
            title="No Tags Dataset",
            description="Description",
            api_key="fake-key",
            session=mock_client,
        )

        payload = mock_client.post.call_args.kwargs["json"]
        assert "tags" not in payload

    async def test_create_dataset_defaults(self):
        """Test default values for optional parameters."""
        mock_response = httpx.Response(
            status_code=201,
            json={"id": "abc123"},
            request=httpx.Request("POST", "https://www.data.gouv.fr/api/1/datasets/"),
        )

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.aclose = AsyncMock()

        await datagouv_api_client.create_dataset(
            title="Defaults Test",
            description="Description",
            api_key="fake-key",
            session=mock_client,
        )

        payload = mock_client.post.call_args.kwargs["json"]
        assert payload["frequency"] == "unknown"
        assert payload["license"] == "fr-lo"
        assert payload["private"] is True

    async def test_create_dataset_http_error_propagates(self):
        """Test that HTTP errors from the API are raised."""
        mock_response = httpx.Response(
            status_code=401,
            json={"message": "Invalid API key"},
            request=httpx.Request("POST", "https://example.com"),
        )

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.aclose = AsyncMock()

        # raise_for_status() should be called inside _post_json
        # We need the mock to actually raise
        mock_response.raise_for_status = lambda: (_ for _ in ()).throw(
            httpx.HTTPStatusError(
                "401 Unauthorized",
                request=mock_response.request,
                response=mock_response,
            )
        )

        with pytest.raises(httpx.HTTPStatusError):
            await datagouv_api_client.create_dataset(
                title="Should Fail",
                description="Description",
                api_key="bad-key",
                session=mock_client,
            )


class TestCreateDatasetToolSafety:
    """Tests for the create_dataset tool-level safety checks.

    These test the validation logic in the tool layer (tools/create_dataset.py)
    by importing and calling the tool registration and then the inner function.
    """

    @pytest.fixture
    def tool_func(self):
        """Get the create_dataset tool function by registering it on a mock MCP."""
        from mcp.server.fastmcp import FastMCP

        mcp = FastMCP("test")
        from tools.create_dataset import register_create_dataset_tool

        register_create_dataset_tool(mcp)

        # The tool is registered; find it by name
        tool = mcp._tool_manager._tools.get("create_dataset")
        assert tool is not None, "create_dataset tool was not registered"
        return tool.fn

    @pytest.mark.asyncio
    async def test_missing_api_key_returns_error(self, tool_func, monkeypatch):
        monkeypatch.delenv("DATAGOUV_API_KEY", raising=False)
        result = await tool_func(title="Test", description="Test description")
        assert "Error" in result
        assert "No API key configured" in result

    @pytest.mark.asyncio
    async def test_invalid_frequency_returns_error(self, tool_func, monkeypatch):
        monkeypatch.setenv("DATAGOUV_API_KEY", "fake-key")
        result = await tool_func(
            title="Test",
            description="Test description",
            frequency="every-5-minutes",
        )
        assert "Error" in result
        assert "Invalid frequency" in result

    @pytest.mark.asyncio
    async def test_empty_title_returns_error(self, tool_func, monkeypatch):
        monkeypatch.setenv("DATAGOUV_API_KEY", "fake-key")
        result = await tool_func(title="", description="Some description")
        assert "Error" in result
        assert "title is required" in result

    @pytest.mark.asyncio
    async def test_empty_description_returns_error(self, tool_func, monkeypatch):
        monkeypatch.setenv("DATAGOUV_API_KEY", "fake-key")
        result = await tool_func(title="Valid Title", description="")
        assert "Error" in result
        assert "description is required" in result

    @pytest.mark.asyncio
    async def test_whitespace_only_title_returns_error(self, tool_func, monkeypatch):
        monkeypatch.setenv("DATAGOUV_API_KEY", "fake-key")
        result = await tool_func(title="   ", description="Some description")
        assert "Error" in result
        assert "title is required" in result

    @pytest.mark.asyncio
    async def test_successful_creation_returns_info(self, tool_func, monkeypatch):
        monkeypatch.setenv("DATAGOUV_API_KEY", "fake-key")
        monkeypatch.setenv("DATAGOUV_ENV", "demo")

        mock_result = {
            "id": "abc123",
            "title": "My New Dataset",
            "slug": "my-new-dataset",
            "private": True,
            "license": "fr-lo",
            "frequency": "monthly",
        }

        with patch.object(
            datagouv_api_client, "create_dataset", new_callable=AsyncMock
        ) as mock_create:
            mock_create.return_value = mock_result

            result = await tool_func(
                title="My New Dataset",
                description="A description",
                frequency="monthly",
            )

            assert "created successfully" in result
            assert "abc123" in result
            assert "my-new-dataset" in result
            assert "PRIVATE (draft)" in result
            assert "demo.data.gouv.fr" in result

    @pytest.mark.asyncio
    async def test_prod_env_label_in_response(self, tool_func, monkeypatch):
        monkeypatch.setenv("DATAGOUV_API_KEY", "fake-key")
        monkeypatch.setenv("DATAGOUV_ENV", "prod")

        mock_result = {
            "id": "abc123",
            "title": "Prod Dataset",
            "slug": "prod-dataset",
            "private": True,
            "license": "fr-lo",
            "frequency": "unknown",
        }

        with patch.object(
            datagouv_api_client, "create_dataset", new_callable=AsyncMock
        ) as mock_create:
            mock_create.return_value = mock_result

            result = await tool_func(
                title="Prod Dataset",
                description="A description",
            )

            assert "PRODUCTION" in result

    @pytest.mark.asyncio
    async def test_public_dataset_status_in_response(self, tool_func, monkeypatch):
        monkeypatch.setenv("DATAGOUV_API_KEY", "fake-key")
        monkeypatch.setenv("DATAGOUV_ENV", "demo")

        mock_result = {
            "id": "abc123",
            "title": "Public Dataset",
            "slug": "public-dataset",
            "private": False,
            "license": "fr-lo",
            "frequency": "unknown",
        }

        with patch.object(
            datagouv_api_client, "create_dataset", new_callable=AsyncMock
        ) as mock_create:
            mock_create.return_value = mock_result

            result = await tool_func(
                title="Public Dataset",
                description="A description",
                private=False,
            )

            assert "PUBLIC" in result

    @pytest.mark.asyncio
    async def test_auth_error_returns_helpful_message(self, tool_func, monkeypatch):
        monkeypatch.setenv("DATAGOUV_API_KEY", "bad-key")
        monkeypatch.setenv("DATAGOUV_ENV", "demo")

        mock_request = httpx.Request(
            "POST", "https://demo.data.gouv.fr/api/1/datasets/"
        )
        mock_response = httpx.Response(
            status_code=401,
            json={"message": "Invalid API key"},
            request=mock_request,
        )
        http_error = httpx.HTTPStatusError(
            "401 Unauthorized", request=mock_request, response=mock_response
        )

        with patch.object(
            datagouv_api_client, "create_dataset", new_callable=AsyncMock
        ) as mock_create:
            mock_create.side_effect = http_error

            result = await tool_func(
                title="Should Fail",
                description="A description",
            )

            assert "Authentication failed" in result
            assert "401" in result

    @pytest.mark.asyncio
    async def test_permission_error_returns_helpful_message(
        self, tool_func, monkeypatch
    ):
        monkeypatch.setenv("DATAGOUV_API_KEY", "valid-key")
        monkeypatch.setenv("DATAGOUV_ENV", "demo")

        mock_request = httpx.Request(
            "POST", "https://demo.data.gouv.fr/api/1/datasets/"
        )
        mock_response = httpx.Response(
            status_code=403,
            json={"message": "You do not have permission"},
            request=mock_request,
        )
        http_error = httpx.HTTPStatusError(
            "403 Forbidden", request=mock_request, response=mock_response
        )

        with patch.object(
            datagouv_api_client, "create_dataset", new_callable=AsyncMock
        ) as mock_create:
            mock_create.side_effect = http_error

            result = await tool_func(
                title="Should Fail",
                description="A description",
                organization="some-org-id",
            )

            assert "Permission denied" in result
            assert "403" in result
