"""Caching layer for database schemas.

This package provides caching functionality to improve performance by
reducing repeated schema introspection queries.
"""

from pg_mcp.cache.schema_cache import SchemaCache

__all__ = [
    "SchemaCache",
]
