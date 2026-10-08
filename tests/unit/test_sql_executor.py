"""Unit tests for SQLExecutor.

This module tests the SQL execution functionality including session parameter
configuration, result serialization, row limiting, and error handling.
"""

import asyncio
import datetime
import decimal
import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import asyncpg
import pytest

from pg_mcp.config.settings import DatabaseConfig, SecurityConfig
from pg_mcp.models.errors import DatabaseError, ExecutionTimeoutError
from pg_mcp.services.sql_executor import SQLExecutor


def create_mock_record(data: dict[str, Any]) -> MagicMock:
    """Create a mock asyncpg.Record object that supports dict() conversion.

    Args:
        data: Dictionary of column names to values.

    Returns:
        MagicMock that behaves like an asyncpg.Record.
    """
    mock_record = MagicMock()
    mock_record.__iter__ = MagicMock(return_value=iter(data.items()))
    mock_record.keys = MagicMock(return_value=list(data.keys()))
    mock_record.values = MagicMock(return_value=list(data.values()))
    mock_record.items = MagicMock(return_value=list(data.items()))
    mock_record.__getitem__ = lambda self, key: data[key]
    mock_record.__len__ = lambda self: len(data)
    return mock_record


@pytest.fixture
def security_config() -> SecurityConfig:
    """Create a default security configuration for testing."""
    return SecurityConfig(
        max_execution_time=30.0,
        max_rows=10000,
        safe_search_path="public",
        readonly_role=None,
    )


@pytest.fixture
def security_config_with_role() -> SecurityConfig:
    """Create security config with readonly role configured."""
    return SecurityConfig(
        max_execution_time=30.0,
        max_rows=10000,
        safe_search_path="public",
        readonly_role="readonly_user",
    )


@pytest.fixture
def db_config() -> DatabaseConfig:
    """Create a default database configuration for testing."""
    return DatabaseConfig(
        host="localhost",
        port=5432,
        name="testdb",
        user="testuser",
        password="testpass",
    )


@pytest.fixture
def mock_connection() -> MagicMock:
    """Create a mock asyncpg connection."""
    conn = MagicMock()
    conn.execute = AsyncMock()
    conn.fetch = AsyncMock()

    # Setup transaction context manager
    transaction_mock = MagicMock()
    transaction_mock.__aenter__ = AsyncMock(return_value=None)
    transaction_mock.__aexit__ = AsyncMock(return_value=None)
    conn.transaction = MagicMock(return_value=transaction_mock)

    return conn


@pytest.fixture
def mock_pool(mock_connection: MagicMock) -> MagicMock:
    """Create a mock asyncpg connection pool."""
    pool = MagicMock()

    # Setup acquire context manager
    acquire_mock = MagicMock()
    acquire_mock.__aenter__ = AsyncMock(return_value=mock_connection)
    acquire_mock.__aexit__ = AsyncMock(return_value=None)
    pool.acquire = MagicMock(return_value=acquire_mock)

    return pool


@pytest.fixture
def executor(
    mock_pool: MagicMock,
    security_config: SecurityConfig,
    db_config: DatabaseConfig,
) -> SQLExecutor:
    """Create a SQLExecutor instance with mocked dependencies."""
    return SQLExecutor(
        pool=mock_pool,
        security_config=security_config,
        db_config=db_config,
    )


class TestSQLExecutor:
    """Test suite for SQLExecutor class."""

    @pytest.mark.asyncio
    async def test_execute_basic_query(
        self,
        executor: SQLExecutor,
        mock_pool: MagicMock,
        mock_connection: MagicMock,
    ) -> None:
        """Test executing a basic SQL query successfully."""
        # Arrange
        sql = "SELECT id, name FROM users"
        mock_records = [
            create_mock_record({"id": 1, "name": "Alice"}),
            create_mock_record({"id": 2, "name": "Bob"}),
        ]

        mock_connection.fetch.return_value = mock_records

        # Act
        results, count = await executor.execute(sql)

        # Assert
        assert count == 2
        assert len(results) == 2
        assert results[0]["id"] == 1
        assert results[0]["name"] == "Alice"
        assert results[1]["id"] == 2
        assert results[1]["name"] == "Bob"

        # Verify session parameters were set
        assert mock_connection.execute.call_count >= 2  # timeout and search_path
        mock_connection.fetch.assert_called_once_with(sql)

    @pytest.mark.asyncio
    async def test_execute_with_custom_timeout_and_max_rows(
        self,
        executor: SQLExecutor,
        mock_pool: MagicMock,
        mock_connection: MagicMock,
    ) -> None:
        """Test executing query with custom timeout and row limit."""
        # Arrange
        sql = "SELECT * FROM large_table"
        custom_timeout = 60.0
        custom_max_rows = 100

        # Create 200 mock records
        mock_records = [create_mock_record({"id": i, "value": f"row_{i}"}) for i in range(200)]
        mock_connection.fetch.return_value = mock_records

        # Act
        results, count = await executor.execute(
            sql, timeout=custom_timeout, max_rows=custom_max_rows
        )

        # Assert
        assert count == 200  # Total count before limiting
        assert len(results) == 100  # Limited to max_rows
        assert results[0]["id"] == 0
        assert results[99]["id"] == 99

    @pytest.mark.asyncio
    async def test_execute_timeout_error(
        self,
        executor: SQLExecutor,
        mock_pool: MagicMock,
        mock_connection: MagicMock,
    ) -> None:
        """Test that timeout errors are properly raised."""
        # Arrange
        sql = "SELECT * FROM slow_query"

        # Simulate timeout
        async def slow_fetch(*args: Any, **kwargs: Any) -> None:
            await asyncio.sleep(10)

        mock_connection.fetch = slow_fetch

        # Act & Assert
        with pytest.raises(ExecutionTimeoutError) as exc_info:
            await executor.execute(sql, timeout=0.1)

        assert "exceeded timeout" in str(exc_info.value.message).lower()
        assert exc_info.value.details["timeout_seconds"] == 0.1

    @pytest.mark.asyncio
    async def test_execute_database_error(
        self,
        executor: SQLExecutor,
        mock_pool: MagicMock,
        mock_connection: MagicMock,
    ) -> None:
        """Test that database errors are properly wrapped."""
        # Arrange
        sql = "SELECT * FROM nonexistent_table"
        pg_error = asyncpg.PostgresError("relation 'nonexistent_table' does not exist")
        pg_error.sqlstate = "42P01"

        mock_connection.fetch.side_effect = pg_error

        # Act & Assert
        with pytest.raises(DatabaseError) as exc_info:
            await executor.execute(sql)

        assert "database query failed" in str(exc_info.value.message).lower()
        assert exc_info.value.details["error_code"] == "42P01"

    @pytest.mark.asyncio
    async def test_session_params_basic(
        self,
        executor: SQLExecutor,
        mock_pool: MagicMock,
        mock_connection: MagicMock,
    ) -> None:
        """Test that basic session parameters are set correctly."""
        # Arrange
        sql = "SELECT 1"
        mock_connection.fetch.return_value = [create_mock_record({"column": 1})]

        # Act
        await executor.execute(sql, timeout=15.0)

        # Assert - verify SET commands were called
        execute_calls = mock_connection.execute.call_args_list
        execute_commands = [str(call[0][0]) for call in execute_calls]

        # Check timeout was set (15 seconds = 15000 ms)
        assert any("SET statement_timeout = 15000" in cmd for cmd in execute_commands)

        # Check search_path was set
        assert any("SET search_path = 'public'" in cmd for cmd in execute_commands)

    @pytest.mark.asyncio
    async def test_session_params_with_readonly_role(
        self,
        mock_connection: MagicMock,
        security_config_with_role: SecurityConfig,
        db_config: DatabaseConfig,
    ) -> None:
        """Test that readonly role is set when configured."""
        # Arrange
        # Create a new pool with the mock connection
        pool = MagicMock()
        acquire_mock = MagicMock()
        acquire_mock.__aenter__ = AsyncMock(return_value=mock_connection)
        acquire_mock.__aexit__ = AsyncMock(return_value=None)
        pool.acquire = MagicMock(return_value=acquire_mock)

        executor = SQLExecutor(
            pool=pool,
            security_config=security_config_with_role,
            db_config=db_config,
        )
        sql = "SELECT 1"
        mock_connection.fetch.return_value = [create_mock_record({"column": 1})]

        # Act
        await executor.execute(sql)

        # Assert - verify SET ROLE was called
        execute_calls = mock_connection.execute.call_args_list
        execute_commands = [str(call[0][0]) for call in execute_calls]
        assert any("SET ROLE readonly_user" in cmd for cmd in execute_commands)

    @pytest.mark.asyncio
    async def test_session_params_invalid_search_path(
        self,
        mock_connection: MagicMock,
        db_config: DatabaseConfig,
    ) -> None:
        """Test that invalid search_path is rejected."""
        # Arrange
        malicious_config = SecurityConfig(
            max_execution_time=30.0,
            max_rows=10000,
            safe_search_path="public; DROP TABLE users;--",  # SQL injection attempt
            readonly_role=None,
        )
        # Create a new pool with the mock connection
        pool = MagicMock()
        acquire_mock = MagicMock()
        acquire_mock.__aenter__ = AsyncMock(return_value=mock_connection)
        acquire_mock.__aexit__ = AsyncMock(return_value=None)
        pool.acquire = MagicMock(return_value=acquire_mock)

        executor = SQLExecutor(
            pool=pool,
            security_config=malicious_config,
            db_config=db_config,
        )
        sql = "SELECT 1"

        # Act & Assert
        with pytest.raises(DatabaseError) as exc_info:
            await executor.execute(sql)

        assert "invalid search_path" in str(exc_info.value.message).lower()

    @pytest.mark.asyncio
    async def test_session_params_invalid_role(
        self,
        mock_connection: MagicMock,
        db_config: DatabaseConfig,
    ) -> None:
        """Test that invalid role name is rejected."""
        # Arrange
        malicious_config = SecurityConfig(
            max_execution_time=30.0,
            max_rows=10000,
            safe_search_path="public",
            readonly_role="admin; DROP TABLE users;--",  # SQL injection attempt
        )
        # Create a new pool with the mock connection
        pool = MagicMock()
        acquire_mock = MagicMock()
        acquire_mock.__aenter__ = AsyncMock(return_value=mock_connection)
        acquire_mock.__aexit__ = AsyncMock(return_value=None)
        pool.acquire = MagicMock(return_value=acquire_mock)

        executor = SQLExecutor(
            pool=pool,
            security_config=malicious_config,
            db_config=db_config,
        )
        sql = "SELECT 1"

        # Act & Assert
        with pytest.raises(DatabaseError) as exc_info:
            await executor.execute(sql)

        assert "invalid readonly_role" in str(exc_info.value.message).lower()


class TestResultSerialization:
    """Test suite for result serialization."""

    @pytest.fixture
    def executor_for_serialization(
        self,
        mock_pool: MagicMock,
        security_config: SecurityConfig,
        db_config: DatabaseConfig,
    ) -> SQLExecutor:
        """Create executor for serialization tests."""
        return SQLExecutor(
            pool=mock_pool,
            security_config=security_config,
            db_config=db_config,
        )

    def test_serialize_datetime_types(
        self,
        executor_for_serialization: SQLExecutor,
    ) -> None:
        """Test serialization of datetime, date, and time types."""
        # Arrange
        results = [
            {
                "timestamp": datetime.datetime(2024, 1, 15, 12, 30, 45),
                "date": datetime.date(2024, 1, 15),
                "time": datetime.time(12, 30, 45),
            }
        ]

        # Act
        serialized = executor_for_serialization._serialize_results(results)

        # Assert
        assert serialized[0]["timestamp"] == "2024-01-15T12:30:45"
        assert serialized[0]["date"] == "2024-01-15"
        assert serialized[0]["time"] == "12:30:45"

    def test_serialize_timedelta(
        self,
        executor_for_serialization: SQLExecutor,
    ) -> None:
        """Test serialization of timedelta."""
        # Arrange
        results = [{"duration": datetime.timedelta(days=1, hours=2, minutes=30)}]

        # Act
        serialized = executor_for_serialization._serialize_results(results)

        # Assert
        assert serialized[0]["duration"] == "1 day, 2:30:00"

    def test_serialize_decimal(
        self,
        executor_for_serialization: SQLExecutor,
    ) -> None:
        """Test serialization of Decimal to float."""
        # Arrange
        results = [
            {
                "price": decimal.Decimal("99.99"),
                "tax": decimal.Decimal("7.50"),
            }
        ]

        # Act
        serialized = executor_for_serialization._serialize_results(results)

        # Assert
        assert serialized[0]["price"] == 99.99
        assert serialized[0]["tax"] == 7.50
        assert isinstance(serialized[0]["price"], float)

    def test_serialize_uuid(
        self,
        executor_for_serialization: SQLExecutor,
    ) -> None:
        """Test serialization of UUID to string."""
        # Arrange
        test_uuid = uuid.UUID("550e8400-e29b-41d4-a716-446655440000")
        results = [{"id": test_uuid}]

        # Act
        serialized = executor_for_serialization._serialize_results(results)

        # Assert
        assert serialized[0]["id"] == "550e8400-e29b-41d4-a716-446655440000"
        assert isinstance(serialized[0]["id"], str)

    def test_serialize_bytes(
        self,
        executor_for_serialization: SQLExecutor,
    ) -> None:
        """Test serialization of bytes to hex string."""
        # Arrange
        results = [{"data": b"\x00\x01\x02\x03\xff"}]

        # Act
        serialized = executor_for_serialization._serialize_results(results)

        # Assert
        assert serialized[0]["data"] == "00010203ff"
        assert isinstance(serialized[0]["data"], str)

    def test_serialize_list(
        self,
        executor_for_serialization: SQLExecutor,
    ) -> None:
        """Test recursive serialization of lists."""
        # Arrange
        results = [
            {
                "tags": ["tag1", "tag2"],
                "dates": [datetime.date(2024, 1, 1), datetime.date(2024, 1, 2)],
                "prices": [decimal.Decimal("10.50"), decimal.Decimal("20.75")],
            }
        ]

        # Act
        serialized = executor_for_serialization._serialize_results(results)

        # Assert
        assert serialized[0]["tags"] == ["tag1", "tag2"]
        assert serialized[0]["dates"] == ["2024-01-01", "2024-01-02"]
        assert serialized[0]["prices"] == [10.50, 20.75]

    def test_serialize_dict(
        self,
        executor_for_serialization: SQLExecutor,
    ) -> None:
        """Test recursive serialization of nested dicts."""
        # Arrange
        results = [
            {
                "metadata": {
                    "created": datetime.datetime(2024, 1, 1, 12, 0),
                    "price": decimal.Decimal("99.99"),
                    "id": uuid.UUID("550e8400-e29b-41d4-a716-446655440000"),
                }
            }
        ]

        # Act
        serialized = executor_for_serialization._serialize_results(results)

        # Assert
        assert serialized[0]["metadata"]["created"] == "2024-01-01T12:00:00"
        assert serialized[0]["metadata"]["price"] == 99.99
        assert serialized[0]["metadata"]["id"] == "550e8400-e29b-41d4-a716-446655440000"

    def test_serialize_none_values(
        self,
        executor_for_serialization: SQLExecutor,
    ) -> None:
        """Test that None values are preserved."""
        # Arrange
        results = [
            {
                "nullable_string": None,
                "nullable_date": None,
                "nullable_decimal": None,
            }
        ]

        # Act
        serialized = executor_for_serialization._serialize_results(results)

        # Assert
        assert serialized[0]["nullable_string"] is None
        assert serialized[0]["nullable_date"] is None
        assert serialized[0]["nullable_decimal"] is None

    def test_serialize_mixed_types(
        self,
        executor_for_serialization: SQLExecutor,
    ) -> None:
        """Test serialization of complex nested structures."""
        # Arrange
        results = [
            {
                "id": 1,
                "name": "Test User",
                "created_at": datetime.datetime(2024, 1, 1, 12, 0),
                "balance": decimal.Decimal("1000.50"),
                "user_id": uuid.UUID("550e8400-e29b-41d4-a716-446655440000"),
                "tags": ["vip", "active"],
                "metadata": {
                    "last_login": datetime.datetime(2024, 1, 15, 10, 30),
                    "preferences": {"theme": "dark", "notifications": True},
                },
                "binary_data": b"\x01\x02\x03",
                "optional_field": None,
            }
        ]

        # Act
        serialized = executor_for_serialization._serialize_results(results)

        # Assert
        assert serialized[0]["id"] == 1
        assert serialized[0]["name"] == "Test User"
        assert serialized[0]["created_at"] == "2024-01-01T12:00:00"
        assert serialized[0]["balance"] == 1000.50
        assert serialized[0]["user_id"] == "550e8400-e29b-41d4-a716-446655440000"
        assert serialized[0]["tags"] == ["vip", "active"]
        assert serialized[0]["metadata"]["last_login"] == "2024-01-15T10:30:00"
        assert serialized[0]["metadata"]["preferences"]["theme"] == "dark"
        assert serialized[0]["binary_data"] == "010203"
        assert serialized[0]["optional_field"] is None


class TestRowLimiting:
    """Test suite for row limiting functionality."""

    @pytest.mark.asyncio
    async def test_row_limiting_applied(
        self,
        executor: SQLExecutor,
        mock_pool: MagicMock,
        mock_connection: MagicMock,
    ) -> None:
        """Test that row limiting is properly applied."""
        # Arrange
        sql = "SELECT * FROM large_table"
        max_rows = 10

        # Create 100 mock records
        mock_records = [create_mock_record({"id": i, "value": f"row_{i}"}) for i in range(100)]
        mock_connection.fetch.return_value = mock_records

        # Act
        results, count = await executor.execute(sql, max_rows=max_rows)

        # Assert
        assert count == 100  # Total count
        assert len(results) == 10  # Limited results
        # Verify we got the first N rows
        for i in range(10):
            assert results[i]["id"] == i

    @pytest.mark.asyncio
    async def test_row_limiting_not_exceeded(
        self,
        executor: SQLExecutor,
        mock_pool: MagicMock,
        mock_connection: MagicMock,
    ) -> None:
        """Test when actual rows are less than limit."""
        # Arrange
        sql = "SELECT * FROM small_table"
        max_rows = 100

        # Create only 10 records
        mock_records = [create_mock_record({"id": i, "value": f"row_{i}"}) for i in range(10)]
        mock_connection.fetch.return_value = mock_records

        # Act
        results, count = await executor.execute(sql, max_rows=max_rows)

        # Assert
        assert count == 10
        assert len(results) == 10  # All results returned
