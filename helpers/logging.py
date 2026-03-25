import functools
import inspect
import logging
import os
from typing import Any, cast

# Python unified logging config
MAIN_LOGGER_NAME = "mcp.main"

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    force=True,
)

# Uvicorn logging config
UVICORN_LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default": {"format": "%(asctime)s | %(levelname)s | %(name)s | %(message)s"}
    },
    "handlers": {
        "default": {
            "class": "logging.StreamHandler",
            "formatter": "default",
        }
    },
    "root": {
        "level": "INFO",
        "handlers": ["default"],
    },
}

# Decorator for tools logging
TOOLS_LOGGER_NAME = "mcp.tools"
logger = logging.getLogger(TOOLS_LOGGER_NAME)


def log_tool(func):
    @functools.wraps(func)
    async def async_wrapper(*args, **kwargs):
        logger.info("Tool called: %s | kwargs=%s", func.__name__, kwargs)
        return await func(*args, **kwargs)

    cast(Any, async_wrapper).__signature__ = inspect.signature(func)
    return async_wrapper
