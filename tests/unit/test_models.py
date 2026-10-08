"""Unit tests for data models.

Tests for schema, query, and error models to ensure correct validation
and behavior.
"""

import pytest
from pydantic import ValidationError

from pg_mcp.models.errors import (
    DatabaseError,
    ErrorCode,
    ErrorDetail,
    LLMTimeoutError,
    LLMUnavailableError,
    PgMcpError,
    SecurityViolationError,
    SQLParseError,
)
from pg_mcp.models.query import QueryRequest, QueryResponse, QueryResult, ReturnType
from pg_mcp.models.schema import (
    ColumnInfo,
    DatabaseSchema,
    EnumTypeInfo,
    ForeignKeyInfo,
    IndexInfo,
    TableInfo,
)


class TestColumnInfo:
    """Tests for ColumnInfo model."""

    def test_basic_column(self) -> None:
        """Test basic column creation."""
        col = ColumnInfo(
            name="id",
            data_type="integer",
            is_nullable=False,
            is_primary_key=True,
        )
        assert col.name == "id"
        assert col.data_type == "integer"
        assert not col.is_nullable
        assert col.is_primary_key

    def test_column_with_default(self) -> None:
        """Test column with default value."""
        col = ColumnInfo(
            name="created_at",
            data_type="timestamp",
            is_nullable=False,
            default_value="now()",
        )
        assert col.default_value == "now()"

    def test_to_prompt_line_primary_key(self) -> None:
        """Test prompt formatting for primary key column."""
        col = ColumnInfo(
            name="id",
            data_type="integer",
            is_nullable=False,
            is_primary_key=True,
        )
        line = col.to_prompt_line()
        assert "id: integer" in line
        assert "PRIMARY KEY" in line
        assert "NOT NULL" in line

    def test_to_prompt_line_with_comment(self) -> None:
        """Test prompt formatting with comment."""
        col = ColumnInfo(
            name="email",
            data_type="varchar(255)",
            is_nullable=False,
            is_unique=True,
            comment="User email address",
        )
        line = col.to_prompt_line()
        assert "email: varchar(255)" in line
        assert "UNIQUE" in line
        assert "User email address" in line


class TestForeignKeyInfo:
    """Tests for ForeignKeyInfo model."""

    def test_foreign_key_creation(self) -> None:
        """Test foreign key creation."""
        fk = ForeignKeyInfo(
            constraint_name="fk_user_id",
            column_name="user_id",
            referenced_table="users",
            referenced_column="id",
        )
        assert fk.column_name == "user_id"
        assert fk.referenced_table == "users"

    def test_to_prompt_line(self) -> None:
        """Test prompt formatting."""
        fk = ForeignKeyInfo(
            constraint_name="fk_user_id",
            column_name="user_id",
            referenced_table="users",
            referenced_column="id",
        )
        line = fk.to_prompt_line()
        assert "user_id -> users.id" in line


class TestIndexInfo:
    """Tests for IndexInfo model."""

    def test_basic_index(self) -> None:
        """Test basic index creation."""
        idx = IndexInfo(
            name="idx_email",
            columns=["email"],
            is_unique=True,
        )
        assert idx.name == "idx_email"
        assert idx.columns == ["email"]
        assert idx.is_unique

    def test_composite_index(self) -> None:
        """Test composite index."""
        idx = IndexInfo(
            name="idx_user_created",
            columns=["user_id", "created_at"],
            index_type="btree",
        )
        assert len(idx.columns) == 2
        line = idx.to_prompt_line()
        assert "user_id, created_at" in line


class TestTableInfo:
    """Tests for TableInfo model."""

    def test_basic_table(self) -> None:
        """Test basic table creation."""
        table = TableInfo(
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
                    name="email",
                    data_type="varchar(255)",
                    is_nullable=False,
                    is_unique=True,
                ),
            ],
        )
        assert table.table_name == "users"
        assert len(table.columns) == 2
        assert table.full_name == "public.users"

    def test_to_prompt_section(self) -> None:
        """Test prompt section generation."""
        table = TableInfo(
            schema_name="public",
            table_name="users",
            columns=[
                ColumnInfo(
                    name="id",
                    data_type="integer",
                    is_nullable=False,
                    is_primary_key=True,
                )
            ],
            comment="User accounts",
        )
        section = table.to_prompt_section()
        assert "Table: public.users" in section
        assert "Description: User accounts" in section
        assert "Columns:" in section


class TestEnumTypeInfo:
    """Tests for EnumTypeInfo model."""

    def test_enum_creation(self) -> None:
        """Test enum type creation."""
        enum = EnumTypeInfo(
            schema_name="public",
            type_name="user_status",
            values=["active", "inactive", "suspended"],
        )
        assert enum.type_name == "user_status"
        assert len(enum.values) == 3
        assert enum.full_name == "public.user_status"

    def test_to_prompt_line(self) -> None:
        """Test prompt formatting."""
        enum = EnumTypeInfo(
            schema_name="public",
            type_name="user_status",
            values=["active", "inactive"],
        )
        line = enum.to_prompt_line()
        assert "user_status:" in line
        assert "'active'" in line
        assert "'inactive'" in line


class TestDatabaseSchema:
    """Tests for DatabaseSchema model."""

    def test_empty_schema(self) -> None:
        """Test empty schema creation."""
        schema = DatabaseSchema(database_name="testdb")
        assert schema.database_name == "testdb"
        assert len(schema.tables) == 0
        assert len(schema.enum_types) == 0

    def test_get_table(self) -> None:
        """Test table lookup."""
        table = TableInfo(schema_name="public", table_name="users", columns=[])
        schema = DatabaseSchema(database_name="testdb", tables=[table])

        found = schema.get_table("users")
        assert found is not None
        assert found.table_name == "users"

        not_found = schema.get_table("nonexistent")
        assert not_found is None

    def test_to_prompt_context(self) -> None:
        """Test full schema prompt generation."""
        schema = DatabaseSchema(
            database_name="testdb",
            version="16.0",
            tables=[
                TableInfo(
                    schema_name="public",
                    table_name="users",
                    columns=[
                        ColumnInfo(
                            name="id",
                            data_type="integer",
                            is_nullable=False,
                            is_primary_key=True,
                        )
                    ],
                )
            ],
            enum_types=[
                EnumTypeInfo(
                    schema_name="public",
                    type_name="user_status",
                    values=["active", "inactive"],
                )
            ],
        )
        context = schema.to_prompt_context()
        assert "Database: testdb" in context
        assert "PostgreSQL Version: 16.0" in context
        assert "Custom Types" in context
        assert "Tables" in context


class TestQueryRequest:
    """Tests for QueryRequest model."""

    def test_valid_request(self) -> None:
        """Test valid query request."""
        req = QueryRequest(
            question="How many users are there?",
            return_type=ReturnType.RESULT,
        )
        assert req.question == "How many users are there?"
        assert req.return_type == ReturnType.RESULT

    def test_question_sanitization(self) -> None:
        """Test question is stripped."""
        req = QueryRequest(question="  trimmed  ")
        assert req.question == "trimmed"

    def test_empty_question_rejected(self) -> None:
        """Test empty question is rejected."""
        with pytest.raises(ValidationError):
            QueryRequest(question="")

    def test_whitespace_only_rejected(self) -> None:
        """Test whitespace-only question is rejected."""
        with pytest.raises(ValidationError):
            QueryRequest(question="   ")

    def test_question_too_long(self) -> None:
        """Test question length limit."""
        with pytest.raises(ValidationError):
            QueryRequest(question="x" * 10001)


class TestQueryResult:
    """Tests for QueryResult model."""

    def test_empty_result(self) -> None:
        """Test empty result."""
        result = QueryResult()
        assert result.row_count == 0
        assert len(result.rows) == 0
        assert len(result.columns) == 0

    def test_result_with_data(self) -> None:
        """Test result with data."""
        result = QueryResult(
            columns=["id", "name"],
            rows=[
                {"id": 1, "name": "Alice"},
                {"id": 2, "name": "Bob"},
            ],
            row_count=2,
            execution_time_ms=15.5,
        )
        assert result.row_count == 2
        assert len(result.rows) == 2
        assert result.execution_time_ms == 15.5


class TestQueryResponse:
    """Tests for QueryResponse model."""

    def test_successful_response(self) -> None:
        """Test successful query response."""
        response = QueryResponse(
            success=True,
            generated_sql="SELECT COUNT(*) FROM users",
            data=QueryResult(
                columns=["count"],
                rows=[{"count": 10}],
                row_count=1,
            ),
            confidence=95,
        )
        assert response.success
        assert response.generated_sql is not None
        assert response.data is not None
        assert response.confidence == 95

    def test_error_response(self) -> None:
        """Test error response."""
        from pg_mcp.models.query import ErrorDetail

        response = QueryResponse(
            success=False,
            error=ErrorDetail(
                code="sql_parse_error",
                message="Invalid SQL syntax",
            ),
        )
        assert not response.success
        assert response.error is not None
        assert response.error.code == "sql_parse_error"

    def test_sql_only_response(self) -> None:
        """Test response with SQL only (no execution)."""
        response = QueryResponse(
            success=True,
            generated_sql="SELECT * FROM users",
            confidence=90,
        )
        assert response.success
        assert response.generated_sql is not None
        assert response.data is None


class TestErrorModels:
    """Tests for error models."""

    def test_error_detail(self) -> None:
        """Test ErrorDetail creation."""
        detail = ErrorDetail(
            code=ErrorCode.SQL_PARSE_ERROR,
            message="Invalid syntax",
            details={"position": 10},
        )
        assert detail.code == ErrorCode.SQL_PARSE_ERROR
        assert detail.message == "Invalid syntax"
        assert detail.details["position"] == 10

    def test_error_detail_to_dict(self) -> None:
        """Test ErrorDetail serialization."""
        detail = ErrorDetail(
            code=ErrorCode.DATABASE_ERROR,
            message="Connection failed",
        )
        d = detail.to_dict()
        assert d["code"] == ErrorCode.DATABASE_ERROR
        assert d["message"] == "Connection failed"

    def test_base_exception(self) -> None:
        """Test PgMcpError base exception."""
        err = PgMcpError(
            message="Something went wrong",
            code=ErrorCode.INTERNAL_ERROR,
        )
        assert str(err) == "Something went wrong"
        assert err.code == ErrorCode.INTERNAL_ERROR

    def test_security_violation_error(self) -> None:
        """Test SecurityViolationError."""
        err = SecurityViolationError(
            message="DELETE not allowed",
            details={"statement": "DELETE"},
        )
        assert err.code == ErrorCode.SECURITY_VIOLATION
        assert "DELETE not allowed" in str(err)

    def test_sql_parse_error(self) -> None:
        """Test SQLParseError."""
        err = SQLParseError(message="Invalid SQL")
        assert err.code == ErrorCode.SQL_PARSE_ERROR

    def test_database_error(self) -> None:
        """Test DatabaseError."""
        err = DatabaseError(message="Query failed")
        assert err.code == ErrorCode.DATABASE_ERROR

    def test_llm_timeout_error(self) -> None:
        """Test LLMTimeoutError."""
        err = LLMTimeoutError(message="Request timed out")
        assert err.code == ErrorCode.LLM_TIMEOUT

    def test_llm_unavailable_error(self) -> None:
        """Test LLMUnavailableError."""
        err = LLMUnavailableError(message="API unavailable")
        assert err.code == ErrorCode.LLM_UNAVAILABLE

    def test_error_to_detail(self) -> None:
        """Test exception to ErrorDetail conversion."""
        err = SecurityViolationError(
            message="Blocked function",
            details={"function": "pg_sleep"},
        )
        detail = err.to_error_detail()
        assert detail.code == ErrorCode.SECURITY_VIOLATION
        assert detail.message == "Blocked function"
        assert detail.details["function"] == "pg_sleep"
