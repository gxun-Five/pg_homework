"""Unit tests for schema cache management.

This module tests the SchemaCache class functionality including caching,
expiration, and auto-refresh capabilities.
"""

import asyncio
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from pg_mcp.cache.schema_cache import SchemaCache
from pg_mcp.config.settings import CacheConfig
from pg_mcp.models.schema import DatabaseSchema, TableInfo


class TestSchemaCache:
    """Test suite for SchemaCache class."""

    @pytest.fixture
    def cache_config(self) -> CacheConfig:
        """Create cache configuration for testing."""
        return CacheConfig(
            schema_ttl=3600,  # 1 hour
            max_size=100,
            enabled=True,
        )

    @pytest.fixture
    def disabled_cache_config(self) -> CacheConfig:
        """Create disabled cache configuration."""
        return CacheConfig(
            schema_ttl=3600,
            max_size=100,
            enabled=False,
        )

    @pytest.fixture
    def cache(self, cache_config: CacheConfig) -> SchemaCache:
        """Create schema cache instance."""
        return SchemaCache(cache_config)

    @pytest.fixture
    def mock_pool(self) -> Mock:
        """Create mock connection pool."""
        pool = MagicMock()
        return pool

    @pytest.fixture
    def sample_schema(self) -> DatabaseSchema:
        """Create sample database schema for testing."""
        return DatabaseSchema(
            database_name="test_db",
            tables=[
                TableInfo(
                    schema_name="public",
                    table_name="users",
                    columns=[],
                )
            ],
            enum_types=[],
            version="PostgreSQL 16.0",
        )

    def test_get_returns_none_when_empty(self, cache: SchemaCache):
        """Test that get returns None when cache is empty."""
        result = cache.get("nonexistent_db")
        assert result is None

    def test_get_returns_none_when_disabled(
        self, disabled_cache_config: CacheConfig, sample_schema: DatabaseSchema
    ):
        """Test that get returns None when caching is disabled."""
        cache = SchemaCache(disabled_cache_config)
        cache._cache["test_db"] = sample_schema
        cache._cache_timestamps["test_db"] = datetime.now(UTC)

        result = cache.get("test_db")
        assert result is None

    @pytest.mark.asyncio
    async def test_load_stores_in_cache(
        self,
        cache: SchemaCache,
        mock_pool: Mock,
        sample_schema: DatabaseSchema,
    ):
        """Test that load stores schema in cache."""
        with patch("pg_mcp.cache.schema_cache.SchemaIntrospector") as mock_introspector_class:
            mock_introspector = AsyncMock()
            mock_introspector.introspect.return_value = sample_schema
            mock_introspector_class.return_value = mock_introspector

            result = await cache.load("test_db", mock_pool)

            assert result == sample_schema
            assert cache.get("test_db") == sample_schema

    @pytest.mark.asyncio
    async def test_load_does_not_cache_when_disabled(
        self,
        disabled_cache_config: CacheConfig,
        mock_pool: Mock,
        sample_schema: DatabaseSchema,
    ):
        """Test that load doesn't cache when caching is disabled."""
        cache = SchemaCache(disabled_cache_config)

        with patch("pg_mcp.cache.schema_cache.SchemaIntrospector") as mock_introspector_class:
            mock_introspector = AsyncMock()
            mock_introspector.introspect.return_value = sample_schema
            mock_introspector_class.return_value = mock_introspector

            result = await cache.load("test_db", mock_pool)

            assert result == sample_schema
            assert cache.get("test_db") is None

    def test_get_cache_age_returns_none_when_not_cached(self, cache: SchemaCache):
        """Test that get_cache_age returns None for non-cached database."""
        age = cache.get_cache_age("nonexistent_db")
        assert age is None

    def test_get_cache_age_returns_correct_age(
        self, cache: SchemaCache, sample_schema: DatabaseSchema
    ):
        """Test that get_cache_age calculates correct age."""
        # Set cache with timestamp 100 seconds ago
        past_time = datetime.now(UTC) - timedelta(seconds=100)
        cache._cache["test_db"] = sample_schema
        cache._cache_timestamps["test_db"] = past_time

        age = cache.get_cache_age("test_db")

        assert age is not None
        assert 95 <= age <= 105  # Allow small time variance

    def test_get_returns_none_when_expired(self, cache: SchemaCache, sample_schema: DatabaseSchema):
        """Test that get returns None when cache is expired."""
        # Set cache with expired timestamp (2 hours ago, TTL is 1 hour)
        expired_time = datetime.now(UTC) - timedelta(hours=2)
        cache._cache["test_db"] = sample_schema
        cache._cache_timestamps["test_db"] = expired_time

        result = cache.get("test_db")

        assert result is None
        # Verify cache was cleaned up
        assert "test_db" not in cache._cache
        assert "test_db" not in cache._cache_timestamps

    def test_get_returns_schema_when_valid(self, cache: SchemaCache, sample_schema: DatabaseSchema):
        """Test that get returns schema when cache is valid."""
        # Set cache with recent timestamp
        cache._cache["test_db"] = sample_schema
        cache._cache_timestamps["test_db"] = datetime.now(UTC)

        result = cache.get("test_db")

        assert result == sample_schema

    @pytest.mark.asyncio
    async def test_refresh_updates_cache(
        self,
        cache: SchemaCache,
        mock_pool: Mock,
        sample_schema: DatabaseSchema,
    ):
        """Test that refresh updates existing cache."""
        # Set initial cache
        old_time = datetime.now(UTC) - timedelta(minutes=30)
        cache._cache["test_db"] = sample_schema
        cache._cache_timestamps["test_db"] = old_time

        with patch("pg_mcp.cache.schema_cache.SchemaIntrospector") as mock_introspector_class:
            mock_introspector = AsyncMock()
            mock_introspector.introspect.return_value = sample_schema
            mock_introspector_class.return_value = mock_introspector

            await cache.refresh("test_db", mock_pool)

            # Verify timestamp was updated
            new_age = cache.get_cache_age("test_db")
            assert new_age is not None
            assert new_age < 60  # Should be very recent

    def test_clear_removes_specific_database(
        self, cache: SchemaCache, sample_schema: DatabaseSchema
    ):
        """Test that clear removes specific database from cache."""
        cache._cache["test_db"] = sample_schema
        cache._cache_timestamps["test_db"] = datetime.now(UTC)
        cache._cache["other_db"] = sample_schema
        cache._cache_timestamps["other_db"] = datetime.now(UTC)

        cache.clear("test_db")

        assert "test_db" not in cache._cache
        assert "test_db" not in cache._cache_timestamps
        assert "other_db" in cache._cache
        assert "other_db" in cache._cache_timestamps

    def test_clear_removes_all_databases(self, cache: SchemaCache, sample_schema: DatabaseSchema):
        """Test that clear with no argument removes all databases."""
        cache._cache["test_db"] = sample_schema
        cache._cache_timestamps["test_db"] = datetime.now(UTC)
        cache._cache["other_db"] = sample_schema
        cache._cache_timestamps["other_db"] = datetime.now(UTC)

        cache.clear()

        assert len(cache._cache) == 0
        assert len(cache._cache_timestamps) == 0

    def test_get_cached_databases_returns_all_databases(
        self, cache: SchemaCache, sample_schema: DatabaseSchema
    ):
        """Test that get_cached_databases returns all cached database names."""
        cache._cache["db1"] = sample_schema
        cache._cache_timestamps["db1"] = datetime.now(UTC)
        cache._cache["db2"] = sample_schema
        cache._cache_timestamps["db2"] = datetime.now(UTC)

        databases = cache.get_cached_databases()

        assert set(databases) == {"db1", "db2"}

    def test_get_cached_databases_returns_empty_list(self, cache: SchemaCache):
        """Test that get_cached_databases returns empty list when cache is empty."""
        databases = cache.get_cached_databases()
        assert databases == []

    @pytest.mark.asyncio
    async def test_start_auto_refresh_when_disabled(
        self, disabled_cache_config: CacheConfig, mock_pool: Mock
    ):
        """Test that auto-refresh does nothing when caching is disabled."""
        cache = SchemaCache(disabled_cache_config)
        pools = {"test_db": mock_pool}

        await cache.start_auto_refresh(1, pools)

        assert cache._refresh_task is None

    @pytest.mark.asyncio
    async def test_start_auto_refresh_starts_task(self, cache: SchemaCache, mock_pool: Mock):
        """Test that auto-refresh starts background task."""
        pools = {"test_db": mock_pool}

        await cache.start_auto_refresh(1, pools)

        assert cache._refresh_task is not None
        assert not cache._refresh_task.done()

        await cache.stop_auto_refresh()

    @pytest.mark.asyncio
    async def test_start_auto_refresh_does_not_start_duplicate(
        self, cache: SchemaCache, mock_pool: Mock
    ):
        """Test that starting auto-refresh twice doesn't create duplicate tasks."""
        pools = {"test_db": mock_pool}

        await cache.start_auto_refresh(1, pools)
        first_task = cache._refresh_task

        await cache.start_auto_refresh(1, pools)
        second_task = cache._refresh_task

        assert first_task is second_task

        await cache.stop_auto_refresh()

    @pytest.mark.asyncio
    async def test_stop_auto_refresh_stops_task(self, cache: SchemaCache, mock_pool: Mock):
        """Test that stop_auto_refresh stops the background task."""
        pools = {"test_db": mock_pool}

        await cache.start_auto_refresh(1, pools)
        assert cache._refresh_task is not None

        await cache.stop_auto_refresh()

        assert cache._stop_refresh is True
        assert cache._refresh_task.done() or cache._refresh_task.cancelled()

    @pytest.mark.asyncio
    async def test_stop_auto_refresh_when_not_running(self, cache: SchemaCache):
        """Test that stop_auto_refresh handles case when task is not running."""
        # Should not raise exception
        await cache.stop_auto_refresh()

        assert cache._stop_refresh is True

    @pytest.mark.asyncio
    async def test_auto_refresh_loop_refreshes_cached_schemas(
        self,
        cache: SchemaCache,
        mock_pool: Mock,
        sample_schema: DatabaseSchema,
    ):
        """Test that auto-refresh loop refreshes cached schemas."""
        # Pre-populate cache
        old_time = datetime.now(UTC) - timedelta(minutes=30)
        cache._cache["test_db"] = sample_schema
        cache._cache_timestamps["test_db"] = old_time

        pools = {"test_db": mock_pool}

        with patch("pg_mcp.cache.schema_cache.SchemaIntrospector") as mock_introspector_class:
            mock_introspector = AsyncMock()
            mock_introspector.introspect.return_value = sample_schema
            mock_introspector_class.return_value = mock_introspector

            # Start refresh with very short interval
            await cache.start_auto_refresh(1 / 60, pools)  # 1 second

            # Wait for at least one refresh cycle
            await asyncio.sleep(1.5)

            # Stop refresh
            await cache.stop_auto_refresh()

            # Verify cache was refreshed
            new_age = cache.get_cache_age("test_db")
            assert new_age is not None
            assert new_age < 30 * 60  # Should be fresher than the original 30 minutes

    @pytest.mark.asyncio
    async def test_auto_refresh_handles_exceptions(
        self,
        cache: SchemaCache,
        mock_pool: Mock,
        sample_schema: DatabaseSchema,
    ):
        """Test that auto-refresh continues after exceptions."""
        cache._cache["test_db"] = sample_schema
        cache._cache_timestamps["test_db"] = datetime.now(UTC)

        pools = {"test_db": mock_pool}

        with patch("pg_mcp.cache.schema_cache.SchemaIntrospector") as mock_introspector_class:
            # Make introspection fail
            mock_introspector = AsyncMock()
            mock_introspector.introspect.side_effect = Exception("Test error")
            mock_introspector_class.return_value = mock_introspector

            # Start refresh
            await cache.start_auto_refresh(1 / 60, pools)

            # Wait a bit
            await asyncio.sleep(0.5)

            # Stop refresh - should not raise exception
            await cache.stop_auto_refresh()

            assert cache._stop_refresh is True
