"""Tests for axiom.core.async_bridge.

Covers:
- Basic coroutine execution from sync context
- Multiple concurrent calls on the same bridge loop
- Exception propagation
- Shutdown and restart cycle
- Re-entrant deadlock detection
- Public import path via axiom.core
"""

import asyncio
import concurrent.futures
import threading
import pytest

import axiom.core.async_bridge as bridge_module
from axiom.core.async_bridge import run_sync, shutdown_bridge
from axiom.core import run_sync as core_run_sync  # verify public re-export


# ── Fixture: always start fresh, always clean up ──────────────────────────────

@pytest.fixture(autouse=True)
def reset_bridge():
    """Guarantee each test starts with a clean bridge state."""
    shutdown_bridge()
    yield
    shutdown_bridge()


# ── Basic correctness ──────────────────────────────────────────────────────────

class TestRunSync:
    def test_returns_coroutine_value(self):
        async def answer():
            return 42

        assert run_sync(answer()) == 42

    def test_returns_none_for_void_coroutine(self):
        async def noop():
            pass

        assert run_sync(noop()) is None

    def test_awaits_internal_sleep(self):
        async def delayed():
            await asyncio.sleep(0.01)
            return "done"

        assert run_sync(delayed()) == "done"

    def test_propagates_exception(self):
        async def boom():
            raise ValueError("test error")

        with pytest.raises(ValueError, match="test error"):
            run_sync(boom())

    def test_multiple_sequential_calls(self):
        async def square(n):
            return n * n

        results = [run_sync(square(i)) for i in range(10)]
        assert results == [i * i for i in range(10)]

    def test_public_re_export_from_axiom_core(self):
        """run_sync must be importable from axiom.core, not just the internal module."""
        async def ping():
            return "pong"

        assert core_run_sync(ping()) == "pong"


# ── Thread safety ─────────────────────────────────────────────────────────────

class TestThreadSafety:
    def test_concurrent_calls_from_multiple_threads(self):
        """Multiple threads can call run_sync() concurrently without corruption."""
        results = {}
        errors = []

        async def compute(n):
            await asyncio.sleep(0.005)
            return n * 2

        def worker(n):
            try:
                results[n] = run_sync(compute(n))
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)

        assert not errors, f"Thread errors: {errors}"
        for i in range(20):
            assert results[i] == i * 2, f"Wrong result for {i}: {results[i]}"

    def test_single_background_thread_is_reused(self):
        """All run_sync() calls share the same background thread."""
        async def get_thread_id():
            return threading.current_thread().ident

        id1 = run_sync(get_thread_id())
        id2 = run_sync(get_thread_id())
        id3 = run_sync(get_thread_id())

        assert id1 == id2 == id3, "Each call must use the same bridge thread"


# ── Shutdown and restart ───────────────────────────────────────────────────────

class TestShutdown:
    def test_shutdown_when_never_started_is_safe(self):
        """shutdown_bridge() before any run_sync() must not crash."""
        shutdown_bridge()  # Already done by fixture, calling again is safe

    def test_restart_after_shutdown(self):
        """Bridge must restart cleanly after shutdown_bridge() is called."""
        async def hello():
            return "hello"

        assert run_sync(hello()) == "hello"
        shutdown_bridge()
        # Must be usable again after restart
        assert run_sync(hello()) == "hello"

    def test_bridge_thread_is_daemon(self):
        """The bridge thread must be a daemon so it doesn't block process exit."""
        run_sync(asyncio.sleep(0))  # Ensure the thread is started
        assert bridge_module._thread is not None
        assert bridge_module._thread.daemon is True


# ── Deadlock detection ─────────────────────────────────────────────────────────

class TestDeadlockDetection:
    def test_run_sync_from_bridge_thread_raises(self):
        """Calling run_sync() from inside the bridge loop must raise RuntimeError."""
        error_captured = []

        async def inner():
            return "inner"

        async def outer():
            coro = inner()
            try:
                run_sync(coro)
            except RuntimeError as e:
                coro.close()  # prevent 'coroutine was never awaited' warning
                error_captured.append(str(e))

        run_sync(outer())
        assert len(error_captured) == 1
        assert "deadlock" in error_captured[0].lower()
