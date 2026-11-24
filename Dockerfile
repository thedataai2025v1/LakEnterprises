# ==============================================================================
# Multi-stage Dockerfile for LakEnterprises Backend & CLI Engine
# Python 3.12 Slim with security hardening
# ==============================================================================

FROM python:3.12-slim AS base

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install uv for fast, deterministic dependency management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Copy project metadata & dependency manifests
COPY pyproject.toml uv.lock ./

# Install dependencies (cached layer)
RUN uv sync --frozen --no-dev

# Copy source code and documentation
COPY src/ ./src/
COPY data/ ./data/
COPY docs/ ./docs/

# Create non-root user for security
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8001

HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8001/health/live || exit 1

ENTRYPOINT ["uv", "run", "uvicorn", "lakenterprises.app:app", "--host", "0.0.0.0", "--port", "8001"]
