"""Result validation service using OpenAI for query result verification.

This module provides the ResultValidator class that uses OpenAI's LLM to validate
whether query results correctly match the user's original question.
"""

import json
from typing import TYPE_CHECKING, Any

from openai import AsyncOpenAI

from pg_mcp.config.settings import OpenAIConfig, ValidationConfig
from pg_mcp.models.errors import LLMError, LLMTimeoutError, LLMUnavailableError
from pg_mcp.models.query import ResultValidationResult
from pg_mcp.prompts.result_validation import (
    RESULT_VALIDATION_SYSTEM_PROMPT,
    build_validation_prompt,
)

if TYPE_CHECKING:
    from openai.types.chat import ChatCompletion


class ResultValidator:
    """Result validator using OpenAI for query result verification.

    This class handles the interaction with OpenAI's API to validate whether
    query results correctly answer the user's original question. It provides
    confidence scoring and suggestions for improvement.

    Example:
        >>> config = OpenAIConfig(api_key="sk-...", model="gpt-4")
        >>> validation_config = ValidationConfig(confidence_threshold=70)
        >>> validator = ResultValidator(config, validation_config)
        >>> result = await validator.validate(
        ...     question="How many users registered today?",
        ...     sql="SELECT COUNT(*) FROM users WHERE created_at >= CURRENT_DATE",
        ...     results=[{"count": 42}],
        ...     row_count=1
        ... )
    """

    def __init__(
        self,
        openai_config: OpenAIConfig,
        validation_config: ValidationConfig,
    ) -> None:
        """Initialize result validator with OpenAI and validation configuration.

        Args:
            openai_config: OpenAI configuration including API key and model settings.
            validation_config: Validation configuration including thresholds and timeouts.
        """
        self.openai_config = openai_config
        self.validation_config = validation_config
        api_key = openai_config.api_key.get_secret_value() if openai_config.api_key else ""
        # The OpenAI client is only created when a key is configured (see
        # SQLGenerator for the same offline-mode handling).
        self.client = (
            AsyncOpenAI(api_key=api_key, timeout=validation_config.timeout_seconds)
            if api_key
            else None
        )

    async def validate(
        self,
        question: str,
        sql: str,
        results: list[dict[str, Any]],
        row_count: int,
    ) -> ResultValidationResult:
        """Validate query results against the user's original question.

        This method sends the question, SQL, and results to OpenAI's API
        and gets a confidence assessment of whether the results correctly
        answer the question.

        Args:
            question: The user's original natural language question.
            sql: The SQL query that was executed.
            results: Query results (will be sampled if too large).
            row_count: Total number of rows in the complete result set.

        Returns:
            ResultValidationResult: Validation result including confidence score,
                explanation, and optional suggestions.

        Raises:
            LLMError: If validation fails or response is invalid.
            LLMTimeoutError: If the API request times out.
            LLMUnavailableError: If the API is unavailable or authentication fails.

        Example:
            >>> result = await validator.validate(
            ...     question="Count active users",
            ...     sql="SELECT COUNT(*) FROM users WHERE status = 'active'",
            ...     results=[{"count": 150}],
            ...     row_count=1
            ... )
            >>> print(f"Confidence: {result.confidence}%")
            >>> print(f"Acceptable: {result.is_acceptable}")
        """
        # If validation is disabled, return high confidence result
        if not self.validation_config.enabled:
            return ResultValidationResult(
                confidence=100,
                explanation="Validation is disabled in configuration",
                suggestion=None,
                is_acceptable=True,
            )

        if self.client is None:
            raise LLMUnavailableError(
                message="OpenAI API key is not configured; cannot validate results",
                details={"model": self.openai_config.model},
            )

        # Sample results to avoid sending too much data to LLM
        sample_results = results[: self.validation_config.sample_rows]

        # Build the validation prompt
        prompt = build_validation_prompt(
            question=question,
            sql=sql,
            results=sample_results,
            row_count=row_count,
        )

        try:
            # Call OpenAI API with structured JSON output
            response: ChatCompletion = await self.client.chat.completions.create(
                model=self.openai_config.model,
                messages=[
                    {"role": "system", "content": RESULT_VALIDATION_SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=500,
                temperature=0.0,  # Use deterministic output for validation
                response_format={"type": "json_object"},  # Ensure JSON response
            )

            # Extract and parse the response
            if not response.choices:
                raise LLMError(
                    message="OpenAI returned empty response for result validation",
                    details={"response": response.model_dump()},
                )

            content = response.choices[0].message.content
            if not content:
                raise LLMError(
                    message="OpenAI returned empty message content for result validation",
                    details={"response": response.model_dump()},
                )

            # Parse JSON response
            try:
                result_dict = json.loads(content)
            except json.JSONDecodeError as e:
                # If JSON parsing fails, return moderate confidence with error explanation
                return ResultValidationResult(
                    confidence=60,
                    explanation=f"Validation response parsing failed: {e!s}",
                    suggestion="Unable to parse LLM response, manual verification recommended",
                    is_acceptable=False,
                )

            # Extract fields from response
            confidence = result_dict.get("confidence", 50)
            explanation = result_dict.get("explanation", "No explanation provided")
            suggestion = result_dict.get("suggestion")

            # Validate confidence is within bounds
            if not isinstance(confidence, int) or not (0 <= confidence <= 100):
                confidence = (
                    max(0, min(100, int(confidence)))
                    if isinstance(confidence, (int, float))
                    else 50
                )

            # Determine if result is acceptable based on threshold
            is_acceptable = confidence >= self.validation_config.confidence_threshold

            return ResultValidationResult(
                confidence=confidence,
                explanation=explanation,
                suggestion=suggestion,
                is_acceptable=is_acceptable,
            )

        except TimeoutError as e:
            timeout = self.validation_config.timeout_seconds
            raise LLMTimeoutError(
                message=f"Result validation timed out after {timeout}s",
                details={"timeout": timeout},
            ) from e
        except json.JSONDecodeError as e:
            # This should be caught above, but kept for safety
            return ResultValidationResult(
                confidence=60,
                explanation=f"JSON parsing error: {e!s}",
                suggestion=None,
                is_acceptable=False,
            )
        except LLMError:
            # Re-raise LLM errors as-is
            raise
        except Exception as e:
            # Handle various OpenAI errors
            error_msg = str(e)
            if "authentication" in error_msg.lower() or "api_key" in error_msg.lower():
                raise LLMUnavailableError(
                    message="OpenAI API authentication failed - check API key",
                    details={"error": error_msg},
                ) from e
            if "rate_limit" in error_msg.lower():
                raise LLMUnavailableError(
                    message="OpenAI API rate limit exceeded",
                    details={"error": error_msg},
                ) from e
            raise LLMError(
                message=f"Result validation failed: {error_msg}",
                details={"error": error_msg},
            ) from e
