import os

import sentry_sdk


def init_sentry() -> None:
    dsn: str | None = os.getenv("SENTRY_DSN")
    if not dsn:
        return

    sample_rate = float(os.getenv("SENTRY_SAMPLE_RATE", "1.0"))

    sentry_sdk.init(
        dsn=dsn,
        environment=os.getenv("MCP_ENV", "local"),
        traces_sample_rate=sample_rate,
        profiles_sample_rate=sample_rate,
        send_default_pii=False,
    )
