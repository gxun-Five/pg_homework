"""Unit tests for SQL Generator service.

This module tests the SQLGenerator class including SQL extraction logic,
error handling, and OpenAI API integration (using mocks).
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import SecretStr

from pg_mcp.config.settings import OpenAIConfig
from pg_mcp.models.errors import LLMError, LLMTimeoutError, LLMUnavailableError
from pg_mcp.models.schema import (
    ColumnInfo,
    DatabaseSchema,
    ForeignKeyInfo,
    IndexInfo,
    TableInfo,
)
from pg_mcp.services.sql_generator import SQLGenerator


class TestSQLExtraction:
    """Test SQL extraction logic from various response formats."""

    @pytest.fixture
    def generator(self) -> SQLGenerator:
        """Create SQLGenerator instance with test config."""
        config = OpenAIConfig(api_key=SecretStr("sk-test-key-12345"))
        return SQLGenerator(config)

    def test_extract_sql_from_code_block(self, generator: SQLGenerator) -> None:
        """Test extraction from markdown SQL code block."""
        content = """Here's the query:
```sql
SELECT * FROM users
WHERE created_at > CURRENT_DATE - INTERVAL '7 days';
```
This query gets recent users."""

        result = generator._extract_sql(content)
        assert result is not None
        assert result == "SELECT * FROM users\nWHERE created_at > CURRENT_DATE - INTERVAL '7 days';"

    def test_extract_sql_from_plain_code_block(self, generator: SQLGenerator) -> None:
        """Test extraction from plain code block without sql marker."""
        content = """```
SELECT COUNT(*) AS total
FROM orders;
```"""

        result = generator._extract_sql(content)
        assert result is not None
        assert "SELECT COUNT(*)" in result
        assert result.endswith(";")

    def test_extract_sql_from_text(self, generator: SQLGenerator) -> None:
        """Test extraction from plain text starting with SELECT."""
        content = "SELECT id, name FROM products WHERE price > 100;"

        result = generator._extract_sql(content)
        assert result is not None
        assert result == "SELECT id, name FROM products WHERE price > 100;"

    def test_extract_sql_with_cte(self, generator: SQLGenerator) -> None:
        """Test extraction of CTE (Common Table Expression) query."""
        content = """```sql
WITH active_users AS (
    SELECT user_id FROM sessions WHERE last_active > NOW() - INTERVAL '1 hour'
)
SELECT COUNT(*) FROM active_users;
```"""

        result = generator._extract_sql(content)
        assert result is not None
        assert result.startswith("WITH active_users")
        assert "SELECT COUNT(*)" in result

    def test_extract_sql_without_code_block(self, generator: SQLGenerator) -> None:
        """Test extraction when SQL is in plain text."""
        content = """
To answer your question, use this query:

SELECT u.name, COUNT(o.id) as order_count
FROM users u
LEFT JOIN orders o ON u.id = o.user_id
GROUP BY u.name;
"""

        result = generator._extract_sql(content)
        assert result is not None
        assert "SELECT u.name" in result
        assert "GROUP BY" in result

    def test_extract_sql_case_insensitive(self, generator: SQLGenerator) -> None:
        """Test extraction works with different case variations."""
        content = """```SQL
select * from Users;
```"""

        result = generator._extract_sql(content)
        assert result is not None
        assert result == "select * from Users;"

    def test_extract_sql_multiline(self, generator: SQLGenerator) -> None:
        """Test extraction of multiline query."""
        content = """```sql
SELECT
    u.id,
    u.name,
    u.email,
    COUNT(o.id) as order_count
FROM
    users u
    LEFT JOIN orders o ON u.id = o.user_id
WHERE
    u.status = 'active'
GROUP BY
    u.id, u.name, u.email
HAVING
    COUNT(o.id) > 5
ORDER BY
    order_count DESC
LIMIT 100;
```"""

        result = generator._extract_sql(content)
        assert result is not None
        assert result.startswith("SELECT")
        assert "LIMIT 100;" in result

    def test_extract_sql_returns_none_for_invalid(self, generator: SQLGenerator) -> None:
        """Test that extraction returns None for non-SQL content."""
        invalid_contents = [
            "",
            "This is just plain text without any SQL",
            "```\nNot a SQL query\n```",
            "UPDATE users SET name = 'test'",  # Not SELECT/WITH
            "DELETE FROM users WHERE id = 1",  # Not SELECT/WITH
        ]

        for content in invalid_contents:
            result = generator._extract_sql(content)
            # Should return None for UPDATE/DELETE (not SELECT/WITH)
            if content.startswith(("UPDATE", "DELETE")):
                assert result is None

    def test_extract_sql_removes_multiple_semicolons(self, generator: SQLGenerator) -> None:
        """Test that extraction normalizes trailing semicolons."""
        content = "```sql\nSELECT * FROM users;;\n```"

        result = generator._extract_sql(content)
        assert result is not None
        # Should normalize to single semicolon
        assert result.count(";") == 1
        assert result.endswith(";")

    def test_extract_sql_with_comments(self, generator: SQLGenerator) -> None:
        """Test extraction of SQL with comments."""
        content = """```sql
-- Get all active users
SELECT *
FROM users
WHERE status = 'active'  -- Only active ones
ORDER BY created_at DESC;
```"""

        result = generator._extract_sql(content)
        assert result is not None
        assert "-- Get all active users" in result
        assert "-- Only active ones" in result


class TestSQLGenerator:
    """Test SQL Generator with mocked OpenAI API."""

    @pytest.fixture
    def config(self) -> OpenAIConfig:
        """Create test OpenAI config."""
        return OpenAIConfig(
            api_key=SecretStr("sk-test-key-12345"),
            model="gpt-4o-mini",
            temperature=0.0,
            max_tokens=2000,
            timeout=30.0,
        )

    @pytest.fixture
    def generator(self, config: OpenAIConfig) -> SQLGenerator:
        """Create SQLGenerator instance."""
        return SQLGenerator(config)

    @pytest.fixture
    def mock_schema(self) -> DatabaseSchema:
        """Create mock database schema."""
        users_table = TableInfo(
            schema_name="public",
            table_name="users",
            columns=[
                ColumnInfo(
                    name="id",
                    data_type="integer",
                    is_nullable=False,
                    is_primary_key=True,
                ),
                ColumnInfo(
                    name="name",
                    data_type="varchar(255)",
                    is_nullable=False,
                ),
                ColumnInfo(
                    name="email",
                    data_type="varchar(255)",
                    is_nullable=False,
                    is_unique=True,
                ),
                ColumnInfo(
                    name="created_at",
                    data_type="timestamp",
                    is_nullable=False,
                    default_value="CURRENT_TIMESTAMP",
                ),
            ],
            indexes=[
                IndexInfo(
                    name="idx_users_email",
                    columns=["email"],
                    is_unique=True,
                    index_type="btree",
                ),
            ],
        )

        orders_table = TableInfo(
            schema_name="public",
            table_name="orders",
            columns=[
                ColumnInfo(
                    name="id",
                    data_type="integer",
                    is_nullable=False,
                    is_primary_key=True,
                ),
                ColumnInfo(
                    name="user_id",
                    data_type="integer",
                    is_nullable=False,
                ),
                ColumnInfo(
                    name="amount",
                    data_type="decimal(10,2)",
                    is_nullable=False,
                ),
                ColumnInfo(
                    name="created_at",
                    data_type="timestamp",
                    is_nullable=False,
                    default_value="CURRENT_TIMESTAMP",
                ),
            ],
            foreign_keys=[
                ForeignKeyInfo(
                    constraint_name="fk_orders_user",
                    column_name="user_id",
                    referenced_table="users",
                    referenced_column="id",
                ),
            ],
        )

        return DatabaseSchema(
            database_name="test_db",
            tables=[users_table, orders_table],
            version="15.0",
        )

    @pytest.mark.asyncio
    async def test_generate_simple_query(
        self, generator: SQLGenerator, mock_schema: DatabaseSchema
    ) -> None:
        """Test simple query generation with mocked OpenAI response."""
        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(message=MagicMock(content="```sql\nSELECT * FROM users;\n```"))
        ]

        # Use AsyncMock for async method
        with patch.object(
            generator.client.chat.completions, "create", new=AsyncMock(return_value=mock_response)
        ) as mock_create:
            result = await generator.generate("列出所有用户", mock_schema)

            # Verify OpenAI was called
            mock_create.assert_called_once()
            call_kwargs = mock_create.call_args.kwargs

            assert call_kwargs["model"] == "gpt-4o-mini"
            assert call_kwargs["temperature"] == 0.0
            assert len(call_kwargs["messages"]) == 2
            assert call_kwargs["messages"][0]["role"] == "system"
            assert call_kwargs["messages"][1]["role"] == "user"

            # Verify result
            assert result == "SELECT * FROM users;"

    @pytest.mark.asyncio
    async def test_generate_with_context(
        self, generator: SQLGenerator, mock_schema: DatabaseSchema
    ) -> None:
        """Test generation with additional context."""
        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(
                message=MagicMock(
                    content="```sql\nSELECT COUNT(*) FROM users WHERE status = 'active';\n```"
                )
            )
        ]

        with patch.object(
            generator.client.chat.completions, "create", new=AsyncMock(return_value=mock_response)
        ):
            result = await generator.generate(
                question="How many active users?",
                schema=mock_schema,
                context="Only count users with status='active'",
            )

            assert "SELECT COUNT(*)" in result
            assert result.endswith(";")

    @pytest.mark.asyncio
    async def test_generate_with_retry_context(
        self, generator: SQLGenerator, mock_schema: DatabaseSchema
    ) -> None:
        """Test generation with retry context (previous attempt + error)."""
        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(message=MagicMock(content="```sql\nSELECT COUNT(*) FROM users;\n```"))
        ]

        with patch.object(
            generator.client.chat.completions, "create", new=AsyncMock(return_value=mock_response)
        ) as mock_create:
            result = await generator.generate(
                question="Count users",
                schema=mock_schema,
                previous_attempt="SELECT COUNT(*) FROM user",
                error_feedback='relation "user" does not exist',
            )

            # Verify the prompt includes retry information
            user_prompt = mock_create.call_args.kwargs["messages"][1]["content"]
            assert "Previous Attempt (Failed)" in user_prompt
            assert "SELECT COUNT(*) FROM user" in user_prompt
            assert 'relation "user" does not exist' in user_prompt

            assert result == "SELECT COUNT(*) FROM users;"

    @pytest.mark.asyncio
    async def test_generate_handles_llm_timeout(
        self, generator: SQLGenerator, mock_schema: DatabaseSchema
    ) -> None:
        """Test LLM timeout error handling."""
        with patch.object(
            generator.client.chat.completions,
            "create",
            new=AsyncMock(side_effect=TimeoutError("Request timed out")),
        ):
            with pytest.raises(LLMTimeoutError) as exc_info:
                await generator.generate("Count users", mock_schema)

            assert "timed out" in str(exc_info.value).lower()
            assert exc_info.value.details["timeout"] == 30.0

    @pytest.mark.asyncio
    async def test_generate_handles_authentication_error(
        self, generator: SQLGenerator, mock_schema: DatabaseSchema
    ) -> None:
        """Test authentication error handling."""
        with patch.object(
            generator.client.chat.completions,
            "create",
            new=AsyncMock(side_effect=Exception("Authentication failed - invalid api_key")),
        ):
            with pytest.raises(LLMUnavailableError) as exc_info:
                await generator.generate("Count users", mock_schema)

            assert "authentication" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_generate_handles_rate_limit_error(
        self, generator: SQLGenerator, mock_schema: DatabaseSchema
    ) -> None:
        """Test rate limit error handling."""
        with patch.object(
            generator.client.chat.completions,
            "create",
            new=AsyncMock(side_effect=Exception("rate_limit exceeded")),
        ):
            with pytest.raises(LLMUnavailableError) as exc_info:
                await generator.generate("Count users", mock_schema)

            assert "rate limit" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_generate_handles_empty_response(
        self, generator: SQLGenerator, mock_schema: DatabaseSchema
    ) -> None:
        """Test handling of empty response from OpenAI."""
        mock_response = MagicMock()
        mock_response.choices = []

        with patch.object(
            generator.client.chat.completions, "create", new=AsyncMock(return_value=mock_response)
        ):
            with pytest.raises(LLMError) as exc_info:
                await generator.generate("Count users", mock_schema)

            assert "empty response" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_generate_handles_empty_content(
        self, generator: SQLGenerator, mock_schema: DatabaseSchema
    ) -> None:
        """Test handling of empty message content."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content=None))]

        with patch.object(
            generator.client.chat.completions, "create", new=AsyncMock(return_value=mock_response)
        ):
            with pytest.raises(LLMError) as exc_info:
                await generator.generate("Count users", mock_schema)

            assert "empty message content" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_generate_handles_invalid_sql_format(
        self, generator: SQLGenerator, mock_schema: DatabaseSchema
    ) -> None:
        """Test handling when SQL cannot be extracted from response."""
        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(message=MagicMock(content="I cannot generate a query for this request."))
        ]

        with patch.object(
            generator.client.chat.completions, "create", new=AsyncMock(return_value=mock_response)
        ):
            with pytest.raises(LLMError) as exc_info:
                await generator.generate("Invalid request", mock_schema)

            assert "failed to extract sql" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_generate_with_cte_query(
        self, generator: SQLGenerator, mock_schema: DatabaseSchema
    ) -> None:
        """Test generation of CTE query."""
        cte_sql = """WITH recent_orders AS (
    SELECT user_id, COUNT(*) as order_count
    FROM orders
    WHERE created_at >= CURRENT_DATE - INTERVAL '30 days'
    GROUP BY user_id
)
SELECT u.name, ro.order_count
FROM users u
INNER JOIN recent_orders ro ON u.id = ro.user_id
ORDER BY ro.order_count DESC
LIMIT 10;"""

        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content=f"```sql\n{cte_sql}\n```"))]

        with patch.object(
            generator.client.chat.completions, "create", new=AsyncMock(return_value=mock_response)
        ):
            result = await generator.generate(
                "Show top 10 users by order count in last 30 days", mock_schema
            )

            assert result.startswith("WITH recent_orders")
            assert "LIMIT 10;" in result

    @pytest.mark.asyncio
    async def test_generate_respects_config_settings(self, mock_schema: DatabaseSchema) -> None:
        """Test that generator respects all config settings."""
        custom_config = OpenAIConfig(
            api_key=SecretStr("sk-custom-key"),
            model="gpt-4",
            temperature=0.5,
            max_tokens=1000,
            timeout=60.0,
        )
        generator = SQLGenerator(custom_config)

        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="```sql\nSELECT 1;\n```"))]

        with patch.object(
            generator.client.chat.completions, "create", new=AsyncMock(return_value=mock_response)
        ) as mock_create:
            await generator.generate("Test query", mock_schema)

            call_kwargs = mock_create.call_args.kwargs
            assert call_kwargs["model"] == "gpt-4"
            assert call_kwargs["temperature"] == 0.5
            assert call_kwargs["max_tokens"] == 1000

    @pytest.mark.asyncio
    async def test_generate_includes_schema_context(
        self, generator: SQLGenerator, mock_schema: DatabaseSchema
    ) -> None:
        """Test that schema context is included in the prompt."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="```sql\nSELECT 1;\n```"))]

        with patch.object(
            generator.client.chat.completions, "create", new=AsyncMock(return_value=mock_response)
        ) as mock_create:
            await generator.generate("Test query", mock_schema)

            user_prompt = mock_create.call_args.kwargs["messages"][1]["content"]
            # Verify schema information is in the prompt
            assert "Database Schema:" in user_prompt
            assert "test_db" in user_prompt
            assert "users" in user_prompt
            assert "orders" in user_prompt
            assert "PostgreSQL Version: 15.0" in user_prompt

    @pytest.mark.asyncio
    async def test_generate_generic_error(
        self, generator: SQLGenerator, mock_schema: DatabaseSchema
    ) -> None:
        """Test handling of generic OpenAI errors."""
        with patch.object(
            generator.client.chat.completions,
            "create",
            new=AsyncMock(side_effect=Exception("Unknown error occurred")),
        ):
            with pytest.raises(LLMError) as exc_info:
                await generator.generate("Count users", mock_schema)

            assert "OpenAI API request failed" in str(exc_info.value)
            assert exc_info.value.details["error"] == "Unknown error occurred"
