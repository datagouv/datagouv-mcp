FROM astral/uv:python3.14-trixie-slim

# Install needed apt packages
RUN apt-get update -y && \
    apt-get install -y --no-install-recommends git && \
    rm -rf /var/lib/apt/lists/*

# Install dependencies
WORKDIR /app
ADD . /app/
# Skip dev dependencies. Set as ENV rather than a `--no-dev` flag: the `uv run`
# of the CMD syncs the environment again at startup.
ENV UV_NO_DEV=1
RUN uv sync --frozen

# Expose port (default 8000, configurable via MCP_PORT env var)
EXPOSE 8000

# Run
ENTRYPOINT ["uv", "run"]
CMD ["python", "main.py"]
