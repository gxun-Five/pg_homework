# ============================================================================
# PostgreSQL MCP Server - Production Dockerfile
# ============================================================================
# Multi-stage build for optimal image size and security
# ============================================================================

# ============================================================================
# Stage 1: Builder
# ============================================================================
# Use official Python 3.14 image as base
FROM python:3.14-slim as builder

# Set working directory
WORKDIR /build

# Install system dependencies required for building Python packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    make \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install UV package manager for faster dependency resolution
RUN pip install --no-cache-dir uv

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Install dependencies using UV
# --no-dev: Skip development dependencies
# --frozen: Use exact versions from lock file
RUN uv pip install --system --no-dev --frozen

# Copy source code
COPY src/ ./src/
COPY main.py ./

# Install the package
RUN uv pip install --system --no-deps .

# ============================================================================
# Stage 2: Runtime
# ============================================================================
FROM python:3.14-slim

# Metadata labels
LABEL maintainer="your-email@example.com"
LABEL version="0.1.0"
LABEL description="PostgreSQL MCP Server - Natural Language to SQL"

# Set environment variables
# Python: Don't write bytecode, unbuffered output
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    # Default to production environment
    ENVIRONMENT=production \
    # Disable pip version check
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user for security
RUN groupadd -r pgmcp && useradd -r -g pgmcp pgmcp

# Set working directory
WORKDIR /app

# Copy Python packages from builder
COPY --from=builder /usr/local/lib/python3.14/site-packages /usr/local/lib/python3.14/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code
COPY --from=builder /build/src ./src
COPY --from=builder /build/main.py ./

# Create directory for logs (if needed)
RUN mkdir -p /app/logs && chown -R pgmcp:pgmcp /app

# Switch to non-root user
USER pgmcp

# Expose Prometheus metrics port
EXPOSE 9090

# Health check
# Check if the process is running
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import psutil; exit(0 if any('python' in p.name() for p in psutil.process_iter()) else 1)" || exit 1

# Default command
# Run the MCP server
CMD ["python", "main.py"]
