"""Data models module."""

from pg_mcp.models.errors import (
    DatabaseConnectionError,
    DatabaseError,
    ErrorCode,
    ErrorDetail,
    ExecutionTimeoutError,
    LLMError,
    LLMTimeoutError,
    LLMUnavailableError,
    PgMcpError,
    RateLimitExceededError,
    SchemaLoadError,
    SecurityViolationError,
    SQLParseError,
    ValidationError,
)
from pg_mcp.models.query import (
    QueryRequest,
    QueryResponse,
    QueryResult,
    ReturnType,
    ValidationResult,
)
from pg_mcp.models.schema import (
    ColumnInfo,
    DatabaseSchema,
    EnumTypeInfo,
    ForeignKeyInfo,
    IndexInfo,
    TableInfo,
)

__all__ = [
    # Schema models
    "ColumnInfo",
    "ForeignKeyInfo",
    "IndexInfo",
    "TableInfo",
    "EnumTypeInfo",
    "DatabaseSchema",
    # Query models
    "ReturnType",
    "QueryRequest",
    "ValidationResult",
    "QueryResult",
    "QueryResponse",
    # Error models
    "ErrorCode",
    "ErrorDetail",
    "PgMcpError",
    "ValidationError",
    "SecurityViolationError",
    "SQLParseError",
    "DatabaseError",
    "DatabaseConnectionError",
    "LLMError",
    "LLMTimeoutError",
    "LLMUnavailableError",
    "SchemaLoadError",
    "ExecutionTimeoutError",
    "RateLimitExceededError",
]
