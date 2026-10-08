"""Prompt templates and builders for LLM interactions.

This module provides prompt templates and utility functions for generating
prompts used in natural language to SQL conversion and result validation.
"""

from pg_mcp.prompts.result_validation import (
    RESULT_VALIDATION_SYSTEM_PROMPT,
    build_validation_prompt,
)
from pg_mcp.prompts.sql_generation import (
    SQL_GENERATION_SYSTEM_PROMPT,
    build_user_prompt,
)

__all__ = [
    "SQL_GENERATION_SYSTEM_PROMPT",
    "build_user_prompt",
    "RESULT_VALIDATION_SYSTEM_PROMPT",
    "build_validation_prompt",
]
