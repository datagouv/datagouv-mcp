from mcp.types import ToolAnnotations

# All tools query public data.gouv.fr and related services; retries do not mutate remote state.
READ_ONLY_EXTERNAL_API_TOOL = ToolAnnotations(
    readOnlyHint=True,
    destructiveHint=False,
    idempotentHint=True,
    openWorldHint=True,
)
