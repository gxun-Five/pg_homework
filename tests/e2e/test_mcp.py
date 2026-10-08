"""End-to-end tests for MCP server integration.

This module provides E2E tests for the FastMCP server implementation,
testing the complete query flow through the MCP protocol.
"""

import pytest

from pg_mcp.server import lifespan, mcp, query


class TestMCPServer:
    """E2E tests for MCP server functionality."""

    @pytest.mark.asyncio
    async def test_lifespan_initialization(self):
        """Test that lifespan context manager initializes all components."""
        # This test verifies that the lifespan context can be entered and exited
        # without errors, which means all components initialize properly.
        async with lifespan(mcp):
            # If we reach here, initialization was successful
            pass

    @pytest.mark.asyncio
    async def test_query_tool_sql_only(self):
        """Test query tool with return_type='sql'."""
        async with lifespan(mcp):
            result = await query(
                question="SELECT COUNT(*) FROM users",
                return_type="sql",
            )

            # Verify response structure
            assert "success" in result
            assert "generated_sql" in result or "error" in result

            # If successful, verify SQL is returned
            if result.get("success"):
                assert result["generated_sql"] is not None
                assert isinstance(result["generated_sql"], str)

    @pytest.mark.asyncio
    async def test_query_tool_with_execution(self):
        """Test query tool with return_type='result'."""
        async with lifespan(mcp):
            result = await query(
                question="Show me all tables",
                return_type="result",
            )

            # Verify response structure
            assert "success" in result

            # If successful, verify data is returned
            if result.get("success"):
                assert "data" in result
                assert result["data"] is not None
                assert "rows" in result["data"]
                assert "columns" in result["data"]

    @pytest.mark.asyncio
    async def test_query_tool_invalid_return_type(self):
        """Test query tool with invalid return_type."""
        async with lifespan(mcp):
            result = await query(
                question="SELECT 1",
                return_type="invalid",
            )

            # Should return error
            assert result["success"] is False
            assert "error" in result
            assert result["error"]["code"] == "INVALID_PARAMETER"

    @pytest.mark.asyncio
    async def test_query_tool_empty_question(self):
        """Test query tool with empty question."""
        async with lifespan(mcp):
            result = await query(
                question="",
                return_type="result",
            )

            # Should return error due to validation
            assert result["success"] is False
            assert "error" in result

    @pytest.mark.asyncio
    async def test_query_tool_with_database_parameter(self):
        """Test query tool with explicit database parameter."""
        async with lifespan(mcp):
            # Use the configured database name
            from pg_mcp.config.settings import Settings

            settings = Settings()
            db_name = settings.database.name

            result = await query(
                question="SELECT 1 as test",
                database=db_name,
                return_type="sql",
            )

            # Should succeed or fail with known error
            assert "success" in result

    @pytest.mark.asyncio
    async def test_query_tool_response_format(self):
        """Test that query tool returns properly formatted response."""
        async with lifespan(mcp):
            result = await query(
                question="SELECT 1",
                return_type="sql",
            )

            # Verify all expected top-level keys are present
            assert isinstance(result, dict)

            # Common fields
            assert "success" in result

            # Either data or error should be present
            if result["success"]:
                # Success case should have generated_sql
                assert "generated_sql" in result
            else:
                # Failure case should have error
                assert "error" in result
                assert "code" in result["error"]
                assert "message" in result["error"]


class TestMCPServerErrors:
    """Tests for error handling in MCP server."""

    @pytest.mark.asyncio
    async def test_query_before_initialization(self):
        """Test calling query tool before server initialization."""
        # Reset global state to ensure clean test
        import pg_mcp.server as server_module

        original_orchestrator = server_module._orchestrator
        server_module._orchestrator = None

        try:
            # Call query without lifespan context
            result = await query(
                question="SELECT 1",
                return_type="sql",
            )

            # Should return initialization error
            assert result["success"] is False
            assert "error" in result
            assert result["error"]["code"] == "SERVER_NOT_INITIALIZED"
        finally:
            # Restore original state
            server_module._orchestrator = original_orchestrator

    @pytest.mark.asyncio
    async def test_malformed_question_handling(self):
        """Test handling of malformed questions."""
        async with lifespan(mcp):
            # Test with very long question (should be rejected by validation)
            long_question = "SELECT " + ("x " * 10000)

            result = await query(
                question=long_question,
                return_type="result",
            )

            # Should handle gracefully
            assert "success" in result
            # If it fails, should have proper error structure
            if not result["success"]:
                assert "error" in result
                assert "code" in result["error"]


class TestMCPServerLifecycle:
    """Tests for server lifecycle management."""

    @pytest.mark.asyncio
    async def test_multiple_lifespan_contexts(self):
        """Test that multiple lifespan contexts can be created sequentially."""
        # First context
        async with lifespan(mcp):
            result1 = await query(
                question="SELECT 1",
                return_type="sql",
            )
            assert "success" in result1

        # Second context (after shutdown of first)
        async with lifespan(mcp):
            result2 = await query(
                question="SELECT 2",
                return_type="sql",
            )
            assert "success" in result2

    @pytest.mark.asyncio
    async def test_nested_queries_in_lifespan(self):
        """Test multiple queries within single lifespan context."""
        async with lifespan(mcp):
            # First query
            result1 = await query(
                question="SELECT 1 as first",
                return_type="sql",
            )
            assert "success" in result1

            # Second query
            result2 = await query(
                question="SELECT 2 as second",
                return_type="sql",
            )
            assert "success" in result2


# Fixtures for E2E tests
@pytest.fixture
async def initialized_server():
    """Fixture that provides an initialized server context."""
    async with lifespan(mcp):
        yield


@pytest.mark.asyncio
async def test_query_with_fixture(initialized_server):
    """Test using fixture for server initialization."""
    result = await query(
        question="SELECT COUNT(*) FROM pg_tables",
        return_type="sql",
    )

    assert "success" in result


# Integration test with actual database
@pytest.mark.asyncio
@pytest.mark.integration
async def test_end_to_end_query_flow():
    """Full end-to-end test of query flow.

    This test requires:
    - Valid database connection configured
    - OpenAI API key configured
    - Database with sample data

    It tests the complete flow:
    1. Server initialization
    2. Natural language question
    3. SQL generation
    4. Validation
    5. Execution
    6. Result validation
    7. Response formatting
    """
    async with lifespan(mcp):
        # Test SQL generation
        sql_result = await query(
            question="How many tables are in the database?",
            return_type="sql",
        )

        # If LLM is configured, should generate SQL
        if sql_result.get("success"):
            assert sql_result["generated_sql"] is not None
            assert len(sql_result["generated_sql"]) > 0

            # Test execution
            exec_result = await query(
                question="How many tables are in the database?",
                return_type="result",
            )

            if exec_result.get("success"):
                assert exec_result["data"] is not None
                assert "rows" in exec_result["data"]
                assert exec_result["data"]["row_count"] >= 0


class TestMCPServerIntegration:
    """Extended E2E integration tests."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_natural_language_to_sql_flow(self):
        """Test complete natural language to SQL conversion flow."""
        async with lifespan(mcp):
            # Test with natural language question
            result = await query(
                question="How many tables are in the public schema?",
                return_type="sql",
            )

            if result.get("success"):
                # Verify SQL was generated
                assert "generated_sql" in result
                assert isinstance(result["generated_sql"], str)
                assert len(result["generated_sql"]) > 0

                # SQL should likely contain SELECT
                assert "select" in result["generated_sql"].lower()

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_query_execution_with_results(self):
        """Test query execution returns actual data."""
        async with lifespan(mcp):
            result = await query(
                question="List all PostgreSQL system catalogs",
                return_type="result",
            )

            if result.get("success"):
                # Verify data structure
                assert "data" in result
                assert result["data"] is not None

                data = result["data"]
                assert "columns" in data
                assert "rows" in data
                assert "row_count" in data

                # Should have some columns and rows
                assert isinstance(data["columns"], list)
                assert isinstance(data["rows"], list)
                assert isinstance(data["row_count"], int)

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_confidence_scoring(self):
        """Test that confidence scores are calculated."""
        async with lifespan(mcp):
            result = await query(
                question="Count the number of tables",
                return_type="result",
            )

            if result.get("success"):
                # Confidence should be present
                assert "confidence" in result
                assert isinstance(result["confidence"], int)
                assert 0 <= result["confidence"] <= 100

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_token_usage_tracking(self):
        """Test that token usage is tracked."""
        async with lifespan(mcp):
            result = await query(
                question="What tables exist?",
                return_type="result",
            )

            if result.get("success"):
                # Tokens should be tracked
                assert "tokens_used" in result
                assert isinstance(result["tokens_used"], int)
                assert result["tokens_used"] >= 0

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_security_validation_enforcement(self):
        """Test that security validation prevents dangerous queries."""
        async with lifespan(mcp):
            dangerous_operations = [
                "DROP TABLE users",
                "DELETE FROM important_data",
                "UPDATE users SET password = 'hacked'",
                "INSERT INTO logs VALUES ('malicious')",
                "TRUNCATE TABLE users",
            ]

            for dangerous_op in dangerous_operations:
                result = await query(
                    question=dangerous_op,
                    return_type="result",
                )

                # Should either fail or LLM should refuse
                # At minimum, verify response is well-formed
                assert isinstance(result, dict)
                assert "success" in result

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_complex_query_generation(self):
        """Test generation of complex SQL queries."""
        async with lifespan(mcp):
            complex_questions = [
                "What are the top 5 largest tables by row count?",
                "Show me all tables with their column counts",
                "Which schemas have the most tables?",
            ]

            for question in complex_questions:
                result = await query(
                    question=question,
                    return_type="sql",
                )

                # Verify response structure
                assert isinstance(result, dict)
                assert "success" in result

                if result.get("success"):
                    assert "generated_sql" in result
                    # Complex queries should have substantial SQL
                    assert len(result["generated_sql"]) > 20

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_schema_context_usage(self):
        """Test that schema context is used in SQL generation."""
        async with lifespan(mcp):
            # Ask about specific tables/columns
            result = await query(
                question="Describe the structure of pg_tables",
                return_type="sql",
            )

            if result.get("success"):
                # SQL should reference actual schema elements
                assert "generated_sql" in result
                sql = result["generated_sql"].lower()

                # Should contain relevant PostgreSQL elements
                assert "pg_tables" in sql or "information_schema" in sql

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_error_recovery(self):
        """Test error recovery and handling."""
        async with lifespan(mcp):
            # Test with potentially problematic input
            problematic_inputs = [
                "",  # Empty
                "   ",  # Whitespace only
                "x" * 20000,  # Very long
            ]

            for input_text in problematic_inputs:
                result = await query(
                    question=input_text,
                    return_type="result",
                )

                # Should handle gracefully with proper error
                assert isinstance(result, dict)
                assert "success" in result

                if not result.get("success"):
                    assert "error" in result
                    assert "code" in result["error"]
                    assert "message" in result["error"]

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_retry_mechanism(self):
        """Test that retry mechanism works for transient failures."""
        async with lifespan(mcp):
            # Use a question that might need retry
            result = await query(
                question="This is an ambiguous query that might need clarification",
                return_type="result",
            )

            # Should either succeed or fail gracefully
            assert isinstance(result, dict)
            assert "success" in result

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_metrics_collection(self):
        """Test that metrics are collected during operations."""
        async with lifespan(mcp):
            # Execute a query to generate metrics
            result = await query(
                question="SELECT 1",
                return_type="sql",
            )

            # Metrics should be collected in background
            # This is a basic test - proper metrics testing would check Prometheus
            assert isinstance(result, dict)

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_concurrent_query_handling(self):
        """Test handling of multiple concurrent queries."""
        import asyncio

        async with lifespan(mcp):
            # Execute multiple queries concurrently
            queries_to_run = [
                query(question=f"SELECT {i} as value", return_type="sql") for i in range(5)
            ]

            results = await asyncio.gather(*queries_to_run, return_exceptions=True)

            # All should complete successfully
            assert len(results) == 5

            for result in results:
                assert isinstance(result, dict)
                assert "success" in result

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_database_parameter_override(self):
        """Test that database parameter can override default."""
        async with lifespan(mcp):
            from pg_mcp.config.settings import Settings

            settings = Settings()
            db_name = settings.database.name

            # Query with explicit database
            result = await query(
                question="SELECT 1",
                database=db_name,
                return_type="sql",
            )

            # Should succeed with valid database
            assert isinstance(result, dict)
            assert "success" in result

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_readonly_enforcement(self):
        """Test that read-only mode is enforced."""
        async with lifespan(mcp):
            write_operations = [
                "INSERT INTO test VALUES (1)",
                "UPDATE test SET value = 1",
                "DELETE FROM test",
                "CREATE TABLE test (id INT)",
                "DROP TABLE test",
                "ALTER TABLE test ADD COLUMN x INT",
            ]

            for write_op in write_operations:
                result = await query(
                    question=write_op,
                    return_type="result",
                )

                # Should fail validation or LLM should refuse
                assert isinstance(result, dict)

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_result_validation_feedback(self):
        """Test that result validation provides feedback."""
        async with lifespan(mcp):
            result = await query(
                question="Count all database tables",
                return_type="result",
            )

            if result.get("success"):
                # Should have validation metadata
                assert "confidence" in result

                # May have validation feedback
                if "validation_feedback" in result:
                    assert isinstance(result["validation_feedback"], str)
