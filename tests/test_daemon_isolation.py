import pytest
import multiprocessing
import sys
from unittest.mock import patch, MagicMock

@pytest.fixture
def mock_engine_deps():
    with patch("axiom.core.engine.EventBus") as mock_bus, \
         patch("axiom.core.engine.Registry") as mock_reg, \
         patch("axiom.memory.SyncMemoryStore") as mock_mem:
        yield mock_bus.return_value, mock_reg.return_value, mock_mem.return_value

def test_engine_daemon_isolation_in_main_process(mock_engine_deps):
    bus, reg, mem = mock_engine_deps
    from axiom.core.engine import Engine
    
    # Simulate MainProcess
    with patch("multiprocessing.current_process") as mock_cp:
        mock_cp.return_value.name = "MainProcess"
        
        engine = Engine(bus=bus, registry=reg, memory=mem)
        
        with patch.object(engine.proactive_watcher, 'start') as pw_start, \
             patch.object(engine.os_watcher, 'start') as ow_start, \
             patch.object(engine.audio_daemon, 'start') as ad_start:
             
             engine.initialize()
             
             pw_start.assert_called_once()
             ow_start.assert_called_once()
             ad_start.assert_called_once()

def test_engine_daemon_isolation_in_child_process(mock_engine_deps):
    bus, reg, mem = mock_engine_deps
    from axiom.core.engine import Engine
    
    # Simulate ChildProcess
    with patch("multiprocessing.current_process") as mock_cp:
        mock_cp.return_value.name = "Process-1"
        
        engine = Engine(bus=bus, registry=reg, memory=mem)
        
        with patch.object(engine.proactive_watcher, 'start') as pw_start, \
             patch.object(engine.os_watcher, 'start') as ow_start, \
             patch.object(engine.audio_daemon, 'start') as ad_start:
             
             engine.initialize()
             
             pw_start.assert_not_called()
             ow_start.assert_not_called()
             ad_start.assert_not_called()

def test_cli_daemon_isolation(mock_engine_deps):
    # Test that cli.py guards sleep daemon
    from axiom.api.cli import CLI
    
    # Simulate ChildProcess
    with patch("multiprocessing.current_process") as mock_cp:
        mock_cp.return_value.name = "Process-1"
        
        # We need to mock UniversalLLMClient and other things CLI initializes
        with patch("axiom.api.cli.UniversalLLMClient"), \
             patch("axiom.api.cli.SyncMemoryStore"), \
             patch("axiom.api.cli.Engine") as mock_engine_cls:
             
             mock_engine_cls.return_value.event_bus = mock_engine_deps[0]
             mock_engine_cls.return_value.registry = mock_engine_deps[1]
             
             cli = CLI()
             
             assert cli.sleep_daemon is None
             assert cli.routine_engine is None
