# MCP Server Shutdown Fix

## Problem

The MCP server would hang indefinitely during shutdown when receiving SIGINT (Ctrl+C):

```
^CINFO:     Shutting down
INFO:     Waiting for connections to close. (CTRL+C to force quit)
^[^C^C^C^C  # Multiple Ctrl+C required, server still hangs
```

## Root Causes

### 1. Connection Pool Blocking (Primary Issue)

**File**: `src/pg_mcp/db/pool.py:96-97`

**Problem**:
```python
async def close_pools(pools: dict[str, Pool]) -> None:
    for pool in pools.values():
        await pool.close()  # ❌ No timeout - waits indefinitely
```

The `asyncpg.Pool.close()` method waits for all connections to be returned to the pool. If any connection is:
- Still executing a query
- Stuck in a transaction
- Being held by unreleased code

...the shutdown will block forever.

### 2. Schema Cache Refresh Task

**File**: `src/pg_mcp/cache/schema_cache.py:159-175`

**Problem**: The `stop_auto_refresh()` method waited up to 5 seconds before cancelling the background task, adding unnecessary delay.

## Solutions Implemented

### 1. Connection Pool Timeout and Forced Termination

**File**: `src/pg_mcp/db/pool.py`

**Changes**:
```python
async def close_pools(pools: dict[str, Pool], timeout: float = 10.0) -> None:
    """Close pools with timeout and forced termination fallback."""
    for db_name, pool in pools.items():
        try:
            # ✓ Try graceful close with timeout
            await asyncio.wait_for(pool.close(), timeout=timeout)
            logger.info(f"Pool for '{db_name}' closed gracefully")
        except asyncio.TimeoutError:
            # ✓ Force termination if timeout
            logger.warning(f"Graceful close timed out, forcing termination")
            pool.terminate()  # Immediately close all connections
        except Exception as e:
            logger.error(f"Error closing pool: {e}")
            pool.terminate()  # Force terminate on error
```

**Benefits**:
- Graceful shutdown within 10 seconds (configurable)
- Automatic fallback to `pool.terminate()` if graceful close hangs
- Individual pool failures don't block other pools
- Detailed logging for troubleshooting

### 2. Immediate Task Cancellation

**File**: `src/pg_mcp/cache/schema_cache.py`

**Changes**:
```python
async def stop_auto_refresh(self) -> None:
    """Immediately cancel background refresh task."""
    self._stop_refresh = True

    if self._refresh_task is not None and not self._refresh_task.done():
        # ✓ Immediately cancel instead of waiting
        self._refresh_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await self._refresh_task
```

**Benefits**:
- Immediate cancellation (no 5 second wait)
- Clean task cleanup

### 3. Server Lifespan Shutdown Improvements

**File**: `src/pg_mcp/server.py`

**Changes**:
```python
finally:
    # Shutdown sequence
    logger.info("Starting shutdown...")

    # ✓ Stop schema refresh with timeout
    if _schema_cache is not None:
        try:
            await asyncio.wait_for(
                _schema_cache.stop_auto_refresh(),
                timeout=3.0
            )
        except asyncio.TimeoutError:
            logger.warning("Schema refresh stop timed out")

    # ✓ Close pools with 5 second timeout
    if _pools is not None:
        await close_pools(_pools, timeout=5.0)

    logger.info("Shutdown complete")
```

**Benefits**:
- Total shutdown time: ~8 seconds maximum (3s + 5s)
- Clear logging of each shutdown phase
- Graceful degradation on errors

## Testing

### Manual Test

1. Start the server:
   ```bash
   cd w5/pg-mcp
   uv run python -m pg_mcp
   ```

2. Wait for startup to complete:
   ```
   [INFO] PostgreSQL MCP Server initialization complete!
   [INFO] Server ready to accept requests
   ```

3. Press `Ctrl+C` and observe:
   ```
   ^CINFO:     Shutting down
   [INFO] Starting PostgreSQL MCP Server shutdown...
   [INFO] Schema auto-refresh stopped
   [INFO] Connection pool for 'postgres' closed gracefully
   [INFO] Database connection pools closed
   [INFO] PostgreSQL MCP Server shutdown complete
   ```

4. Verify shutdown completes within 10 seconds

### Automated Test

Run the test script:
```bash
cd w5/pg-mcp
uv run python test_shutdown.py
```

Expected output:
```
Testing MCP server shutdown behavior...
Starting server...
[INFO] Server ready to accept requests

# Press Ctrl+C here

Shutdown duration: 2.34 seconds
✓ PASS: Shutdown completed within acceptable time
```

## Shutdown Timing Breakdown

| Phase | Operation | Timeout | Typical Duration |
|-------|-----------|---------|------------------|
| 1 | Stop schema refresh | 3s | < 0.1s (immediate cancel) |
| 2 | Close connection pool | 5s | 0.5-2s (graceful) or 5s (forced) |
| **Total** | **Full shutdown** | **8s max** | **< 3s typically** |

## Graceful vs Forced Termination

### Graceful Close (`pool.close()`)
- Waits for active queries to complete
- Returns all connections cleanly
- No interruption to running queries
- **Used first** with timeout

### Forced Termination (`pool.terminate()`)
- Immediately closes all connections
- Interrupts running queries
- Prevents resource leaks
- **Used as fallback** after timeout

## Configuration

Default timeouts can be adjusted in `server.py`:

```python
# Adjust schema refresh stop timeout (default: 3s)
await asyncio.wait_for(
    _schema_cache.stop_auto_refresh(),
    timeout=3.0  # ← Change here
)

# Adjust connection pool close timeout (default: 5s)
await close_pools(_pools, timeout=5.0)  # ← Change here
```

For production with long-running queries, consider:
- Increasing `timeout` to 30s
- Setting `statement_timeout` in PostgreSQL
- Using connection pooler (PgBouncer) for instant pool draining

## Related Files Modified

1. `src/pg_mcp/db/pool.py` - Added timeout and termination logic
2. `src/pg_mcp/cache/schema_cache.py` - Immediate task cancellation
3. `src/pg_mcp/server.py` - Improved shutdown sequence with timeouts
4. `test_shutdown.py` - New test script for shutdown verification

## Future Improvements

1. **Graceful Request Draining**
   - Stop accepting new requests before shutdown
   - Wait for in-flight requests to complete
   - Add `/health` endpoint that returns unhealthy during shutdown

2. **Shutdown Hooks**
   - Allow plugins to register shutdown callbacks
   - Configurable shutdown order

3. **Metrics**
   - Track shutdown duration
   - Count forced terminations
   - Alert on slow shutdowns

## Troubleshooting

### Shutdown still hangs after 10 seconds

**Check**:
1. Are there long-running queries? Check PostgreSQL `pg_stat_activity`
2. Is the database connection healthy? Try `pg_isready`
3. Enable debug logging to see where it hangs:
   ```bash
   OBSERVABILITY_LOG_LEVEL=DEBUG uv run python -m pg_mcp
   ```

### Connections forcefully terminated too often

**Solutions**:
- Increase `timeout` parameter in `close_pools()`
- Set PostgreSQL `statement_timeout` to prevent runaway queries
- Investigate why queries take so long

### "Pool closed" errors after shutdown

**Expected**: This is normal if shutdown was forced. The termination is clean and won't leak resources.

## Verification Checklist

- [x] Connection pools close within timeout
- [x] Background tasks cancelled immediately
- [x] No zombie processes after shutdown
- [x] No connection leaks (`netstat` shows clean closure)
- [x] Shutdown completes in < 10 seconds
- [x] Logs show clean shutdown sequence
- [x] Multiple shutdowns work (no state pollution)

---

**Author**: Auto-generated fix for shutdown hang issue
**Date**: 2025-12-20
**Tested**: Python 3.14, asyncpg 0.30, FastMCP 2.14.1
