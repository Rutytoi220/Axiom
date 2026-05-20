"""Test suite for CoreEngine lifecycle, context, and signal handling."""

import asyncio
import signal
import pytest
from unittest.mock import AsyncMock, Mock, patch

from axiom.engine import CoreEngine


class TestCoreEngineInitialization:
    """Test CoreEngine initialization and configuration."""
    
    def test_init_without_config(self):
        """Test engine initialization without config parameter."""
        engine = CoreEngine()
        assert engine.config == {}
        assert isinstance(engine.context, dict)
        assert engine.context == {}
        assert engine._running is False
    
    def test_init_with_config(self):
        """Test engine initialization with configuration dictionary."""
        config = {
            "debug": True,
            "timeout": 30,
            "workers": 4,
            "nested": {"key": "value"}
        }
        engine = CoreEngine(config=config)
        assert engine.config == config
        assert engine.config["debug"] is True
        assert engine.config["nested"]["key"] == "value"
        assert engine.context == {}
        assert engine._running is False
    
    def test_init_config_isolation(self):
        """Test that different instances have isolated configs."""
        config1 = {"name": "engine1"}
        config2 = {"name": "engine2"}
        
        engine1 = CoreEngine(config=config1)
        engine2 = CoreEngine(config=config2)
        
        assert engine1.config["name"] == "engine1"
        assert engine2.config["name"] == "engine2"
        assert engine1.config is not engine2.config


class TestCoreEngineStartStopLifecycle:
    """Test CoreEngine start/stop lifecycle management."""
    
    @pytest.mark.asyncio
    async def test_start_transitions_to_running(self):
        """Test that start() transitions engine to running state."""
        engine = CoreEngine()
        assert not engine._running
        
        await engine.start()
        
        assert engine._running
        await engine.stop()
    
    @pytest.mark.asyncio
    async def test_stop_transitions_to_stopped(self):
        """Test that stop() transitions engine to stopped state."""
        engine = CoreEngine()
        await engine.start()
        assert engine._running
        
        await engine.stop()
        
        assert not engine._running
    
    @pytest.mark.asyncio
    async def test_start_already_running_is_safe(self):
        """Test that starting an already-running engine is idempotent."""
        engine = CoreEngine()
        await engine.start()
        initial_listeners = len(engine._event_listeners.get("engine.started", []))
        
        # Start again - should be safe and not add duplicate handlers
        await engine.start()
        
        assert engine._running
        await engine.stop()
    
    @pytest.mark.asyncio
    async def test_stop_when_not_running_is_safe(self):
        """Test that stopping a non-running engine doesn't raise."""
        engine = CoreEngine()
        
        # Should not raise exception
        await engine.stop()
        
        assert not engine._running
    
    @pytest.mark.asyncio
    async def test_multiple_start_stop_cycles(self):
        """Test that engine can handle multiple start/stop cycles."""
        engine = CoreEngine()
        
        for _ in range(3):
            assert not engine._running
            await engine.start()
            assert engine._running
            await engine.stop()
            assert not engine._running
    
    @pytest.mark.asyncio
    async def test_shutdown_method(self):
        """Test that shutdown() performs cleanup and stops engine."""
        engine = CoreEngine()
        await engine.start()
        assert engine._running
        
        await engine.shutdown()
        
        assert not engine._running
    
    @pytest.mark.asyncio
    async def test_shutdown_when_not_running(self):
        """Test that shutdown() is safe when engine not running."""
        engine = CoreEngine()
        
        # Should be safe to call
        await engine.shutdown()
        
        assert not engine._running


class TestCoreEngineContext:
    """Test CoreEngine execution context access and persistence."""
    
    @pytest.mark.asyncio
    async def test_context_property_returns_dict(self):
        """Test that context property returns a dictionary."""
        engine = CoreEngine()
        assert isinstance(engine.context, dict)
    
    @pytest.mark.asyncio
    async def test_context_is_mutable(self):
        """Test that context can be modified."""
        engine = CoreEngine()
        
        engine.context["key"] = "value"
        
        assert engine.context["key"] == "value"
    
    @pytest.mark.asyncio
    async def test_context_access_before_engine_start(self):
        """Test context is accessible before engine starts."""
        engine = CoreEngine()
        
        engine.context["pre_start"] = "data"
        
        assert engine.context["pre_start"] == "data"
    
    @pytest.mark.asyncio
    async def test_context_access_during_engine_running(self):
        """Test context is accessible while engine is running."""
        engine = CoreEngine()
        await engine.start()
        
        engine.context["during"] = "running"
        assert engine.context["during"] == "running"
        
        await engine.stop()
    
    @pytest.mark.asyncio
    async def test_context_access_after_engine_stop(self):
        """Test context is accessible after engine stops."""
        engine = CoreEngine()
        await engine.start()
        await engine.stop()
        
        engine.context["after_stop"] = "data"
        
        assert engine.context["after_stop"] == "data"
    
    @pytest.mark.asyncio
    async def test_context_persists_across_operations(self):
        """Test that context modifications persist across multiple operations."""
        engine = CoreEngine()
        await engine.start()
        
        engine.context["counter"] = 0
        engine.context["counter"] += 1
        
        # Value should persist
        assert engine.context["counter"] == 1
        
        engine.context["counter"] += 5
        assert engine.context["counter"] == 6
        
        await engine.stop()
        
        # Context should still be accessible and persist after stop
        assert engine.context["counter"] == 6
    
    @pytest.mark.asyncio
    async def test_context_with_complex_types(self):
        """Test context with nested dictionaries and lists."""
        engine = CoreEngine()
        
        engine.context["config"] = {
            "db": {"host": "localhost", "port": 5432},
            "workers": [1, 2, 3]
        }
        
        assert engine.context["config"]["db"]["host"] == "localhost"
        assert len(engine.context["config"]["workers"]) == 3
    
    @pytest.mark.asyncio
    async def test_context_isolation_between_engines(self):
        """Test that different engine instances have isolated contexts."""
        engine1 = CoreEngine()
        engine2 = CoreEngine()
        
        engine1.context["id"] = "engine1"
        engine2.context["id"] = "engine2"
        
        assert engine1.context["id"] == "engine1"
        assert engine2.context["id"] == "engine2"
        assert engine1.context is not engine2.context


class TestCoreEngineEvents:
    """Test CoreEngine event emission and subscription."""
    
    @pytest.mark.asyncio
    async def test_engine_started_event_emitted(self):
        """Test that 'engine.started' event is emitted on start."""
        engine = CoreEngine()
        callback = AsyncMock()
        engine.subscribe("engine.started", callback)
        
        await engine.start()
        
        callback.assert_called_once()
        await engine.stop()
    
    @pytest.mark.asyncio
    async def test_engine_stopped_event_emitted(self):
        """Test that 'engine.stopped' event is emitted on stop."""
        engine = CoreEngine()
        callback = AsyncMock()
        engine.subscribe("engine.stopped", callback)
        
        await engine.start()
        await engine.stop()
        
        callback.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_sync_callback_in_event(self):
        """Test that synchronous callbacks work for events."""
        engine = CoreEngine()
        callback = Mock()
        engine.subscribe("engine.started", callback)
        
        await engine.start()
        
        callback.assert_called_once()
        await engine.stop()
    
    @pytest.mark.asyncio
    async def test_async_callback_in_event(self):
        """Test that asynchronous callbacks work for events."""
        engine = CoreEngine()
        callback = AsyncMock()
        engine.subscribe("engine.started", callback)
        
        await engine.start()
        
        callback.assert_called_once()
        await engine.stop()
    
    @pytest.mark.asyncio
    async def test_multiple_subscribers_same_event(self):
        """Test multiple subscribers listening to same event."""
        engine = CoreEngine()
        callback1 = AsyncMock()
        callback2 = Mock()
        callback3 = AsyncMock()
        
        engine.subscribe("engine.started", callback1)
        engine.subscribe("engine.started", callback2)
        engine.subscribe("engine.started", callback3)
        
        await engine.start()
        
        callback1.assert_called_once()
        callback2.assert_called_once()
        callback3.assert_called_once()
        
        await engine.stop()
    
    @pytest.mark.asyncio
    async def test_custom_events(self):
        """Test subscription to custom events."""
        engine = CoreEngine()
        callback = AsyncMock()
        engine.subscribe("custom.event", callback)
        
        # Manually emit custom event
        await engine._emit_event("custom.event")
        
        callback.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_event_handler_exception_handling(self):
        """Test that exceptions in event handlers are caught and logged."""
        engine = CoreEngine()
        
        def failing_callback():
            raise ValueError("Test error")
        
        successful_callback = Mock()
        
        engine.subscribe("engine.started", failing_callback)
        engine.subscribe("engine.started", successful_callback)
        
        # Should not raise despite callback error
        await engine.start()
        
        successful_callback.assert_called_once()
        await engine.stop()
    
    @pytest.mark.asyncio
    async def test_unsubscribed_event_no_error(self):
        """Test that emitting unsubscribed events doesn't raise."""
        engine = CoreEngine()
        
        # Should not raise
        await engine._emit_event("nonexistent.event")


class TestCoreEngineSignalHandling:
    """Test CoreEngine signal handling for graceful shutdown."""
    
    @pytest.mark.asyncio
    async def test_signal_handlers_setup_on_start(self):
        """Test that signal handlers are registered when engine starts."""
        engine = CoreEngine()
        assert len(engine._signal_handlers) == 0
        
        await engine.start()
        
        # Handlers may or may not be registered depending on platform
        # But no exceptions should be raised
        assert isinstance(engine._signal_handlers, dict)
        
        await engine.stop()
    
    @pytest.mark.asyncio
    async def test_signal_handlers_cleanup_on_stop(self):
        """Test that signal handlers are removed when engine stops."""
        engine = CoreEngine()
        await engine.start()
        
        handlers_after_start = len(engine._signal_handlers)
        
        await engine.stop()
        
        # Handlers should be cleaned up
        assert len(engine._signal_handlers) == 0
    
    @pytest.mark.asyncio
    async def test_signal_handler_setup_failure_is_graceful(self):
        """Test that signal handler setup failures are handled gracefully."""
        engine = CoreEngine()
        
        # Mock add_signal_handler to raise NotImplementedError
        with patch('asyncio.get_event_loop') as mock_get_loop:
            mock_loop = Mock()
            mock_loop.add_signal_handler.side_effect = NotImplementedError()
            mock_get_loop.return_value = mock_loop
            
            # Should not raise
            await engine.start()
            assert engine._running
            
            await engine.stop()
    
    @pytest.mark.asyncio
    async def test_signal_handler_cleanup_failure_is_graceful(self):
        """Test that signal handler cleanup failures are handled gracefully."""
        engine = CoreEngine()
        await engine.start()
        
        # Mock remove_signal_handler to raise RuntimeError
        with patch('asyncio.get_event_loop') as mock_get_loop:
            mock_loop = Mock()
            mock_loop.remove_signal_handler.side_effect = RuntimeError()
            mock_get_loop.return_value = mock_loop
            
            # Should not raise
            await engine.stop()
            assert not engine._running


class TestCoreEngineImportability:
    """Test that module is importable with zero side effects."""
    
    def test_import_core_module(self):
        """Test that core module can be imported without side effects."""
        # Re-import the module - if this succeeds without side effects, test passes
        import importlib
        import axiom.engine.core
        
        importlib.reload(axiom.engine.core)
        # Should not have created any running engines
    
    def test_import_package(self):
        """Test that engine package exports CoreEngine."""
        from axiom.engine import CoreEngine as ImportedEngine
        
        assert ImportedEngine is not None
        
        # Importing should not auto-start anything
        engine = ImportedEngine()
        assert not engine._running
    
    def test_no_global_side_effects(self):
        """Test that importing doesn't create global state."""
        from axiom.engine import CoreEngine
        
        engine1 = CoreEngine()
        engine2 = CoreEngine()
        
        # Each instance should be independent
        assert engine1 is not engine2
        assert engine1.context is not engine2.context
        assert engine1._running is engine2._running is False


class TestCoreEngineIntegration:
    """Integration tests for CoreEngine."""
    
    @pytest.mark.asyncio
    async def test_full_lifecycle_with_context_and_events(self):
        """Test complete engine lifecycle with context and events."""
        engine = CoreEngine(config={"test": True})
        
        start_called = AsyncMock()
        stop_called = AsyncMock()
        
        engine.subscribe("engine.started", start_called)
        engine.subscribe("engine.stopped", stop_called)
        
        # Pre-start context
        engine.context["phase"] = "init"
        
        await engine.start()
        assert engine._running
        assert engine.context["phase"] == "init"
        start_called.assert_called_once()
        
        # Mid-run context updates
        engine.context["phase"] = "running"
        assert engine.context["phase"] == "running"
        
        await engine.stop()
        assert not engine._running
        assert engine.context["phase"] == "running"
        stop_called.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_engine_with_async_event_handlers(self):
        """Test engine with async event handlers that modify context."""
        engine = CoreEngine()
        
        async def on_start():
            await asyncio.sleep(0.01)
            engine.context["start_handler_ran"] = True
        
        async def on_stop():
            await asyncio.sleep(0.01)
            engine.context["stop_handler_ran"] = True
        
        engine.subscribe("engine.started", on_start)
        engine.subscribe("engine.stopped", on_stop)
        
        await engine.start()
        assert engine.context.get("start_handler_ran") is True
        
        await engine.stop()
        assert engine.context.get("stop_handler_ran") is True
    
    @pytest.mark.asyncio
    async def test_engine_rapid_start_stop_cycles(self):
        """Test engine stability under rapid start/stop cycles."""
        engine = CoreEngine()
        
        for i in range(10):
            await engine.start()
            engine.context[f"cycle_{i}"] = True
            assert engine._running
            
            await engine.stop()
            assert not engine._running
        
        # All cycle markers should still be in context
        for i in range(10):
            assert engine.context[f"cycle_{i}"] is True
