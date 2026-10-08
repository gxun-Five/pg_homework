"""PostgreSQL MCP Server - Natural Language to SQL.

A Model Context Protocol server that enables natural language querying
of PostgreSQL databases with built-in security, validation, and observability.
"""

__version__ = "0.1.0"

from pg_mcp.config.settings import Settings, get_settings
from pg_mcp.models.errors import (
    DatabaseError,
    ErrorCode,
    LLMError,
    PgMcpError,
    SecurityViolationError,
    SQLParseError,
)
from pg_mcp.models.query import QueryRequest, QueryResponse, QueryResult, ReturnType
from pg_mcp.models.schema import DatabaseSchema, TableInfo

__all__ = [
    "__version__",
    # Config
    "Settings",
    "get_settings",
    # Models
    "QueryRequest",
    "QueryResponse",
    "QueryResult",
    "ReturnType",
    "DatabaseSchema",
    "TableInfo",
    # Errors
    "PgMcpError",
    "SecurityViolationError",
    "SQLParseError",
    "DatabaseError",
    "LLMError",
    "ErrorCode",
]
