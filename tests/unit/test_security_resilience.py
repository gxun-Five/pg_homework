"""Tests for multi-database routing, security controls, resilience, and observability.

These tests verify the functionality described in the supplementary implementation
plan that was previously only designed but not wired into the request flow:

- Per-database executor selection (a request is executed against the requested DB)
- Table/column access restrictions and EXPLAIN policy via configuration
- allow_write_operations actually enabling INSERT/UPDATE/DELETE
- Rate limiting integrated into the query pipeline
- Retry with exponential backoff
- Metrics and request tracing integrated into the request flow
- Schema cache maximum size enforcement
- Removal of the duplicate QueryResponse.to_dict
- Offline startup (server runs without a database connection via PG_MCP_OFFLINE)
"""

from contextlib import asynccontextmanager
from unittest.mock import ANY, AsyncMock, MagicMock, patch

import pytest

from pg_mcp.cache.schema_cache import SchemaCache
from pg_mcp.config.settings import (
    CacheConfig,
    ResilienceConfig,
    SecurityConfig,
    ValidationConfig,
)
from pg_mcp.db.introspection import SchemaIntrospector
from pg_mcp.models.errors import (
    ErrorCode,
    SecurityViolationError,
    SQLParseError,
)
from pg_mcp.models.query import QueryRequest, QueryResponse, ReturnType
from pg_mcp.models.schema import ColumnInfo, DatabaseSchema, TableInfo
from pg_mcp.resilience.rate_limiter import MultiRateLimiter
from pg_mcp.services.orchestrator import QueryOrchestrator
from pg_mcp.services.sql_validator import SQLValidator


def _schema(name: str = "test_db") -> DatabaseSchema:
    """Build a minimal database schema for tests."""
    return DatabaseSchema(
        database_name=name,
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
                    ),
                    ColumnInfo(name="name", data_type="varchar(255)", is_nullable=False),
                ],
            )
        ],
        version="15.0",
    )


def _orchestrator(
    *,
    sql_executors: dict[str, MagicMock] | None = None,
    pools: dict[str, MagicMock] | None = None,
    rate_limiter: MultiRateLimiter | None = None,
    metrics: MagicMock | None = None,
    resilience_config: ResilienceConfig | None = None,
) -> QueryOrchestrator:
    """Create an orchestrator with sensible mocks for unit tests."""
    pools = pools or {"test_db": MagicMock()}
    sql_executors = sql_executors or {"test_db": AsyncMock()}
    return QueryOrchestrator(
        sql_generator=AsyncMock(),
        sql_validator=MagicMock(),
        result_validator=MagicMock(),
        schema_cache=MagicMock(),
        pools=pools,
        resilience_config=resilience_config or ResilienceConfig(),
        validation_config=ValidationConfig(),
        sql_executors=sql_executors,
        rate_limiter=rate_limiter,
        metrics=metrics,
    )


class TestMultiDatabaseRouting:
    """Ensure a query is executed against the database it resolved to."""

    @pytest.mark.asyncio
    async def test_execute_query_routes_to_correct_executor(self) -> None:
        schema = _schema("db2")
        cache = MagicMock()
        cache.get.return_value = schema

        exec_db1 = AsyncMock()
        exec_db2 = AsyncMock()
        exec_db2.execute.return_value = ([{"id": 7}], 1)

        gen = AsyncMock()
        gen.generate.return_value = "SELECT id FROM users;"
        val = MagicMock()
        val.validate_or_raise.return_value = None

        orch = QueryOrchestrator(
            sql_generator=gen,
            sql_validator=val,
            result_validator=MagicMock(),
            schema_cache=cache,
            pools={"db1": MagicMock(), "db2": MagicMock()},
            resilience_config=ResilienceConfig(),
            validation_config=ValidationConfig(),
            sql_executors={"db1": exec_db1, "db2": exec_db2},
        )

        resp = await orch.execute_query(
            QueryRequest(question="get ids", database="db2", return_type=ReturnType.RESULT)
        )

        assert resp.success is True
        exec_db2.execute.assert_awaited_once()
        exec_db1.execute.assert_not_awaited()
        # The SQL must have been dispatched to the db2 executor
        assert exec_db2.execute.call_args.args[0] == "SELECT id FROM users;"
        assert resp.data is not None and resp.data.row_count == 1

    @pytest.mark.asyncio
    async def test_execute_query_rejects_unknown_database(self) -> None:
        orch = _orchestrator(sql_executors={"db1": AsyncMock()})
        resp = await orch.execute_query(
            QueryRequest(question="q", database="does_not_exist", return_type=ReturnType.SQL)
        )
        assert resp.success is False
        assert resp.error is not None
        assert resp.error.code == ErrorCode.DATABASE_ERROR.value
        assert "does_not_exist" in resp.error.message


class TestSecurityControls:
    """Verify configured table/column restrictions and EXPLAIN/write policy."""

    def _validator(self, **kw: object) -> SQLValidator:
        cfg = SecurityConfig(**kw)  # type: ignore[arg-type]
        return SQLValidator(
            config=cfg,
            blocked_tables=cfg.blocked_tables,
            blocked_columns=cfg.blocked_columns,
            allow_explain=cfg.allow_explain,
        )

    def test_blocked_table_rejected(self) -> None:
        v = self._validator(blocked_tables=["secrets"])
        with pytest.raises(SecurityViolationError):
            v.validate_or_raise("SELECT * FROM secrets")
        # Allowed table still passes
        v.validate_or_raise("SELECT * FROM users")

    def test_blocked_column_rejected(self) -> None:
        v = self._validator(blocked_columns=["password"])
        with pytest.raises(SecurityViolationError):
            v.validate_or_raise("SELECT password FROM users")
        # Unrelated column passes
        v.validate_or_raise("SELECT name FROM users")

    def test_allow_explain_policy(self) -> None:
        allowed = self._validator(allow_explain=True)
        allowed.validate_or_raise("EXPLAIN SELECT * FROM users")

        denied = self._validator(allow_explain=False)
        with pytest.raises(SecurityViolationError):
            denied.validate_or_raise("EXPLAIN SELECT * FROM users")

    def test_allow_write_operations_enables_writes(self) -> None:
        enabled = self._validator(allow_write_operations=True)
        # INSERT is now permitted
        enabled.validate_or_raise("INSERT INTO users (id) VALUES (1)")

        disabled = self._validator(allow_write_operations=False)
        with pytest.raises(SecurityViolationError):
            disabled.validate_or_raise("INSERT INTO users (id) VALUES (1)")


class TestRateLimiting:
    """Verify the rate limiter is applied to the query pipeline."""

    @asynccontextmanager
    async def _blocking_rate_limiter(self, *, timeout: float | None = None):  # noqa: ASYNC109
        """Async context manager that always rejects (simulates no free slots)."""
        raise TimeoutError("no free slots")
        yield  # pragma: no cover - unreachable

    @pytest.mark.asyncio
    async def test_rate_limit_exceeded_returns_error(self) -> None:
        schema = _schema()
        cache = MagicMock()
        cache.get.return_value = schema

        # A rate limiter that can never grant a slot for queries
        blocking = MagicMock()
        blocking.for_queries = self._blocking_rate_limiter
        blocking.query_limiter = MagicMock(max_concurrent=1, active_count=1)

        orch = _orchestrator(
            sql_executors={"test_db": AsyncMock()},
            rate_limiter=blocking,
        )

        resp = await orch.execute_query(
            QueryRequest(question="q", database="test_db", return_type=ReturnType.SQL)
        )

        assert resp.success is False
        assert resp.error is not None
        assert resp.error.code == ErrorCode.RATE_LIMIT_EXCEEDED.value
        # The request must never reach SQL generation when rejected
        orch.sql_generator.generate.assert_not_awaited()


class TestRetryBackoff:
    """Verify retries use exponential backoff between attempts."""

    @pytest.mark.asyncio
    async def test_exponential_backoff_between_retries(self) -> None:
        import pg_mcp.services.orchestrator as orch_mod

        schema = _schema()
        gen = AsyncMock()
        gen.generate.side_effect = ["SELECT * FROM bad;", "SELECT 1;"]
        val = MagicMock()
        val.validate_or_raise.side_effect = [
            SQLParseError("relation bad does not exist"),
            None,
        ]

        orch = QueryOrchestrator(
            sql_generator=gen,
            sql_validator=val,
            result_validator=MagicMock(),
            schema_cache=MagicMock(),
            pools={"test_db": MagicMock()},
            resilience_config=ResilienceConfig(
                max_retries=3, retry_delay=0.5, backoff_factor=2.0
            ),
            validation_config=ValidationConfig(),
            sql_executors={"test_db": AsyncMock()},
        )

        with patch.object(orch_mod.asyncio, "sleep", new=AsyncMock()) as sleep_mock:
            sql, _vr, _tokens = await orch._generate_sql_with_retry(
                question="q", schema=schema, request_id="r"
            )

        assert sql == "SELECT 1;"
        # First retry backs off by retry_delay * backoff_factor ** 0 = 0.5s
        sleep_mock.assert_awaited_once_with(0.5)


class TestObservabilityIntegration:
    """Verify metrics are recorded at the right points in the flow."""

    @pytest.mark.asyncio
    async def test_metrics_recorded_on_sql_only_success(self) -> None:
        schema = _schema()
        cache = MagicMock()
        cache.get.return_value = schema

        gen = AsyncMock()
        gen.generate.return_value = "SELECT 1;"
        val = MagicMock()
        val.validate_or_raise.return_value = None

        metrics = MagicMock()
        orch = QueryOrchestrator(
            sql_generator=gen,
            sql_validator=val,
            result_validator=MagicMock(),
            schema_cache=cache,
            pools={"test_db": MagicMock()},
            resilience_config=ResilienceConfig(),
            validation_config=ValidationConfig(),
            sql_executors={"test_db": AsyncMock()},
            metrics=metrics,
        )

        resp = await orch.execute_query(
            QueryRequest(question="q", database="test_db", return_type=ReturnType.SQL)
        )

        assert resp.success is True
        metrics.increment_query_request.assert_called_with("success", "test_db")
        metrics.increment_llm_call.assert_called_with("generate_sql")
        metrics.observe_llm_latency.assert_called_once()

    @pytest.mark.asyncio
    async def test_db_metrics_recorded_on_execution(self) -> None:
        schema = _schema()
        cache = MagicMock()
        cache.get.return_value = schema

        gen = AsyncMock()
        gen.generate.return_value = "SELECT id FROM users;"
        val = MagicMock()
        val.validate_or_raise.return_value = None

        metrics = MagicMock()
        orch = QueryOrchestrator(
            sql_generator=gen,
            sql_validator=val,
            result_validator=MagicMock(),
            schema_cache=cache,
            pools={"test_db": MagicMock()},
            resilience_config=ResilienceConfig(),
            validation_config=ValidationConfig(),
            sql_executors={"test_db": AsyncMock(execute=AsyncMock(return_value=([], 0)))},
            metrics=metrics,
        )

        resp = await orch.execute_query(
            QueryRequest(question="q", database="test_db", return_type=ReturnType.RESULT)
        )

        assert resp.success is True
        metrics.observe_db_query_duration.assert_called_once()
        metrics.set_db_connections_active.assert_called_once_with("test_db", ANY)


class TestSchemaCacheMaxSize:
    """Verify the configured cache max_size is enforced (FIFO eviction)."""

    @pytest.mark.asyncio
    async def test_max_size_evicts_oldest(self) -> None:
        dummy = DatabaseSchema(database_name="x", tables=[], version="15")
        with patch.object(
            SchemaIntrospector, "introspect", new=AsyncMock(return_value=dummy)
        ):
            cache = SchemaCache(CacheConfig(max_size=2, enabled=True, schema_ttl=3600))
            await cache.load("a", MagicMock())
            await cache.load("b", MagicMock())
            await cache.load("c", MagicMock())

            cached = set(cache.get_cached_databases())
            assert cached == {"b", "c"}
            assert "a" not in cached


class TestQueryResponseToDict:
    """Verify the single to_dict behaviour (no duplicate definitions)."""

    def test_tokens_used_always_present(self) -> None:
        resp = QueryResponse(
            success=True,
            generated_sql="SELECT 1",
            tokens_used=None,
            confidence=100,
        )
        result = resp.to_dict()
        assert "tokens_used" in result
        assert result["tokens_used"] == 0
        # None fields are omitted for a clean contract
        assert "error" not in result
        assert "data" not in result

    def test_failure_response_includes_tokens_used(self) -> None:
        from pg_mcp.models.query import ErrorDetail

        resp = QueryResponse(
            success=False,
            generated_sql=None,
            error=ErrorDetail(code=ErrorCode.SECURITY_VIOLATION, message="blocked"),
            tokens_used=None,
            confidence=0,
        )
        result = resp.to_dict()
        assert result["success"] is False
        assert "tokens_used" in result
        assert result["tokens_used"] == 0
        assert result["error"]["code"] == ErrorCode.SECURITY_VIOLATION.value


class TestOfflineStartup:
    """Verify the server can start without a database/LLM connection."""

    @pytest.mark.asyncio
    async def test_server_starts_offline_and_rejects_queries(self, monkeypatch) -> None:
        monkeypatch.setenv("PG_MCP_OFFLINE", "1")
        monkeypatch.setenv("PG_MCP_METRICS_ENABLED", "false")

        from pg_mcp.server import lifespan, mcp, query

        async with lifespan(mcp):
            result = await query("How many users?", database=None, return_type="result")

        assert result["success"] is False
        assert result["error"]["code"] == "OFFLINE_MODE"

    @pytest.mark.asyncio
    async def test_settings_constructs_without_openai_key(self) -> None:
        from pg_mcp.config.settings import Settings

        settings = Settings()
        # Empty key is accepted so the server can boot in offline mode
        assert settings.openai.api_key.get_secret_value() == ""
