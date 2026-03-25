# MCP SSH Gateway - Production Docker Image
FROM python:3.11-slim-bookworm

# Labels
LABEL maintainer="MCP Gateway Team"
LABEL version="1.0.0"
LABEL description="Remote MCP Server for ChatGPT with SSH Gateway"

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    openssh-client \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user for security
RUN groupadd -r mcp && useradd -r -g mcp mcp

# Create directories
WORKDIR /app
RUN mkdir -p /app/secrets /var/log/mcp-server && \
    chown -R mcp:mcp /app /var/log/mcp-server

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ ./src/
COPY pyproject.toml .

# Install the package
RUN pip install -e .

# Switch to non-root user
USER mcp

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run the application
CMD ["python", "-m", "mcp_server.main"]
