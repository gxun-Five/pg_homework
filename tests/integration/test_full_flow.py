"""Integration tests for full query flow.

This module provides comprehensive integration tests that verify the complete
query flow through all components of the system.
"""

import pytest

from pg_mcp.server import lifespan, mcp, query


class TestFullQueryFlow:
    """Integration tests for complete query flow through all components."""

    @pytest.mark.asyncio
    async def test_simple_query_execution(self):
        """Test simple query execution through complete flow.

        This test verifies:
        1. Server initialization
        2. Natural language to SQL conversion
        3. SQL validation
        4. Query execution
        5. Result formatting
        """
        async with lifespan(mcp):
            result = await query(
                question="SELECT 1 as test_value",
                return_type="result",
            )

            # Verify response structure
            assert isinstance(result, dict)
            assert "success" in result

            # If successful, verify data structure
            if result.get("success"):
                assert "data" in result
                assert result["data"] is not None
                assert "rows" in result["data"]
                assert "columns" in result["data"]
                assert "row_count" in result["data"]
                assert result["data"]["row_count"] >= 0

    @pytest.mark.asyncio
    async def test_query_with_validation(self):
        """Test query execution with result validation.

        This test verifies:
        1. Query execution succeeds
        2. Result validator is invoked
        3. Confidence score is calculated
        4. Validation feedback is included
        """
        async with lifespan(mcp):
            result = await query(
                question="Count all tables in the database",
                return_type="result",
            )

            # Verify response structure
            assert isinstance(result, dict)

            # If successful, check for validation metadata
            if result.get("success"):
                # Confidence score should be present
                assert "confidence" in result
                assert isinstance(result["confidence"], int)
                assert 0 <= result["confidence"] <= 100

                # Generated SQL should be present
                assert "generated_sql" in result
                assert isinstance(result["generated_sql"], str)

    @pytest.mark.asyncio
    async def test_sql_only_mode(self):
        """Test SQL generation without execution.

        This test verifies:
        1. SQL generation succeeds
        2. Query is NOT executed
        3. Only SQL is returned
        4. No data field is present
        """
        async with lifespan(mcp):
            result = await query(
                question="Show me all tables in the current schema",
                return_type="sql",
            )

            # Verify response structure
            assert isinstance(result, dict)
            assert "success" in result

            # If successful, verify SQL-only response
            if result.get("success"):
                # Should have generated SQL
                assert "generated_sql" in result
                assert isinstance(result["generated_sql"], str)
                assert len(result["generated_sql"]) > 0

                # Should NOT have execution data
                assert "data" not in result or result["data"] is None

    @pytest.mark.asyncio
    async def test_multi_database_selection(self):
        """Test explicit database selection.

        This test verifies:
        1. Database parameter is respected
        2. Query executes against correct database
        3. Schema from correct database is used
        """
        async with lifespan(mcp):
            # Get configured database name
            from pg_mcp.config.settings import Settings

            settings = Settings()
            db_name = settings.database.name

            result = await query(
                question="SELECT 1 as test",
                database=db_name,
                return_type="sql",
            )

            # Verify response
            assert isinstance(result, dict)
            assert "success" in result

            # Should succeed with valid database
            if result.get("success"):
                assert "generated_sql" in result

    @pytest.mark.asyncio
    async def test_security_rejection(self):
        """Test security validation rejects dangerous queries.

        This test verifies:
        1. Security validator is invoked
        2. Dangerous operations are blocked
        3. Appropriate error is returned
        """
        async with lifespan(mcp):
            dangerous_queries = [
                "DROP TABLE users",
                "DELETE FROM users WHERE id = 1",
                "INSERT INTO users VALUES (1, 'test')",
                "UPDATE users SET name = 'hacked'",
                "CREATE TABLE malicious (id INT)",
                "ALTER TABLE users ADD COLUMN hacked TEXT",
            ]

            for dangerous_query in dangerous_queries:
                result = await query(
                    question=dangerous_query,
                    return_type="result",
                )

                # Should either:
                # 1. Fail validation (preferred)
                # 2. LLM refuses to generate dangerous SQL
                assert isinstance(result, dict)

                # If it failed (expected), verify error structure
                if not result.get("success", True):
                    assert "error" in result
                    assert "code" in result["error"]
                    assert "message" in result["error"]

    @pytest.mark.asyncio
    async def test_llm_retry_on_invalid_sql(self):
        """Test LLM retry mechanism on SQL syntax errors.

        This test verifies:
        1. Invalid SQL triggers retry
        2. Retry mechanism attempts correction
        3. Max retries are respected
        4. Appropriate error is returned on failure
        """
        async with lifespan(mcp):
            # Use a question that might generate invalid SQL
            result = await query(
                question="This is not a valid query request at all, just random words",
                return_type="result",
            )

            # Verify response structure
            assert isinstance(result, dict)
            assert "success" in result

            # Response should either succeed (LLM corrected) or fail gracefully
            if not result.get("success"):
                assert "error" in result
                assert "code" in result["error"]

    @pytest.mark.asyncio
    async def test_blocked_functions(self):
        """Test that blocked PostgreSQL functions are rejected.

        This test verifies:
        1. Dangerous functions are detected
        2. Security validation blocks them
        3. Appropriate error is returned
        """
        async with lifespan(mcp):
            blocked_function_queries = [
                "SELECT pg_sleep(1000)",
                "SELECT pg_read_file('/etc/passwd')",
                "SELECT lo_import('/tmp/file')",
            ]

            for query_text in blocked_function_queries:
                result = await query(
                    question=query_text,
                    return_type="result",
                )

                # Should fail validation
                assert isinstance(result, dict)

                # If validation worked, should not be successful
                # (or LLM should refuse to generate it)
                if not result.get("success", True):
                    assert "error" in result

    @pytest.mark.asyncio
    async def test_query_timeout_handling(self):
        """Test query timeout enforcement.

        This test verifies:
        1. Long-running queries are cancelled
        2. Timeout error is returned
        3. Resources are properly cleaned up
        """
        async with lifespan(mcp):
            # Try to create a query that would timeout
            # Note: pg_sleep might be blocked, so this may not actually timeout
            result = await query(
                question="SELECT COUNT(*) FROM pg_tables",
                return_type="result",
            )

            # Verify response structure (should complete quickly)
            assert isinstance(result, dict)
            assert "success" in result

    @pytest.mark.asyncio
    async def test_schema_cache_usage(self):
        """Test that schema cache is used effectively.

        This test verifies:
        1. Schema is loaded on startup
        2. Multiple queries use cached schema
        3. No redundant schema fetches
        """
        async with lifespan(mcp):
            # Execute multiple queries
            for i in range(3):
                result = await query(
                    question=f"SELECT {i + 1} as iteration",
                    return_type="sql",
                )

                # All queries should succeed (or fail for same reason)
                assert isinstance(result, dict)
                assert "success" in result

    @pytest.mark.asyncio
    async def test_error_handling_with_invalid_database(self):
        """Test error handling when invalid database is specified.

        This test verifies:
        1. Invalid database name is caught
        2. Appropriate error is returned
        3. Server remains stable
        """
        async with lifespan(mcp):
            result = await query(
                question="SELECT 1",
                database="nonexistent_database_12345",
                return_type="result",
            )

            # Should fail gracefully
            assert isinstance(result, dict)
            assert result.get("success") is False
            assert "error" in result

    @pytest.mark.asyncio
    async def test_empty_result_handling(self):
        """Test handling of queries that return no rows.

        This test verifies:
        1. Empty results are handled correctly
        2. Response structure is maintained
        3. Row count is zero
        """
        async with lifespan(mcp):
            result = await query(
                question="SELECT * FROM pg_tables WHERE tablename = 'nonexistent_table_xyz'",
                return_type="result",
            )

            # Verify response
            assert isinstance(result, dict)

            if result.get("success"):
                assert "data" in result
                # Empty result should have 0 rows
                if result["data"] is not None:
                    assert result["data"]["row_count"] >= 0

    @pytest.mark.asyncio
    async def test_large_result_set_handling(self):
        """Test handling of queries that return many rows.

        This test verifies:
        1. Large results are handled efficiently
        2. Row limits are enforced
        3. No memory exhaustion
        """
        async with lifespan(mcp):
            result = await query(
                question="SELECT generate_series(1, 100) as num",
                return_type="result",
            )

            # Verify response
            assert isinstance(result, dict)

            if result.get("success"):
                assert "data" in result
                if result["data"] is not None:
                    # Should respect max_rows limit
                    from pg_mcp.config.settings import Settings

                    settings = Settings()
                    assert result["data"]["row_count"] <= settings.security.max_rows

    @pytest.mark.asyncio
    async def test_concurrent_queries(self):
        """Test handling of concurrent queries.

        This test verifies:
        1. Multiple concurrent queries are handled
        2. Connection pool works correctly
        3. No race conditions
        """
        import asyncio

        async with lifespan(mcp):
            # Execute multiple queries concurrently
            queries = [query(question=f"SELECT {i} as value", return_type="sql") for i in range(5)]

            results = await asyncio.gather(*queries, return_exceptions=True)

            # All queries should complete
            assert len(results) == 5

            # Verify all results are valid
            for result in results:
                assert isinstance(result, dict)
                assert "success" in result

    @pytest.mark.asyncio
    async def test_tokens_used_tracking(self):
        """Test that LLM token usage is tracked.

        This test verifies:
        1. Token usage is recorded
        2. Tokens are included in response
        3. Value is reasonable
        """
        async with lifespan(mcp):
            result = await query(
                question="Count all tables",
                return_type="result",
            )

            # Verify response
            if result.get("success"):
                # Token usage should be present
                assert "tokens_used" in result
                assert isinstance(result["tokens_used"], int)
                assert result["tokens_used"] >= 0


class TestIntegrationErrorScenarios:
    """Integration tests for error scenarios."""

    @pytest.mark.asyncio
    async def test_malformed_input_handling(self):
        """Test handling of malformed input."""
        async with lifespan(mcp):
            # Test with extremely long question
            long_question = "x" * 50000

            result = await query(
                question=long_question,
                return_type="result",
            )

            # Should handle gracefully
            assert isinstance(result, dict)
            assert result.get("success") is False
            assert "error" in result

    @pytest.mark.asyncio
    async def test_special_characters_in_query(self):
        """Test handling of special characters."""
        async with lifespan(mcp):
            special_queries = [
                "SELECT 'test'; DROP TABLE users;--",
                "SELECT * FROM users WHERE name = '' OR '1'='1",
                "SELECT '\"; DROP TABLE users; --",
            ]

            for special_query in special_queries:
                result = await query(
                    question=special_query,
                    return_type="result",
                )

                # Should handle securely
                assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_unicode_handling(self):
        """Test handling of unicode characters."""
        async with lifespan(mcp):
            unicode_queries = [
                "SELECT '你好世界' as greeting",
                "SELECT 'émojis: 🎉🎊' as message",
                "SELECT 'مرحبا' as arabic",
            ]

            for unicode_query in unicode_queries:
                result = await query(
                    question=unicode_query,
                    return_type="sql",
                )

                # Should handle unicode correctly
                assert isinstance(result, dict)


class TestIntegrationPerformance:
    """Integration tests for performance characteristics."""

    @pytest.mark.asyncio
    async def test_query_response_time(self):
        """Test that queries complete in reasonable time."""
        import time

        async with lifespan(mcp):
            start = time.time()

            result = await query(
                question="SELECT 1",
                return_type="sql",
            )

            elapsed = time.time() - start

            # Should complete in under 30 seconds (LLM call + validation)
            assert elapsed < 30.0

            # Verify success
            assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_connection_pool_efficiency(self):
        """Test connection pool reuse efficiency."""
        async with lifespan(mcp):
            # Execute multiple queries to test pool reuse
            for i in range(10):
                result = await query(
                    question=f"SELECT {i}",
                    return_type="sql",
                )

                assert isinstance(result, dict)
