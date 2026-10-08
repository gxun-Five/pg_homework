"""SQL generation prompt templates for LLM-based natural language to SQL conversion.

This module provides prompt templates and builder functions for converting
natural language questions into valid PostgreSQL SQL queries using LLMs.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pg_mcp.models.schema import DatabaseSchema


SQL_GENERATION_SYSTEM_PROMPT = """You are a PostgreSQL SQL expert.

Your task is to convert natural language questions into valid PostgreSQL SQL queries.

## Rules:
1. ONLY generate SELECT queries or CTE (WITH ... SELECT) queries
2. NEVER generate INSERT, UPDATE, DELETE, DROP, CREATE, ALTER, or any DDL/DML statements
3. Use proper PostgreSQL syntax and functions
4. Always use explicit table aliases for clarity
5. Include appropriate LIMIT clauses for potentially large result sets
6. Use proper date/time functions (CURRENT_DATE, CURRENT_TIMESTAMP, INTERVAL, etc.)
7. Handle NULL values appropriately
8. Use appropriate aggregation functions (COUNT, SUM, AVG, etc.) when needed

## Output Format:
Return ONLY the SQL query wrapped in ```sql ... ``` code block.
Do not include any explanation before or after the SQL.

## Example:
User: 查询过去7天的订单数量
```sql
SELECT COUNT(*) AS order_count
FROM orders
WHERE created_at >= CURRENT_DATE - INTERVAL '7 days';
```
"""


def build_user_prompt(
    question: str,
    schema: "DatabaseSchema",
    context: str | None = None,
    previous_attempt: str | None = None,
    error_feedback: str | None = None,
) -> str:
    """Build user prompt for SQL generation.

    This function constructs a comprehensive prompt that includes database schema
    information, optional context, and error feedback for retry scenarios.

    Args:
        question: The user's natural language question.
        schema: Database schema information including tables, columns, and relationships.
        context: Optional additional context to guide SQL generation.
        previous_attempt: Previous SQL that failed (used for retry scenarios).
        error_feedback: Error message from previous attempt (used for retry scenarios).

    Returns:
        str: Formatted user prompt ready for LLM consumption.

    Example:
        >>> prompt = build_user_prompt(
        ...     question="How many users registered today?",
        ...     schema=db_schema,
        ...     context="Focus on the users table"
        ... )
    """
    parts = []

    # Schema context
    parts.append("## Database Schema:")
    parts.append(schema.to_prompt_context())
    parts.append("")

    # Additional context
    if context:
        parts.append("## Additional Context:")
        parts.append(context)
        parts.append("")

    # If this is a retry, include previous attempt and error
    if previous_attempt and error_feedback:
        parts.append("## Previous Attempt (Failed):")
        parts.append(f"```sql\n{previous_attempt}\n```")
        parts.append(f"Error: {error_feedback}")
        parts.append("Please fix the issue and generate a correct query.")
        parts.append("")

    # User question
    parts.append("## Question:")
    parts.append(question)

    return "\n".join(parts)
