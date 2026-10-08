"""Rate limiting implementation for controlling concurrent access.

This module provides rate limiters that control concurrent access to resources
using semaphores. It helps prevent resource exhaustion by limiting the number
of concurrent operations.
"""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any


class RateLimiter:
    """Async rate limiter using semaphore for concurrent request control.

    This rate limiter controls the maximum number of concurrent operations
    using an asyncio.Semaphore. It's designed for use with async/await code.

    Example:
        >>> limiter = RateLimiter(max_concurrent=5)
        >>> async with limiter:
        ...     # Only 5 concurrent operations allowed
        ...     result = await perform_operation()

    Attributes:
        max_concurrent: Maximum number of concurrent operations allowed.
    """

    def __init__(self, max_concurrent: int) -> None:
        """Initialize rate limiter.

        Args:
            max_concurrent: Maximum number of concurrent operations allowed.

        Raises:
            ValueError: If max_concurrent is less than 1.
        """
        if max_concurrent < 1:
            raise ValueError("max_concurrent must be >= 1")

        self._max_concurrent = max_concurrent
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._active_count = 0
        self._total_requests = 0
        self._total_rejections = 0
        self._lock = asyncio.Lock()

    @property
    def max_concurrent(self) -> int:
        """Get maximum concurrent operations allowed.

        Returns:
            Maximum concurrent operations.
        """
        return self._max_concurrent

    @property
    def active_count(self) -> int:
        """Get number of currently active operations.

        Returns:
            Number of active operations.
        """
        return self._active_count

    @property
    def available(self) -> int:
        """Get number of available slots.

        Returns:
            Number of available concurrent slots.
        """
        return self._max_concurrent - self._active_count

    async def acquire(self, *, timeout: float | None = None) -> bool:  # noqa: ASYNC109
        """Acquire a slot for concurrent operation.

        Args:
            timeout: Optional timeout in seconds. If None, waits indefinitely.

        Returns:
            True if slot was acquired, False if timeout occurred.

        Raises:
            asyncio.TimeoutError: If timeout is exceeded.
        """
        async with self._lock:
            self._total_requests += 1

        try:
            if timeout is not None:
                async with asyncio.timeout(timeout):
                    await self._semaphore.acquire()
            else:
                await self._semaphore.acquire()

            async with self._lock:
                self._active_count += 1

            return True

        except TimeoutError:
            async with self._lock:
                self._total_rejections += 1
            return False

    def release(self) -> None:
        """Release a slot after operation completes.

        This should be called after acquire() when the operation is complete.
        Use the async context manager to handle this automatically.
        """
        self._semaphore.release()
        # Note: We use a try-except here because release() is not async
        # but we need to update the counter. The counter update is not
        # critical for correctness.
        try:
            loop = asyncio.get_running_loop()
            _task = loop.create_task(self._decrement_counter())  # noqa: RUF006
        except RuntimeError:
            # No event loop running, just decrement directly (testing scenario)
            self._active_count = max(0, self._active_count - 1)

    async def _decrement_counter(self) -> None:
        """Decrement active counter (internal helper)."""
        async with self._lock:
            self._active_count = max(0, self._active_count - 1)

    @asynccontextmanager
    async def __call__(
        self,
        *,
        timeout: float | None = None,  # noqa: ASYNC109
    ) -> AsyncIterator[None]:
        """Context manager for rate-limited operations.

        Args:
            timeout: Optional timeout in seconds.

        Yields:
            None

        Raises:
            asyncio.TimeoutError: If timeout is exceeded.

        Example:
            >>> limiter = RateLimiter(max_concurrent=5)
            >>> async with limiter(timeout=10.0):
            ...     await perform_operation()
        """
        acquired = await self.acquire(timeout=timeout)
        if not acquired:
            raise TimeoutError("Rate limiter timeout exceeded")

        try:
            yield
        finally:
            self.release()

    def get_stats(self) -> dict[str, Any]:
        """Get rate limiter statistics.

        Returns:
            Dictionary containing current metrics.
        """
        return {
            "max_concurrent": self._max_concurrent,
            "active_count": self._active_count,
            "available": self.available,
            "total_requests": self._total_requests,
            "total_rejections": self._total_rejections,
        }

    def reset_stats(self) -> None:
        """Reset statistics counters.

        This does not affect the active operation count, only the
        cumulative statistics.
        """
        self._total_requests = 0
        self._total_rejections = 0

    def __repr__(self) -> str:
        """String representation of rate limiter.

        Returns:
            String describing current state.
        """
        return (
            f"RateLimiter(max={self._max_concurrent}, "
            f"active={self._active_count}, "
            f"available={self.available})"
        )


class MultiRateLimiter:
    """Manages multiple rate limiters for different resource types.

    This class provides a convenient way to manage multiple rate limiters
    for different types of operations (e.g., queries, LLM calls).

    Example:
        >>> limiter = MultiRateLimiter(
        ...     query_limit=10,
        ...     llm_limit=5
        ... )
        >>> async with limiter.for_queries():
        ...     result = await execute_query()
        >>> async with limiter.for_llm():
        ...     sql = await generate_sql()
    """

    def __init__(
        self,
        query_limit: int = 10,
        llm_limit: int = 5,
    ) -> None:
        """Initialize multi-rate limiter.

        Args:
            query_limit: Maximum concurrent database queries.
            llm_limit: Maximum concurrent LLM API calls.
        """
        self._query_limiter = RateLimiter(max_concurrent=query_limit)
        self._llm_limiter = RateLimiter(max_concurrent=llm_limit)

    @property
    def query_limiter(self) -> RateLimiter:
        """Get the query rate limiter.

        Returns:
            Rate limiter for database queries.
        """
        return self._query_limiter

    @property
    def llm_limiter(self) -> RateLimiter:
        """Get the LLM rate limiter.

        Returns:
            Rate limiter for LLM API calls.
        """
        return self._llm_limiter

    @asynccontextmanager
    async def for_queries(
        self,
        *,
        timeout: float | None = None,  # noqa: ASYNC109
    ) -> AsyncIterator[None]:
        """Context manager for rate-limited query operations.

        Args:
            timeout: Optional timeout in seconds.

        Yields:
            None

        Example:
            >>> async with multi_limiter.for_queries(timeout=30.0):
            ...     result = await execute_query()
        """
        async with self._query_limiter(timeout=timeout):
            yield

    @asynccontextmanager
    async def for_llm(
        self,
        *,
        timeout: float | None = None,  # noqa: ASYNC109
    ) -> AsyncIterator[None]:
        """Context manager for rate-limited LLM operations.

        Args:
            timeout: Optional timeout in seconds.

        Yields:
            None

        Example:
            >>> async with multi_limiter.for_llm(timeout=60.0):
            ...     sql = await generate_sql()
        """
        async with self._llm_limiter(timeout=timeout):
            yield

    def get_all_stats(self) -> dict[str, dict[str, Any]]:
        """Get statistics for all rate limiters.

        Returns:
            Dictionary mapping limiter names to their statistics.
        """
        return {
            "queries": self._query_limiter.get_stats(),
            "llm": self._llm_limiter.get_stats(),
        }

    def reset_all_stats(self) -> None:
        """Reset statistics for all rate limiters."""
        self._query_limiter.reset_stats()
        self._llm_limiter.reset_stats()

    def __repr__(self) -> str:
        """String representation of multi-rate limiter.

        Returns:
            String describing all limiters.
        """
        return f"MultiRateLimiter(\n  queries={self._query_limiter},\n  llm={self._llm_limiter}\n)"
