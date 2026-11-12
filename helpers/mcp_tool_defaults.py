from mcp.types import ToolAnnotations

# All tools query public data.gouv.fr and related services; retries do not mutate remote state.
READ_ONLY_EXTERNAL_API_TOOL = ToolAnnotations(
    read_only_hint=True,
    destructive_hint=False,
    idempotent_hint=True,
    open_world_hint=True,
)
