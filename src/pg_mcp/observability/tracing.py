"""Request tracing and context propagation for PostgreSQL MCP Server.

This module provides request ID generation and context propagation throughout
the query processing pipeline, enabling end-to-end tracing of requests.
"""

import contextvars
import logging
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from functools import wraps
from typing import Any, ParamSpec, TypeVar

from pydantic import BaseModel

# Context variable for current request ID
_request_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "request_id", default=None
)

# Type variables for decorators
P = ParamSpec("P")
R = TypeVar("R")


class TraceContext(BaseModel):
    """Trace context containing request tracking information.

    Attributes:
        request_id: Unique identifier for the request.
        parent_id: Optional parent request ID for nested operations.
        operation: Name of the operation being traced.
        metadata: Additional metadata about the request.
    """

    request_id: str
    parent_id: str | None = None
    operation: str | None = None
    metadata: dict[str, Any] | None = None


def generate_request_id() -> str:
    """Generate a unique request ID.

    Returns:
        UUID4-based request ID as a string.

    Example:
        >>> req_id = generate_request_id()
        >>> print(req_id)
        'a1b2c3d4-e5f6-7890-abcd-ef1234567890'
    """
    return str(uuid.uuid4())


def get_request_id() -> str | None:
    """Get the current request ID from context.

    Returns:
        Current request ID or None if not set.

    Example:
        >>> with request_context():
        ...     print(get_request_id())
        'a1b2c3d4-e5f6-7890-abcd-ef1234567890'
    """
    return _request_id_var.get()


def set_request_id(request_id: str) -> None:
    """Set the current request ID in context.

    Args:
        request_id: Request ID to set.

    Example:
        >>> set_request_id("custom-request-id")
        >>> assert get_request_id() == "custom-request-id"
    """
    _request_id_var.set(request_id)


def clear_request_id() -> None:
    """Clear the current request ID from context.

    Example:
        >>> clear_request_id()
        >>> assert get_request_id() is None
    """
    _request_id_var.set(None)


@asynccontextmanager
async def request_context(request_id: str | None = None) -> AsyncIterator[str]:
    """Context manager for request tracing.

    Creates a new request context with a unique (or provided) request ID
    that will be propagated through all async operations.

    Args:
        request_id: Optional request ID. If not provided, a new one is generated.

    Yields:
        The request ID for this context.

    Example:
        >>> async with request_context() as req_id:
        ...     logger.info("Processing request", extra={"request_id": req_id})
        ...     await some_operation()
    """
    if request_id is None:
        request_id = generate_request_id()

    token = _request_id_var.set(request_id)
    try:
        yield request_id
    finally:
        _request_id_var.reset(token)


def trace_async(
    operation: str | None = None,
) -> Callable[[Callable[P, Awaitable[R]]], Callable[P, Awaitable[R]]]:
    """Decorator to trace async functions with request ID.

    Automatically injects request_id into log records and ensures
    context propagation through async calls.

    Args:
        operation: Optional operation name. If not provided, uses function name.

    Returns:
        Decorated function that maintains request context.

    Example:
        >>> @trace_async(operation="generate_sql")
        ... async def generate_sql(question: str) -> str:
        ...     logger.info("Generating SQL", extra={"question": question})
        ...     return "SELECT 1"
    """

    def decorator(func: Callable[P, Awaitable[R]]) -> Callable[P, Awaitable[R]]:
        op_name = operation or func.__name__

        @wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            request_id = get_request_id()

            if request_id:
                # Create a log adapter that adds request_id to all log records
                old_factory = logging.getLogRecordFactory()

                def record_factory(*factory_args: Any, **factory_kwargs: Any) -> logging.LogRecord:
                    record = old_factory(*factory_args, **factory_kwargs)
                    record.request_id = request_id
                    record.operation = op_name
                    return record

                logging.setLogRecordFactory(record_factory)

                try:
                    result = await func(*args, **kwargs)
                    return result
                finally:
                    logging.setLogRecordFactory(old_factory)
            else:
                # No request context, just execute
                return await func(*args, **kwargs)

        return wrapper

    return decorator


def trace_sync(
    operation: str | None = None,
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Decorator to trace synchronous functions with request ID.

    Similar to trace_async but for synchronous functions.

    Args:
        operation: Optional operation name. If not provided, uses function name.

    Returns:
        Decorated function that maintains request context.

    Example:
        >>> @trace_sync(operation="validate_sql")
        ... def validate_sql(sql: str) -> bool:
        ...     logger.info("Validating SQL", extra={"sql": sql})
        ...     return True
    """

    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        op_name = operation or func.__name__

        @wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            request_id = get_request_id()

            if request_id:
                old_factory = logging.getLogRecordFactory()

                def record_factory(*factory_args: Any, **factory_kwargs: Any) -> logging.LogRecord:
                    record = old_factory(*factory_args, **factory_kwargs)
                    record.request_id = request_id
                    record.operation = op_name
                    return record

                logging.setLogRecordFactory(record_factory)

                try:
                    result = func(*args, **kwargs)
                    return result
                finally:
                    logging.setLogRecordFactory(old_factory)
            else:
                return func(*args, **kwargs)

        return wrapper

    return decorator


class TracingLogger:
    """Logger wrapper that automatically includes request context.

    This class wraps the standard logger to automatically include
    request_id and operation name in all log messages.

    Example:
        >>> logger = TracingLogger(__name__)
        >>> async with request_context():
        ...     logger.info("Processing query", database="mydb")
    """

    def __init__(self, name: str):
        """Initialize tracing logger.

        Args:
            name: Logger name (typically module name).
        """
        self._logger = logging.getLogger(name)

    def _log(self, level: int, msg: str, *args: Any, **kwargs: Any) -> None:
        """Internal log method that adds request context.

        Args:
            level: Log level.
            msg: Log message.
            *args: Positional arguments for message formatting.
            **kwargs: Keyword arguments including 'extra' for additional fields.
        """
        extra = kwargs.pop("extra", {})
        request_id = get_request_id()

        # Only add request_id if not already present
        if request_id and "request_id" not in extra:
            extra["request_id"] = request_id

        kwargs["extra"] = extra
        self._logger.log(level, msg, *args, **kwargs)

    def debug(self, msg: str, *args: Any, **kwargs: Any) -> None:
        """Log a debug message."""
        self._log(logging.DEBUG, msg, *args, **kwargs)

    def info(self, msg: str, *args: Any, **kwargs: Any) -> None:
        """Log an info message."""
        self._log(logging.INFO, msg, *args, **kwargs)

    def warning(self, msg: str, *args: Any, **kwargs: Any) -> None:
        """Log a warning message."""
        self._log(logging.WARNING, msg, *args, **kwargs)

    def error(self, msg: str, *args: Any, **kwargs: Any) -> None:
        """Log an error message."""
        self._log(logging.ERROR, msg, *args, **kwargs)

    def critical(self, msg: str, *args: Any, **kwargs: Any) -> None:
        """Log a critical message."""
        self._log(logging.CRITICAL, msg, *args, **kwargs)

    def exception(self, msg: str, *args: Any, **kwargs: Any) -> None:
        """Log an exception message with traceback."""
        kwargs["exc_info"] = True
        self._log(logging.ERROR, msg, *args, **kwargs)


def get_tracing_logger(name: str) -> TracingLogger:
    """Get a tracing logger instance.

    Args:
        name: Logger name (typically __name__).

    Returns:
        TracingLogger instance.

    Example:
        >>> logger = get_tracing_logger(__name__)
        >>> logger.info("Operation started")
    """
    return TracingLogger(name)
