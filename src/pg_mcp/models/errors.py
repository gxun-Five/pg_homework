"""Custom exceptions and error codes for PostgreSQL MCP Server.

This module defines a hierarchy of exceptions for different error scenarios
and error codes for structured error reporting.
"""

from enum import StrEnum
from typing import Any


class ErrorCode(StrEnum):
    """Standardized error codes for the application."""

    # Success
    SUCCESS = "success"

    # Client errors (4xx)
    INVALID_REQUEST = "invalid_request"
    VALIDATION_FAILED = "validation_failed"
    SECURITY_VIOLATION = "security_violation"
    SQL_PARSE_ERROR = "sql_parse_error"
    QUESTION_TOO_LONG = "question_too_long"

    # Server errors (5xx)
    INTERNAL_ERROR = "internal_error"
    DATABASE_ERROR = "database_error"
    DATABASE_CONNECTION_ERROR = "database_connection_error"
    LLM_ERROR = "llm_error"
    LLM_TIMEOUT = "llm_timeout"
    LLM_UNAVAILABLE = "llm_unavailable"
    SCHEMA_LOAD_ERROR = "schema_load_error"
    EXECUTION_TIMEOUT = "execution_timeout"

    # Resource errors
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    RESOURCE_EXHAUSTED = "resource_exhausted"


class ErrorDetail:
    """Structured error detail information."""

    def __init__(
        self,
        code: ErrorCode,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Initialize error detail.

        Args:
            code: Error code identifier.
            message: Human-readable error message.
            details: Optional additional context.
        """
        self.code = code
        self.message = message
        self.details = details or {}

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation.

        Returns:
            dict: Dictionary containing error information.
        """
        result: dict[str, Any] = {
            "code": self.code,
            "message": self.message,
        }
        if self.details:
            result["details"] = self.details
        return result

    def __repr__(self) -> str:
        """String representation of error detail.

        Returns:
            str: String representation.
        """
        return f"ErrorDetail(code={self.code}, message={self.message!r})"


class PgMcpError(Exception):
    """Base exception for all PostgreSQL MCP Server errors.

    All custom exceptions in this application should inherit from this class.
    """

    def __init__(
        self,
        message: str,
        code: ErrorCode = ErrorCode.INTERNAL_ERROR,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Initialize base error.

        Args:
            message: Human-readable error message.
            code: Error code identifier.
            details: Optional additional context.
        """
        super().__init__(message)
        self.message = message
        self.code = code
        self.details = details or {}

    def to_error_detail(self) -> ErrorDetail:
        """Convert exception to ErrorDetail.

        Returns:
            ErrorDetail: Structured error detail.
        """
        return ErrorDetail(code=self.code, message=self.message, details=self.details)

    def __repr__(self) -> str:
        """String representation of error.

        Returns:
            str: String representation.
        """
        return f"{self.__class__.__name__}(code={self.code}, message={self.message!r})"


class ValidationError(PgMcpError):
    """Exception raised for validation failures."""

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        """Initialize validation error.

        Args:
            message: Error message describing validation failure.
            details: Optional validation failure details.
        """
        super().__init__(message=message, code=ErrorCode.VALIDATION_FAILED, details=details)


class SecurityViolationError(PgMcpError):
    """Exception raised when security constraints are violated.

    This includes:
    - Attempts to execute write operations when not allowed
    - Use of blocked functions
    - SQL injection attempts
    - Access to restricted tables or schemas
    """

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        """Initialize security violation error.

        Args:
            message: Error message describing security violation.
            details: Optional violation details.
        """
        super().__init__(message=message, code=ErrorCode.SECURITY_VIOLATION, details=details)


class SQLParseError(PgMcpError):
    """Exception raised when SQL parsing or validation fails."""

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        """Initialize SQL parse error.

        Args:
            message: Error message describing parse failure.
            details: Optional parse error details (e.g., position, syntax).
        """
        super().__init__(message=message, code=ErrorCode.SQL_PARSE_ERROR, details=details)


class DatabaseError(PgMcpError):
    """Exception raised for database operation failures."""

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        """Initialize database error.

        Args:
            message: Error message describing database failure.
            details: Optional database error details.
        """
        super().__init__(message=message, code=ErrorCode.DATABASE_ERROR, details=details)


class DatabaseConnectionError(PgMcpError):
    """Exception raised when database connection fails."""

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        """Initialize database connection error.

        Args:
            message: Error message describing connection failure.
            details: Optional connection error details.
        """
        super().__init__(message=message, code=ErrorCode.DATABASE_CONNECTION_ERROR, details=details)


class LLMError(PgMcpError):
    """Base exception for LLM-related errors."""

    def __init__(
        self,
        message: str,
        code: ErrorCode = ErrorCode.LLM_ERROR,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Initialize LLM error.

        Args:
            message: Error message describing LLM failure.
            code: Specific LLM error code.
            details: Optional LLM error details.
        """
        super().__init__(message=message, code=code, details=details)


class LLMTimeoutError(LLMError):
    """Exception raised when LLM request times out."""

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        """Initialize LLM timeout error.

        Args:
            message: Error message describing timeout.
            details: Optional timeout details (e.g., duration).
        """
        super().__init__(message=message, code=ErrorCode.LLM_TIMEOUT, details=details)


class LLMUnavailableError(LLMError):
    """Exception raised when LLM service is unavailable.

    This includes:
    - API key invalid or missing
    - Service rate limited
    - Service temporarily down
    """

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        """Initialize LLM unavailable error.

        Args:
            message: Error message describing unavailability.
            details: Optional unavailability details.
        """
        super().__init__(message=message, code=ErrorCode.LLM_UNAVAILABLE, details=details)


class SchemaLoadError(PgMcpError):
    """Exception raised when schema loading fails."""

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        """Initialize schema load error.

        Args:
            message: Error message describing schema load failure.
            details: Optional schema error details.
        """
        super().__init__(message=message, code=ErrorCode.SCHEMA_LOAD_ERROR, details=details)


class ExecutionTimeoutError(PgMcpError):
    """Exception raised when query execution exceeds timeout."""

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        """Initialize execution timeout error.

        Args:
            message: Error message describing timeout.
            details: Optional timeout details.
        """
        super().__init__(message=message, code=ErrorCode.EXECUTION_TIMEOUT, details=details)


class RateLimitExceededError(PgMcpError):
    """Exception raised when rate limit is exceeded."""

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        """Initialize rate limit error.

        Args:
            message: Error message describing rate limit.
            details: Optional rate limit details (e.g., retry_after).
        """
        super().__init__(message=message, code=ErrorCode.RATE_LIMIT_EXCEEDED, details=details)
