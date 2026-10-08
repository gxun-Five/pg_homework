"""Observability module for PostgreSQL MCP Server.

This module provides comprehensive observability features including:
- Prometheus metrics collection
- Structured JSON logging
- Request tracing and context propagation

Example:
    >>> from pg_mcp.observability import metrics, configure_logging, request_context
    >>>
    >>> # Configure logging
    >>> configure_logging(level="INFO", log_format="json")
    >>>
    >>> # Start metrics server
    >>> metrics.start_metrics_server(9090)
    >>>
    >>> # Use request tracing
    >>> async with request_context() as request_id:
    ...     metrics.increment_query_request(status="success", database="mydb")
    ...     logger.info("Query completed", extra={"request_id": request_id})
"""

from pg_mcp.observability.logging import (
    JSONFormatter,
    SensitiveDataFilter,
    TextFormatter,
    configure_logging,
    get_logger,
)
from pg_mcp.observability.metrics import MetricsCollector, metrics
from pg_mcp.observability.tracing import (
    TraceContext,
    TracingLogger,
    clear_request_id,
    generate_request_id,
    get_request_id,
    get_tracing_logger,
    request_context,
    set_request_id,
    trace_async,
    trace_sync,
)

__all__ = [
    # Metrics
    "MetricsCollector",
    "metrics",
    # Logging
    "configure_logging",
    "get_logger",
    "JSONFormatter",
    "TextFormatter",
    "SensitiveDataFilter",
    # Tracing
    "request_context",
    "generate_request_id",
    "get_request_id",
    "set_request_id",
    "clear_request_id",
    "trace_async",
    "trace_sync",
    "TraceContext",
    "TracingLogger",
    "get_tracing_logger",
]
