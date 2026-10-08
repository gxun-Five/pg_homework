"""Comprehensive unit tests for resilience components.

Tests cover:
- Circuit breaker state transitions
- Circuit breaker failure threshold
- Circuit breaker recovery timeout
- Rate limiter concurrent control
- Rate limiter timeout behavior
- Multi-rate limiter coordination
"""

import asyncio
import time

import pytest

from pg_mcp.resilience.circuit_breaker import CircuitBreaker, CircuitState
from pg_mcp.resilience.rate_limiter import MultiRateLimiter, RateLimiter


class TestCircuitBreaker:
    """Test cases for CircuitBreaker implementation."""

    def test_initial_state_is_closed(self) -> None:
        """Circuit breaker should start in CLOSED state."""
        breaker = CircuitBreaker()
        assert breaker.state == CircuitState.CLOSED
        assert breaker.failure_count == 0

    def test_allow_request_when_closed(self) -> None:
        """Requests should be allowed in CLOSED state."""
        breaker = CircuitBreaker()
        assert breaker.allow_request() is True

    def test_invalid_failure_threshold(self) -> None:
        """Should raise ValueError for invalid failure threshold."""
        with pytest.raises(ValueError, match="failure_threshold must be >= 1"):
            CircuitBreaker(failure_threshold=0)

    def test_invalid_recovery_timeout(self) -> None:
        """Should raise ValueError for invalid recovery timeout."""
        with pytest.raises(ValueError, match="recovery_timeout must be >= 0"):
            CircuitBreaker(recovery_timeout=-1.0)

    def test_record_success_resets_failure_count(self) -> None:
        """Recording success should reset failure counter."""
        breaker = CircuitBreaker(failure_threshold=5)

        # Record some failures
        breaker.record_failure()
        breaker.record_failure()
        assert breaker.failure_count == 2

        # Success should reset
        breaker.record_success()
        assert breaker.failure_count == 0

    def test_circuit_opens_on_threshold(self) -> None:
        """Circuit should open when failures reach threshold."""
        breaker = CircuitBreaker(failure_threshold=3)

        # Record failures up to threshold
        assert breaker.state == CircuitState.CLOSED
        breaker.record_failure()  # 1
        assert breaker.state == CircuitState.CLOSED

        breaker.record_failure()  # 2
        assert breaker.state == CircuitState.CLOSED

        breaker.record_failure()  # 3 - threshold reached
        assert breaker.state == CircuitState.OPEN

    def test_requests_blocked_when_open(self) -> None:
        """Requests should be blocked in OPEN state."""
        breaker = CircuitBreaker(failure_threshold=2)

        # Trip the circuit
        breaker.record_failure()
        breaker.record_failure()
        assert breaker.state == CircuitState.OPEN

        # Requests should be blocked
        assert breaker.allow_request() is False

    def test_transition_to_half_open_after_timeout(self) -> None:
        """Circuit should transition to HALF_OPEN after recovery timeout."""
        breaker = CircuitBreaker(
            failure_threshold=2,
            recovery_timeout=0.1,  # 100ms for testing
        )

        # Trip the circuit
        breaker.record_failure()
        breaker.record_failure()
        assert breaker.state == CircuitState.OPEN

        # Wait for recovery timeout
        time.sleep(0.15)

        # Should transition to HALF_OPEN
        assert breaker.state == CircuitState.HALF_OPEN

    def test_allow_request_in_half_open(self) -> None:
        """One request should be allowed in HALF_OPEN state."""
        breaker = CircuitBreaker(failure_threshold=2, recovery_timeout=0.1)

        # Trip and wait for half-open
        breaker.record_failure()
        breaker.record_failure()
        time.sleep(0.15)

        assert breaker.state == CircuitState.HALF_OPEN
        assert breaker.allow_request() is True

    def test_success_in_half_open_closes_circuit(self) -> None:
        """Success in HALF_OPEN should close the circuit."""
        breaker = CircuitBreaker(failure_threshold=2, recovery_timeout=0.1)

        # Trip and wait for half-open
        breaker.record_failure()
        breaker.record_failure()
        time.sleep(0.15)
        assert breaker.state == CircuitState.HALF_OPEN

        # Success should close circuit
        breaker.record_success()
        assert breaker.state == CircuitState.CLOSED
        assert breaker.failure_count == 0

    def test_failure_in_half_open_reopens_circuit(self) -> None:
        """Failure in HALF_OPEN should reopen the circuit."""
        breaker = CircuitBreaker(failure_threshold=2, recovery_timeout=0.1)

        # Trip and wait for half-open
        breaker.record_failure()
        breaker.record_failure()
        time.sleep(0.15)
        assert breaker.state == CircuitState.HALF_OPEN

        # Failure should reopen
        breaker.record_failure()
        assert breaker.state == CircuitState.OPEN

    def test_manual_reset(self) -> None:
        """Manual reset should close circuit and clear failures."""
        breaker = CircuitBreaker(failure_threshold=2)

        # Trip the circuit
        breaker.record_failure()
        breaker.record_failure()
        assert breaker.state == CircuitState.OPEN
        assert breaker.failure_count == 2

        # Manual reset
        breaker.reset()
        assert breaker.state == CircuitState.CLOSED
        assert breaker.failure_count == 0

    def test_get_stats(self) -> None:
        """Statistics should reflect current state."""
        breaker = CircuitBreaker(failure_threshold=5, recovery_timeout=60.0)

        stats = breaker.get_stats()
        assert stats["state"] == CircuitState.CLOSED
        assert stats["failure_count"] == 0
        assert stats["failure_threshold"] == 5
        assert stats["recovery_timeout"] == 60.0
        assert stats["last_failure_time"] is None

        # Record a failure
        breaker.record_failure()
        stats = breaker.get_stats()
        assert stats["failure_count"] == 1
        assert stats["last_failure_time"] is not None

    def test_repr(self) -> None:
        """String representation should be informative."""
        breaker = CircuitBreaker(failure_threshold=5)
        repr_str = repr(breaker)
        assert "CircuitBreaker" in repr_str
        assert "state=closed" in repr_str
        assert "failures=0/5" in repr_str

    def test_thread_safety(self) -> None:
        """Circuit breaker should be thread-safe."""
        import concurrent.futures

        breaker = CircuitBreaker(failure_threshold=100)
        failure_count = 50

        def record_failures():
            for _ in range(failure_count):
                breaker.record_failure()

        # Run multiple threads
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            futures = [executor.submit(record_failures) for _ in range(4)]
            concurrent.futures.wait(futures)

        # Should have recorded all failures
        assert breaker.failure_count == failure_count * 4


class TestRateLimiter:
    """Test cases for RateLimiter implementation."""

    def test_invalid_max_concurrent(self) -> None:
        """Should raise ValueError for invalid max_concurrent."""
        with pytest.raises(ValueError, match="max_concurrent must be >= 1"):
            RateLimiter(max_concurrent=0)

    def test_initial_state(self) -> None:
        """Rate limiter should start with all slots available."""
        limiter = RateLimiter(max_concurrent=5)
        assert limiter.max_concurrent == 5
        assert limiter.active_count == 0
        assert limiter.available == 5

    @pytest.mark.asyncio
    async def test_acquire_and_release(self) -> None:
        """Acquire should increment counter, release should decrement."""
        limiter = RateLimiter(max_concurrent=5)

        acquired = await limiter.acquire()
        assert acquired is True
        assert limiter.active_count == 1
        assert limiter.available == 4

        limiter.release()
        # Give time for async counter update
        await asyncio.sleep(0.01)
        assert limiter.active_count == 0
        assert limiter.available == 5

    @pytest.mark.asyncio
    async def test_context_manager(self) -> None:
        """Context manager should acquire and release automatically."""
        limiter = RateLimiter(max_concurrent=5)

        async with limiter():
            assert limiter.active_count == 1
            assert limiter.available == 4

        await asyncio.sleep(0.01)
        assert limiter.active_count == 0
        assert limiter.available == 5

    @pytest.mark.asyncio
    async def test_concurrent_limit_enforcement(self) -> None:
        """Should enforce maximum concurrent operations."""
        limiter = RateLimiter(max_concurrent=3)
        concurrent_counts = []
        lock = asyncio.Lock()

        async def operation(delay: float) -> str:
            async with limiter():
                # Wait a tiny bit to ensure acquire has updated counter
                await asyncio.sleep(0.001)
                async with lock:
                    concurrent_counts.append(limiter.active_count)
                await asyncio.sleep(delay)
                return "done"

        # Start 5 operations concurrently
        tasks = [operation(0.05) for _ in range(5)]
        await asyncio.gather(*tasks)

        # Maximum concurrent should never exceed limit
        # The semaphore should strictly enforce the limit
        assert max(concurrent_counts) <= 3

    @pytest.mark.asyncio
    async def test_timeout_on_acquire(self) -> None:
        """Acquire should timeout if waiting too long."""
        limiter = RateLimiter(max_concurrent=1)

        # Hold the only slot
        await limiter.acquire()

        # Try to acquire with timeout
        acquired = await limiter.acquire(timeout=0.1)
        assert acquired is False

    @pytest.mark.asyncio
    async def test_timeout_in_context_manager(self) -> None:
        """Context manager should raise TimeoutError on timeout."""
        limiter = RateLimiter(max_concurrent=1)

        # Hold the only slot
        await limiter.acquire()

        # Try to use context manager with timeout
        with pytest.raises(TimeoutError):
            async with limiter(timeout=0.1):
                pass

    @pytest.mark.asyncio
    async def test_statistics_tracking(self) -> None:
        """Should track request and rejection statistics."""
        limiter = RateLimiter(max_concurrent=1)

        # Successful request
        async with limiter():
            stats = limiter.get_stats()
            assert stats["total_requests"] == 1
            assert stats["total_rejections"] == 0

        # Timed out request
        await limiter.acquire()  # Hold the slot
        acquired = await limiter.acquire(timeout=0.05)
        assert acquired is False

        stats = limiter.get_stats()
        # Total requests includes both successful and rejected attempts
        assert stats["total_requests"] == 3  # 1 from context manager, 2 from acquires
        assert stats["total_rejections"] == 1

    @pytest.mark.asyncio
    async def test_reset_stats(self) -> None:
        """Reset should clear statistics but not active count."""
        limiter = RateLimiter(max_concurrent=5)

        async with limiter():
            limiter.reset_stats()
            stats = limiter.get_stats()
            assert stats["total_requests"] == 0
            assert stats["total_rejections"] == 0
            # Active count should not be reset
            assert stats["active_count"] == 1

    def test_repr(self) -> None:
        """String representation should be informative."""
        limiter = RateLimiter(max_concurrent=10)
        repr_str = repr(limiter)
        assert "RateLimiter" in repr_str
        assert "max=10" in repr_str
        assert "active=0" in repr_str
        assert "available=10" in repr_str

    @pytest.mark.asyncio
    async def test_many_concurrent_operations(self) -> None:
        """Should handle many concurrent operations correctly."""
        limiter = RateLimiter(max_concurrent=10)
        operation_count = 50
        completed = []

        async def operation(op_id: int) -> None:
            async with limiter():
                await asyncio.sleep(0.01)
                completed.append(op_id)

        # Run many operations
        tasks = [operation(i) for i in range(operation_count)]
        await asyncio.gather(*tasks)

        # All should complete
        assert len(completed) == operation_count
        assert sorted(completed) == list(range(operation_count))


class TestMultiRateLimiter:
    """Test cases for MultiRateLimiter implementation."""

    def test_initialization(self) -> None:
        """Should initialize with separate limiters."""
        limiter = MultiRateLimiter(query_limit=10, llm_limit=5)

        assert limiter.query_limiter.max_concurrent == 10
        assert limiter.llm_limiter.max_concurrent == 5

    @pytest.mark.asyncio
    async def test_query_limiter_context(self) -> None:
        """Query limiter context should work correctly."""
        limiter = MultiRateLimiter(query_limit=3, llm_limit=2)

        async with limiter.for_queries():
            assert limiter.query_limiter.active_count == 1
            assert limiter.llm_limiter.active_count == 0

        await asyncio.sleep(0.01)
        assert limiter.query_limiter.active_count == 0

    @pytest.mark.asyncio
    async def test_llm_limiter_context(self) -> None:
        """LLM limiter context should work correctly."""
        limiter = MultiRateLimiter(query_limit=3, llm_limit=2)

        async with limiter.for_llm():
            assert limiter.llm_limiter.active_count == 1
            assert limiter.query_limiter.active_count == 0

        await asyncio.sleep(0.01)
        assert limiter.llm_limiter.active_count == 0

    @pytest.mark.asyncio
    async def test_independent_limits(self) -> None:
        """Query and LLM limits should be independent."""
        limiter = MultiRateLimiter(query_limit=2, llm_limit=1)

        # Hold all query slots
        await limiter.query_limiter.acquire()
        await limiter.query_limiter.acquire()

        # LLM should still work
        async with limiter.for_llm():
            assert limiter.llm_limiter.active_count == 1
            assert limiter.query_limiter.active_count == 2

    @pytest.mark.asyncio
    async def test_get_all_stats(self) -> None:
        """Should return statistics for all limiters."""
        limiter = MultiRateLimiter(query_limit=5, llm_limit=3)

        stats = limiter.get_all_stats()
        assert "queries" in stats
        assert "llm" in stats
        assert stats["queries"]["max_concurrent"] == 5
        assert stats["llm"]["max_concurrent"] == 3

    @pytest.mark.asyncio
    async def test_reset_all_stats(self) -> None:
        """Should reset statistics for all limiters."""
        limiter = MultiRateLimiter(query_limit=5, llm_limit=3)

        # Generate some statistics
        async with limiter.for_queries():
            pass
        async with limiter.for_llm():
            pass

        # Reset
        limiter.reset_all_stats()

        stats = limiter.get_all_stats()
        assert stats["queries"]["total_requests"] == 0
        assert stats["llm"]["total_requests"] == 0

    def test_repr(self) -> None:
        """String representation should be informative."""
        limiter = MultiRateLimiter(query_limit=10, llm_limit=5)
        repr_str = repr(limiter)
        assert "MultiRateLimiter" in repr_str
        assert "queries=" in repr_str
        assert "llm=" in repr_str

    @pytest.mark.asyncio
    async def test_concurrent_query_and_llm(self) -> None:
        """Should handle concurrent query and LLM operations."""
        limiter = MultiRateLimiter(query_limit=3, llm_limit=2)
        query_results = []
        llm_results = []

        async def query_operation(op_id: int) -> None:
            async with limiter.for_queries():
                await asyncio.sleep(0.02)
                query_results.append(op_id)

        async def llm_operation(op_id: int) -> None:
            async with limiter.for_llm():
                await asyncio.sleep(0.02)
                llm_results.append(op_id)

        # Run mixed operations
        tasks = []
        tasks.extend([query_operation(i) for i in range(5)])
        tasks.extend([llm_operation(i) for i in range(5)])

        await asyncio.gather(*tasks)

        # All should complete
        assert len(query_results) == 5
        assert len(llm_results) == 5


class TestIntegration:
    """Integration tests combining circuit breaker and rate limiter."""

    @pytest.mark.asyncio
    async def test_circuit_breaker_with_rate_limiter(self) -> None:
        """Circuit breaker and rate limiter should work together."""
        breaker = CircuitBreaker(failure_threshold=3, recovery_timeout=0.2)
        limiter = RateLimiter(max_concurrent=2)

        async def protected_operation(should_fail: bool) -> str:
            # Check circuit breaker
            if not breaker.allow_request():
                raise RuntimeError("Circuit is open")

            # Use rate limiter
            async with limiter():
                await asyncio.sleep(0.01)
                if should_fail:
                    breaker.record_failure()
                    raise ValueError("Operation failed")
                else:
                    breaker.record_success()
                    return "success"

        # Successful operations
        result = await protected_operation(False)
        assert result == "success"

        # Trip the circuit
        for _ in range(3):
            with pytest.raises(ValueError):
                await protected_operation(True)

        # Circuit should be open
        assert breaker.state == CircuitState.OPEN

        # Operations should be rejected
        with pytest.raises(RuntimeError, match="Circuit is open"):
            await protected_operation(False)

        # Wait for recovery
        await asyncio.sleep(0.25)
        assert breaker.state == CircuitState.HALF_OPEN

        # Successful operation should close circuit
        result = await protected_operation(False)
        assert result == "success"
        assert breaker.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_realistic_workload(self) -> None:
        """Simulate realistic workload with failures and recovery."""
        breaker = CircuitBreaker(failure_threshold=5, recovery_timeout=0.3)
        limiter = MultiRateLimiter(query_limit=3, llm_limit=2)

        success_count = 0
        failure_count = 0
        rejected_count = 0

        async def simulated_operation(fail_rate: float) -> None:
            nonlocal success_count, failure_count, rejected_count

            # Check circuit
            if not breaker.allow_request():
                rejected_count += 1
                return

            # Use rate limiter
            async with limiter.for_queries(timeout=1.0):
                import random

                await asyncio.sleep(0.01)

                if random.random() < fail_rate:  # noqa: S311
                    breaker.record_failure()
                    failure_count += 1
                else:
                    breaker.record_success()
                    success_count += 1

        # Simulate workload with 30% failure rate
        tasks = [simulated_operation(0.3) for _ in range(20)]
        await asyncio.gather(*tasks, return_exceptions=True)

        # Verify some operations completed
        total = success_count + failure_count + rejected_count
        assert total == 20
        assert success_count > 0
        assert failure_count > 0
