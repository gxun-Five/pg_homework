"""Query orchestrator for coordinating the complete query flow.

This module provides the QueryOrchestrator class that coordinates all components
of the query processing pipeline: SQL generation, validation, execution, and result
validation. It implements retry logic with exponential backoff, circuit breaker
pattern for fault tolerance, rate limiting, metrics collection, request tracing,
and comprehensive error handling.

Multi-database support: the orchestrator holds one SQLExecutor per configured
database and selects the correct executor for the resolved target database, so a
request is always executed against the database the caller asked for.
"""

import asyncio
import contextlib
import logging
import uuid
from typing import Any

from asyncpg import Pool

from pg_mcp.cache.schema_cache import SchemaCache
from pg_mcp.config.settings import ResilienceConfig, ValidationConfig
from pg_mcp.models.errors import (
    DatabaseError,
    ErrorCode,
    LLMError,
    PgMcpError,
    RateLimitExceededError,
    SchemaLoadError,
    SecurityViolationError,
    SQLParseError,
    ValidationError,
)
from pg_mcp.models.query import (
    ErrorDetail,
    QueryRequest,
    QueryResponse,
    QueryResult,
    ReturnType,
    ValidationResult,
)
from pg_mcp.observability.metrics import MetricsCollector
from pg_mcp.observability.tracing import clear_request_id, set_request_id
from pg_mcp.resilience.circuit_breaker import CircuitBreaker
from pg_mcp.resilience.rate_limiter import MultiRateLimiter
from pg_mcp.services.result_validator import ResultValidator
from pg_mcp.services.sql_executor import SQLExecutor
from pg_mcp.services.sql_generator import SQLGenerator
from pg_mcp.services.sql_validator import SQLValidator

logger = logging.getLogger(__name__)


class QueryOrchestrator:
    """Orchestrates the complete query processing pipeline.

    This class coordinates SQL generation, validation, execution, and result
    validation. It implements retry logic with exponential backoff, circuit
    breaker pattern for fault tolerance, rate limiting, metrics collection, and
    request tracing.

    Example:
        >>> orchestrator = QueryOrchestrator(
        ...     sql_generator=generator,
        ...     sql_validator=validator,
        ...     sql_executors={"mydb": executor},
        ...     result_validator=result_validator,
        ...     schema_cache=cache,
        ...     pools={"mydb": pool},
        ...     resilience_config=resilience_config,
        ...     validation_config=validation_config,
        ... )
        >>> response = await orchestrator.execute_query(QueryRequest(
        ...     question="How many users?",
        ...     database="mydb"
        ... ))
    """

    def __init__(
        self,
        sql_generator: SQLGenerator,
        sql_validator: SQLValidator,
        result_validator: ResultValidator,
        schema_cache: SchemaCache,
        pools: dict[str, Pool],
        resilience_config: ResilienceConfig,
        validation_config: ValidationConfig,
        sql_executor: SQLExecutor | None = None,
        sql_executors: dict[str, SQLExecutor] | None = None,
        rate_limiter: MultiRateLimiter | None = None,
        metrics: MetricsCollector | None = None,
    ) -> None:
        """Initialize query orchestrator.

        Args:
            sql_generator: SQL generation service.
            sql_validator: SQL validation service.
            sql_executor: Single executor (fallback, broadcast to all pools).
            sql_executors: Dictionary mapping database names to executors.
                Preferred over ``sql_executor`` for true multi-database routing.
            result_validator: Result validation service.
            schema_cache: Schema cache instance.
            pools: Dictionary mapping database names to connection pools.
            resilience_config: Resilience configuration for retries and circuit breaker.
            validation_config: Validation configuration including thresholds.
            rate_limiter: Optional rate limiter applied to query execution.
            metrics: Optional metrics collector integrated into the request flow.
        """
        self.sql_generator = sql_generator
        self.sql_validator = sql_validator
        self.result_validator = result_validator
        self.schema_cache = schema_cache
        self.pools = pools
        self.resilience_config = resilience_config
        self.validation_config = validation_config
        self.rate_limiter = rate_limiter
        self.metrics = metrics

        # Multi-database executor selection. Prefer the explicit per-database map;
        # otherwise broadcast a single executor to every configured database (used
        # by tests and single-database deployments). This guarantees that a request
        # is always executed against the database the caller resolved to.
        if sql_executors:
            self.sql_executors = sql_executors
        elif sql_executor is not None:
            self.sql_executors = dict.fromkeys(pools, sql_executor)
        else:
            raise ValueError("Either sql_executor or sql_executors must be provided")

        # Create circuit breaker for LLM calls
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=resilience_config.circuit_breaker_threshold,
            recovery_timeout=resilience_config.circuit_breaker_timeout,
        )

    async def execute_query(self, request: QueryRequest) -> QueryResponse:
        """Execute complete query flow from question to results.

        This method orchestrates the entire pipeline:
        1. Generate request_id and establish tracing context
        2. Enforce configured question length limit
        3. Resolve and validate database name (and select its executor)
        4. Acquire a rate-limit slot for the query
        5. Load schema from cache
        6. Generate and validate SQL with retry + exponential backoff
        7. Execute SQL on the correct database (if return_type == RESULT)
        8. Validate results (optional)
        9. Record metrics and return structured response

        Args:
            request: Query request containing question and parameters.

        Returns:
            QueryResponse: Complete response with SQL, results, or error information.
        """
        request_id = str(uuid.uuid4())
        # Establish tracing context so all downstream logs carry the request_id
        set_request_id(request_id)
        logger.info(
            "Starting query execution",
            extra={"request_id": request_id, "question": request.question[:100]},
        )

        database_name: str | None = None
        rate_cm = None

        try:
            # Enforce configured question length limit
            if len(request.question) > self.validation_config.max_question_length:
                raise ValidationError(
                    message=(
                        f"Question exceeds maximum length of "
                        f"{self.validation_config.max_question_length} characters"
                    ),
                    details={
                        "length": len(request.question),
                        "max_length": self.validation_config.max_question_length,
                    },
                )

            # Step 1: Resolve database name (and implicitly its executor)
            database_name = self._resolve_database(request.database)
            logger.debug(
                "Resolved database",
                extra={"request_id": request_id, "database": database_name},
            )

            # Step 2: Acquire rate-limit slot for concurrent query control
            if self.rate_limiter is not None:
                try:
                    rate_cm = self.rate_limiter.for_queries(
                        timeout=self.resilience_config.rate_limit_timeout
                    )
                    await rate_cm.__aenter__()
                except TimeoutError as e:
                    raise RateLimitExceededError(
                        message="Rate limit exceeded: too many concurrent queries",
                        details={
                            "limit": self.rate_limiter.query_limiter.max_concurrent,
                            "active": self.rate_limiter.query_limiter.active_count,
                        },
                    ) from e

            # Step 3: Get schema from cache
            schema = self.schema_cache.get(database_name)
            if schema is None:
                pool = self.pools.get(database_name)
                if pool is None:
                    raise DatabaseError(
                        message=f"No connection pool available for database '{database_name}'",
                        details={"database": database_name},
                    )
                try:
                    schema = await self.schema_cache.load(database_name, pool)
                except Exception as e:
                    raise SchemaLoadError(
                        message=f"Failed to load schema for database '{database_name}': {e!s}",
                        details={"database": database_name, "error": str(e)},
                    ) from e

            logger.debug(
                "Schema loaded",
                extra={
                    "request_id": request_id,
                    "database": database_name,
                    "tables": len(schema.tables),
                },
            )

            # Step 4: Generate and validate SQL with retry logic
            generated_sql, validation_result, tokens_used = await self._generate_sql_with_retry(
                question=request.question,
                schema=schema,
                request_id=request_id,
            )

            # Step 5: If return_type is SQL, return early
            if request.return_type == ReturnType.SQL:
                logger.info(
                    "Returning SQL only",
                    extra={"request_id": request_id, "sql_length": len(generated_sql)},
                )
                self._record_query_metric("success", database_name)
                return QueryResponse(
                    success=True,
                    generated_sql=generated_sql,
                    validation=validation_result,
                    data=None,
                    error=None,
                    confidence=100,
                    tokens_used=tokens_used,
                )

            # Step 6: Execute SQL on the resolved database's executor
            logger.debug("Executing SQL", extra={"request_id": request_id})
            start_time = self._get_current_time_ms()

            executor = self.sql_executors[database_name]
            results, total_count = await executor.execute(generated_sql)

            execution_time_ms = self._get_current_time_ms() - start_time
            self._record_db_metrics(database_name, execution_time_ms)
            logger.info(
                "SQL executed successfully",
                extra={
                    "request_id": request_id,
                    "database": database_name,
                    "row_count": total_count,
                    "execution_time_ms": execution_time_ms,
                },
            )

            # Step 7: Validate results (non-blocking, failures don't fail the request)
            result_confidence = await self._validate_results_safely(
                question=request.question,
                sql=generated_sql,
                results=results,
                row_count=total_count,
                request_id=request_id,
            )

            # Step 8: Build successful response
            query_result = QueryResult(
                columns=list(results[0].keys()) if results else [],
                rows=results,
                row_count=len(results),  # Limited row count (after max_rows applied)
                execution_time_ms=execution_time_ms,
            )

            self._record_query_metric("success", database_name)
            return QueryResponse(
                success=True,
                generated_sql=generated_sql,
                validation=validation_result,
                data=query_result,
                error=None,
                confidence=result_confidence,
                tokens_used=tokens_used,
            )

        except PgMcpError as e:
            # Handle known application errors
            logger.warning(
                "Query execution failed with known error",
                extra={
                    "request_id": request_id,
                    "error_code": e.code,
                    "error_message": str(e),
                },
            )
            self._record_query_metric("error", database_name, e)
            return self._build_error_response(request_id, e)
        except Exception as e:
            # Handle unexpected errors
            logger.exception(
                "Query execution failed with unexpected error",
                extra={"request_id": request_id},
            )
            self._record_query_metric("error", database_name)
            return QueryResponse(
                success=False,
                generated_sql=None,
                validation=None,
                data=None,
                error=ErrorDetail(
                    code=ErrorCode.INTERNAL_ERROR.value,
                    message=f"Internal server error: {e!s}",
                    details={"error_type": type(e).__name__},
                ),
                confidence=0,
                tokens_used=None,
            )
        finally:
            if rate_cm is not None:
                await rate_cm.__aexit__(None, None, None)
            # Clear tracing context
            clear_request_id()

    def _resolve_database(self, database: str | None) -> str:
        """Resolve database name from request or auto-select.

        If database is specified, validate it exists.
        If not specified and only one database available, auto-select it.

        Args:
            database: Database name from request (optional).

        Returns:
            str: Resolved database name.

        Raises:
            DatabaseError: If database is invalid or cannot be auto-selected.
        """
        if database is not None:
            # Validate specified database exists (and therefore has an executor)
            if database not in self.sql_executors:
                raise DatabaseError(
                    message=f"Database '{database}' not found",
                    details={
                        "requested_database": database,
                        "available_databases": list(self.sql_executors.keys()),
                    },
                )
            return database

        # Auto-select if only one database available
        available_dbs = list(self.sql_executors.keys())
        if len(available_dbs) == 0:
            raise DatabaseError(
                message="No databases configured",
                details={},
            )
        if len(available_dbs) == 1:
            return available_dbs[0]

        # Multiple databases, must specify
        raise DatabaseError(
            message="Multiple databases available, please specify which to query",
            details={"available_databases": available_dbs},
        )

    async def _generate_sql_with_retry(
        self,
        question: str,
        schema: Any,
        request_id: str,
    ) -> tuple[str, ValidationResult, int | None]:
        """Generate and validate SQL with retry logic and exponential backoff.

        This method implements a retry loop that:
        1. Checks circuit breaker state
        2. Generates SQL using LLM (timed + metrics recorded)
        3. Validates the generated SQL
        4. On validation failure, retries with error feedback and exponential backoff
        5. Records success/failure to circuit breaker and metrics

        Args:
            question: User's natural language question.
            schema: Database schema for context.
            request_id: Request ID for tracking.

        Returns:
            tuple: (generated_sql, validation_result, tokens_used)

        Raises:
            LLMError: If circuit breaker is open or generation fails.
            SecurityViolationError: If SQL fails validation after all retries.
            SQLParseError: If SQL cannot be parsed.
        """
        # Check circuit breaker
        if not self.circuit_breaker.allow_request():
            self._record_sql_rejected("circuit_open")
            raise LLMError(
                message="SQL generation service is temporarily unavailable (circuit breaker open)",
                details={
                    "circuit_state": self.circuit_breaker.state,
                    "failure_count": self.circuit_breaker.failure_count,
                },
            )

        previous_sql: str | None = None
        error_feedback: str | None = None
        max_retries = self.resilience_config.max_retries
        tokens_used: int | None = None

        for attempt in range(max_retries + 1):
            try:
                logger.debug(
                    "Generating SQL",
                    extra={
                        "request_id": request_id,
                        "attempt": attempt + 1,
                        "max_retries": max_retries + 1,
                    },
                )

                # Generate SQL (timed for latency metrics)
                gen_start = self._get_current_time_ms()
                generated_sql = await self.sql_generator.generate(
                    question=question,
                    schema=schema,
                    previous_attempt=previous_sql,
                    error_feedback=error_feedback,
                )
                gen_duration_ms = self._get_current_time_ms() - gen_start
                self._record_llm_metric("generate_sql", gen_duration_ms)

                logger.debug(
                    "SQL generated",
                    extra={
                        "request_id": request_id,
                        "sql_length": len(generated_sql),
                    },
                )

                # Validate SQL
                try:
                    self.sql_validator.validate_or_raise(generated_sql)
                except (SecurityViolationError, SQLParseError) as validation_error:
                    if attempt < max_retries:
                        # Record as failure and retry with feedback + backoff
                        self._record_sql_rejected("validation_failed")
                        logger.warning(
                            "SQL validation failed, retrying with feedback",
                            extra={
                                "request_id": request_id,
                                "attempt": attempt + 1,
                                "error": str(validation_error),
                            },
                        )
                        previous_sql = generated_sql
                        error_feedback = str(validation_error)
                        # Exponential backoff before the next attempt
                        if self.resilience_config.retry_delay > 0:
                            delay = self.resilience_config.retry_delay * (
                                self.resilience_config.backoff_factor**attempt
                            )
                            logger.debug(
                                "Backing off before retry",
                                extra={"request_id": request_id, "delay_seconds": delay},
                            )
                            await asyncio.sleep(delay)
                        continue
                    else:
                        # Out of retries, record failure and raise
                        self.circuit_breaker.record_failure()
                        self._record_sql_rejected("validation_failed")
                        logger.error(
                            "SQL validation failed after all retries",
                            extra={
                                "request_id": request_id,
                                "attempts": attempt + 1,
                                "error": str(validation_error),
                            },
                        )
                        raise

                # Validation successful
                self.circuit_breaker.record_success()
                logger.info(
                    "SQL generated and validated successfully",
                    extra={
                        "request_id": request_id,
                        "attempts": attempt + 1,
                    },
                )

                # Build validation result
                validation_result = ValidationResult(
                    is_valid=True,
                    is_select=True,
                    allows_data_modification=False,
                    uses_blocked_functions=[],
                    error_message=None,
                )

                return generated_sql, validation_result, tokens_used

            except (LLMError, SecurityViolationError, SQLParseError):
                # Re-raise known errors
                raise
            except Exception as e:
                # Unexpected error during generation
                self.circuit_breaker.record_failure()
                logger.exception(
                    "Unexpected error during SQL generation",
                    extra={"request_id": request_id},
                )
                raise LLMError(
                    message=f"SQL generation failed unexpectedly: {e!s}",
                    details={"error_type": type(e).__name__},
                ) from e

        # Should not reach here, but just in case
        self.circuit_breaker.record_failure()
        raise LLMError(
            message="SQL generation failed after all retry attempts",
            details={"max_retries": max_retries},
        )

    async def _validate_results_safely(
        self,
        question: str,
        sql: str,
        results: list[dict[str, Any]],
        row_count: int,
        request_id: str,
    ) -> int:
        """Validate query results with error handling (non-blocking).

        This method attempts to validate results using LLM, but failures
        don't cause the overall query to fail. Returns a confidence score.

        Args:
            question: User's original question.
            sql: Generated SQL query.
            results: Query results.
            row_count: Total row count.
            request_id: Request ID for tracking.

        Returns:
            int: Confidence score (0-100). Returns 100 if validation disabled/fails.
        """
        if not self.validation_config.enabled:
            return 100

        try:
            logger.debug(
                "Validating results",
                extra={"request_id": request_id},
            )

            validation_result = await self.result_validator.validate(
                question=question,
                sql=sql,
                results=results,
                row_count=row_count,
            )

            logger.info(
                "Result validation completed",
                extra={
                    "request_id": request_id,
                    "confidence": validation_result.confidence,
                    "is_acceptable": validation_result.is_acceptable,
                },
            )

            return validation_result.confidence

        except Exception as e:
            # Log but don't fail the query
            logger.warning(
                "Result validation failed, continuing with default confidence",
                extra={
                    "request_id": request_id,
                    "error": str(e),
                },
            )
            return 100  # Default to high confidence if validation fails

    # ------------------------------------------------------------------
    # Observability helpers
    # ------------------------------------------------------------------
    def _record_query_metric(
        self, status: str, database: str | None, error: PgMcpError | None = None
    ) -> None:
        """Record a query-request metric if a collector is configured."""
        if self.metrics is None:
            return
        db = database or "unknown"
        self.metrics.increment_query_request(status, db)
        if status == "error" and error is not None and error.code == ErrorCode.SECURITY_VIOLATION:
            self._record_sql_rejected("security_violation")

    def _record_sql_rejected(self, reason: str) -> None:
        """Record a SQL-rejected metric if a collector is configured."""
        if self.metrics is None:
            return
        self.metrics.increment_sql_rejected(reason)

    def _record_llm_metric(self, operation: str, duration_ms: float) -> None:
        """Record LLM call count and latency if a collector is configured."""
        if self.metrics is None:
            return
        self.metrics.increment_llm_call(operation)
        self.metrics.observe_llm_latency(operation, duration_ms / 1000.0)

    def _record_db_metrics(self, database_name: str, duration_ms: float) -> None:
        """Record database query duration and active connection count."""
        if self.metrics is None:
            return
        self.metrics.observe_db_query_duration(duration_ms / 1000.0)
        pool = self.pools.get(database_name)
        if pool is not None:
            # Connection pool size introspection is best-effort
            with contextlib.suppress(Exception):
                self.metrics.set_db_connections_active(database_name, pool.get_size())

    @staticmethod
    def _build_error_response(request_id: str, error: PgMcpError) -> QueryResponse:
        """Build a QueryResponse from a known PgMcpError."""
        return QueryResponse(
            success=False,
            generated_sql=None,
            validation=None,
            data=None,
            error=ErrorDetail(
                code=error.code.value,
                message=error.message,
                details=error.details,
            ),
            confidence=0,
            tokens_used=None,
        )

    @staticmethod
    def _get_current_time_ms() -> float:
        """Get current time in milliseconds."""
        import time

        return time.time() * 1000
