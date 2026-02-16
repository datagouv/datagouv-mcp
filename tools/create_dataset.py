import logging
import os

import httpx
from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from helpers import datagouv_api_client, env_config

logger = logging.getLogger("datagouv_mcp")

VALID_FREQUENCIES = {
    "unknown",
    "punctual",
    "continuous",
    "hourly",
    "fourTimesADay",
    "threeTimesADay",
    "semidaily",
    "daily",
    "fourTimesAWeek",
    "threeTimesAWeek",
    "semiweekly",
    "weekly",
    "biweekly",
    "threeTimesAMonth",
    "semimonthly",
    "monthly",
    "bimonthly",
    "quarterly",
    "threeTimesAYear",
    "semiannual",
    "annual",
    "biennial",
    "triennial",
    "quinquennial",
    "irregular",
}


def register_create_dataset_tool(mcp: FastMCP) -> None:
    @mcp.tool(
        annotations=ToolAnnotations(
            readOnlyHint=False,
            destructiveHint=True,
            idempotentHint=False,
            openWorldHint=True,
        )
    )
    async def create_dataset(
        title: str,
        description: str,
        frequency: str = "unknown",
        organization: str | None = None,
        license: str = "fr-lo",
        tags: list[str] | None = None,
        private: bool = True,
    ) -> str:
        """
        Create a new dataset on data.gouv.fr.

        This is a WRITE operation that creates a real dataset on data.gouv.fr.
        By default, datasets are created as private DRAFTS (not visible publicly).
        Set private=False only when you are ready to publish.

        Requires a DATAGOUV_API_KEY environment variable to be set.

        Args:
            title: Dataset title (required).
            description: Dataset description, supports markdown (required).
            frequency: Update frequency (default: "unknown"). Valid values:
                unknown, punctual, continuous, hourly, daily, weekly, monthly,
                quarterly, semiannual, annual, irregular, and more.
            organization: Organization ID to publish under (optional).
                If omitted, published under the user's personal account.
            license: License identifier (default: "fr-lo" = Licence Ouverte).
            tags: List of tags (optional).
            private: If True (default), create as draft (not publicly visible).
        """
        # Check API key
        api_key = env_config.get_api_key()
        if not api_key:
            return (
                "Error: No API key configured.\n"
                "Set the DATAGOUV_API_KEY environment variable to publish datasets.\n"
                "You can get your API key from your data.gouv.fr profile settings:\n"
                "https://www.data.gouv.fr/fr/admin/me"
            )

        # Validate frequency
        if frequency not in VALID_FREQUENCIES:
            return (
                f"Error: Invalid frequency '{frequency}'.\n"
                f"Valid values are: {', '.join(sorted(VALID_FREQUENCIES))}"
            )

        # Validate required fields
        if not title or not title.strip():
            return "Error: title is required and cannot be empty."
        if not description or not description.strip():
            return "Error: description is required and cannot be empty."

        # Determine environment for user context
        current_env: str = os.getenv("DATAGOUV_ENV", "prod").strip().lower()
        env_label = (
            "demo.data.gouv.fr"
            if current_env == "demo"
            else "www.data.gouv.fr (PRODUCTION)"
        )

        try:
            result = await datagouv_api_client.create_dataset(
                title=title.strip(),
                description=description.strip(),
                api_key=api_key,
                frequency=frequency,
                organization=organization,
                license_id=license,
                tags=tags,
                private=private,
            )

            dataset_id = result.get("id", "unknown")
            slug = result.get("slug", dataset_id)
            site_url = f"{env_config.get_base_url('site')}datasets/{slug}/"
            status = "PRIVATE (draft)" if result.get("private", True) else "PUBLIC"

            content_parts = [
                f"Dataset created successfully on {env_label}:",
                "",
                f"  Title: {result.get('title', title)}",
                f"  ID: {dataset_id}",
                f"  Slug: {slug}",
                f"  URL: {site_url}",
                f"  Status: {status}",
                f"  License: {result.get('license', license)}",
                f"  Frequency: {result.get('frequency', frequency)}",
            ]

            if result.get("organization"):
                org = result["organization"]
                if isinstance(org, dict):
                    content_parts.append(f"  Organization: {org.get('name', '')}")

            content_parts.append("")
            content_parts.append("Next steps:")
            content_parts.append(
                "  - Add resources (files) to this dataset using add_resource"
            )
            if result.get("private", True):
                content_parts.append(
                    "  - When ready, set private=False to make it publicly visible"
                )

            logger.info(
                "Dataset created: id=%s title='%s' env=%s private=%s",
                dataset_id,
                title,
                current_env,
                private,
            )

            return "\n".join(content_parts)

        except httpx.HTTPStatusError as e:
            status_code = e.response.status_code
            try:
                error_body = e.response.json()
                error_msg = error_body.get("message", str(e))
            except Exception:  # noqa: BLE001
                error_msg = str(e)

            if status_code == 401:
                return (
                    "Error: Authentication failed (HTTP 401).\n"
                    "Your API key may be invalid or expired.\n"
                    "Check your DATAGOUV_API_KEY environment variable."
                )
            if status_code == 403:
                return (
                    f"Error: Permission denied (HTTP 403).\n"
                    f"You may not have permission to publish "
                    f"{'for this organization' if organization else 'with this account'}.\n"
                    f"Details: {error_msg}"
                )
            return f"Error: HTTP {status_code} - {error_msg}"
        except Exception as e:  # noqa: BLE001
            logger.exception("Unexpected error in create_dataset tool")
            return f"Error creating dataset: {str(e)}"
