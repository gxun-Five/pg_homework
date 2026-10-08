#!/usr/bin/env python3
"""Test script to verify graceful shutdown behavior.

This script tests that the MCP server can shutdown properly within
a reasonable timeframe when receiving SIGINT (Ctrl+C).
"""

import asyncio
import signal
import sys
from datetime import datetime


async def test_shutdown():
    """Test server shutdown timing."""
    print("Testing MCP server shutdown behavior...")
    print("Instructions:")
    print("1. The server will start")
    print("2. Wait for 'Server ready' message")
    print("3. Press Ctrl+C to trigger shutdown")
    print("4. Observe shutdown timing (should complete in < 10 seconds)")
    print()

    from pg_mcp.server import mcp

    # Track shutdown time
    shutdown_start = None

    def signal_handler(signum, frame):
        nonlocal shutdown_start
        shutdown_start = datetime.now()
        print(f"\n[{shutdown_start.strftime('%H:%M:%S')}] Shutdown signal received...")
        raise KeyboardInterrupt

    # Install signal handler
    signal.signal(signal.SIGINT, signal_handler)

    try:
        print("Starting server...")
        await mcp.run_stdio_async()
    except KeyboardInterrupt:
        shutdown_end = datetime.now()
        if shutdown_start:
            duration = (shutdown_end - shutdown_start).total_seconds()
            print(f"[{shutdown_end.strftime('%H:%M:%S')}] Shutdown completed")
            print(f"\nShutdown duration: {duration:.2f} seconds")

            if duration < 10:
                print("✓ PASS: Shutdown completed within acceptable time")
                return 0
            else:
                print("✗ FAIL: Shutdown took too long")
                return 1
    except Exception as e:
        print(f"✗ ERROR: {e}")
        return 1

    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(test_shutdown())
    sys.exit(exit_code)
