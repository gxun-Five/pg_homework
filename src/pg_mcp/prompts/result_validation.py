"""Result validation prompt templates for LLM-based query result verification.

This module provides prompt templates and builder functions for validating
whether query results correctly match the user's original question using LLMs.
"""

import json
from typing import Any

RESULT_VALIDATION_SYSTEM_PROMPT = """You are a SQL query result validator. \
Your task is to evaluate whether the query results match the user's original question.

Analyze:
1. Does the SQL query correctly interpret the user's intent?
2. Do the results make sense given the question?
3. Are there any obvious errors or mismatches?
4. Are the column names and data types appropriate for the question?
5. Does the result set size seem reasonable for the question?

Return a JSON object with:
{
  "confidence": <0-100 integer>,
  "explanation": "<brief explanation of why the results match or don't match>",
  "suggestion": "<optional improvement suggestion or null>"
}

Confidence levels:
- 90-100: Results clearly match the question, SQL is well-formed and accurate
- 70-89: Results likely match, minor uncertainties or potential improvements exist
- 50-69: Results may not fully match, significant concerns or ambiguities present
- 0-49: Results likely don't match the question, major issues detected

Be concise but specific in your explanation. Focus on semantic correctness \
rather than minor formatting issues.
"""


def build_validation_prompt(
    question: str,
    sql: str,
    results: list[dict[str, Any]],
    row_count: int,
) -> str:
    """Build validation prompt for result verification.

    This function constructs a comprehensive prompt that includes the user's
    original question, the generated SQL, and a sample of the query results
    for LLM-based validation.

    Args:
        question: The user's original natural language question.
        sql: The SQL query that was executed.
        results: Sample of query results (limited number of rows).
        row_count: Total number of rows in the complete result set.

    Returns:
        str: Formatted validation prompt ready for LLM consumption.

    Example:
        >>> prompt = build_validation_prompt(
        ...     question="How many users registered today?",
        ...     sql="SELECT COUNT(*) FROM users WHERE created_at >= CURRENT_DATE",
        ...     results=[{"count": 42}],
        ...     row_count=1
        ... )
    """
    # Format results as JSON for better readability
    results_preview = json.dumps(results, ensure_ascii=False, indent=2, default=str)

    # Build the prompt
    parts = [
        "## Original Question:",
        question,
        "",
        "## Executed SQL:",
        "```sql",
        sql,
        "```",
        "",
        f"## Results (showing {len(results)} of {row_count} rows):",
        "```json",
        results_preview,
        "```",
        "",
        (
            "Please evaluate if the results match the user's question "
            "and return your assessment as a JSON object."
        ),
    ]

    return "\n".join(parts)
