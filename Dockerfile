FROM astral/uv:python3.13-trixie-slim

# Install needed apt packages
RUN apt-get update -y && \
    apt-get install -y --no-install-recommends git && \
    rm -rf /var/lib/apt/lists/*

# Install dependencies
WORKDIR /app
ADD . /app/
RUN uv sync --frozen

# Expose port (default 8000, configurable via MCP_PORT env var)
EXPOSE 8000

# Run
ENTRYPOINT ["uv", "run"]
CMD ["python", "main.py"]
