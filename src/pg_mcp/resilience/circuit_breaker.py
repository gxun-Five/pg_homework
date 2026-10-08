"""Circuit breaker implementation for fault tolerance.

This module provides a circuit breaker pattern implementation that prevents
cascading failures by stopping requests to failing services temporarily.

State transitions:
    CLOSED -> OPEN: When failure count exceeds threshold
    OPEN -> HALF_OPEN: After recovery timeout expires
    HALF_OPEN -> CLOSED: On successful request
    HALF_OPEN -> OPEN: On failed request
"""

import time
from enum import StrEnum, auto
from threading import Lock
from typing import Any


class CircuitState(StrEnum):
    """Circuit breaker states."""

    CLOSED = auto()  # Normal operation, requests allowed
    OPEN = auto()  # Circuit tripped, requests blocked
    HALF_OPEN = auto()  # Testing if service recovered


class CircuitBreaker:
    """Thread-safe circuit breaker for protecting external service calls.

    The circuit breaker tracks failures and automatically opens when failures
    exceed a threshold. After a recovery timeout, it enters half-open state
    to test if the service has recovered.

    Example:
        >>> breaker = CircuitBreaker(failure_threshold=5, recovery_timeout=60.0)
        >>> if breaker.allow_request():
        ...     try:
        ...         result = call_external_service()
        ...         breaker.record_success()
        ...     except Exception:
        ...         breaker.record_failure()
        ...         raise
        ... else:
        ...     # Circuit is open, service unavailable
        ...     raise ServiceUnavailableError()
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
    ) -> None:
        """Initialize circuit breaker.

        Args:
            failure_threshold: Number of consecutive failures before opening circuit.
            recovery_timeout: Seconds to wait before attempting recovery (OPEN -> HALF_OPEN).
        """
        if failure_threshold < 1:
            raise ValueError("failure_threshold must be >= 1")
        if recovery_timeout < 0:
            raise ValueError("recovery_timeout must be >= 0")

        self._failure_threshold = failure_threshold
        self._recovery_timeout = recovery_timeout

        # State tracking
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time: float | None = None

        # Thread safety
        self._lock = Lock()

    @property
    def state(self) -> CircuitState:
        """Get current circuit state.

        Returns:
            Current state of the circuit breaker.
        """
        with self._lock:
            self._update_state()
            return self._state

    @property
    def failure_count(self) -> int:
        """Get current failure count.

        Returns:
            Number of consecutive failures recorded.
        """
        with self._lock:
            return self._failure_count

    def allow_request(self) -> bool:
        """Check if a request is allowed through the circuit.

        This method should be called before making a request to the protected service.
        It automatically transitions from OPEN to HALF_OPEN after recovery timeout.

        Returns:
            True if request should proceed, False if circuit is open.
        """
        with self._lock:
            self._update_state()
            return self._state in (CircuitState.CLOSED, CircuitState.HALF_OPEN)

    def record_success(self) -> None:
        """Record a successful request.

        In HALF_OPEN state, this closes the circuit. In CLOSED state,
        it resets the failure counter.
        """
        with self._lock:
            self._failure_count = 0
            self._last_failure_time = None

            if self._state == CircuitState.HALF_OPEN:
                # Recovery confirmed, close the circuit
                self._state = CircuitState.CLOSED

    def record_failure(self) -> None:
        """Record a failed request.

        Increments failure counter and opens circuit if threshold exceeded.
        In HALF_OPEN state, immediately reopens the circuit.
        """
        with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.time()

            if self._state == CircuitState.HALF_OPEN:
                # Recovery failed, reopen circuit
                self._state = CircuitState.OPEN
            elif (
                self._state == CircuitState.CLOSED
                and self._failure_count >= self._failure_threshold
            ):
                # Check if we should open circuit
                self._state = CircuitState.OPEN

    def reset(self) -> None:
        """Manually reset the circuit breaker to CLOSED state.

        This should be used sparingly, typically only for testing or
        administrative override.
        """
        with self._lock:
            self._state = CircuitState.CLOSED
            self._failure_count = 0
            self._last_failure_time = None

    def _update_state(self) -> None:
        """Update state based on time and current state.

        Transitions from OPEN to HALF_OPEN after recovery timeout.
        Must be called with lock held.
        """
        if self._state == CircuitState.OPEN and self._last_failure_time is not None:
            elapsed = time.time() - self._last_failure_time
            if elapsed >= self._recovery_timeout:
                # Try recovery
                self._state = CircuitState.HALF_OPEN

    def get_stats(self) -> dict[str, Any]:
        """Get circuit breaker statistics.

        Returns:
            Dictionary containing current state and metrics.
        """
        with self._lock:
            self._update_state()
            return {
                "state": self._state,
                "failure_count": self._failure_count,
                "failure_threshold": self._failure_threshold,
                "recovery_timeout": self._recovery_timeout,
                "last_failure_time": self._last_failure_time,
            }

    def __repr__(self) -> str:
        """String representation of circuit breaker.

        Returns:
            String describing current state.
        """
        with self._lock:
            return (
                f"CircuitBreaker(state={self._state}, "
                f"failures={self._failure_count}/{self._failure_threshold})"
            )
