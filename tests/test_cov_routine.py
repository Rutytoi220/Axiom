import pytest
import asyncio
from datetime import datetime
from unittest.mock import patch, MagicMock, AsyncMock
from axiom.core.routine import RoutineEngine

@pytest.fixture
def mock_cli():
    cli = MagicMock()
    return cli

@pytest.mark.asyncio
async def test_routine_init():
    engine = RoutineEngine()
    assert engine.cli is None
    
    cli = MagicMock()
    engine = RoutineEngine(cli)
    assert engine.cli == cli

@pytest.mark.asyncio
async def test_parse_schedule_to_cron():
    engine = RoutineEngine()
    res = await engine.parse_schedule_to_cron("test")
    assert res == "0 0 * * *"
    
    cli = MagicMock()
    cli.ollama = None
    engine = RoutineEngine(cli)
    res = await engine.parse_schedule_to_cron("test")
    assert res == "0 0 * * *"
    
    cli.ollama = MagicMock()
    cli.ollama.generate.return_value = "`* * * * *`"
    engine = RoutineEngine(cli)
    res = await engine.parse_schedule_to_cron("every minute")
    assert res == "* * * * *"
    
    cli.ollama.generate.return_value = "invalid cron"
    res = await engine.parse_schedule_to_cron("test")
    assert res == "0 0 * * *"
    
    cli.ollama.generate.side_effect = Exception("error")
    res = await engine.parse_schedule_to_cron("test")
    assert res == "0 0 * * *"

def test_add_routine():
    engine = RoutineEngine()
    engine.add_routine("prompt", "* * * * *")
    
    cli = MagicMock()
    engine = RoutineEngine(cli)
    engine.add_routine("prompt", "* * * * *")
    cli.memory.set.assert_called()

def test_list_routines():
    engine = RoutineEngine()
    assert engine.list_routines() == []
    
    cli = MagicMock()
    cli.memory.list_keys.return_value = ["routine:123", "other:456"]
    cli.memory.get.return_value = {"id": "123"}
    engine = RoutineEngine(cli)
    res = engine.list_routines()
    assert len(res) == 1
    assert res[0]["id"] == "123"

def test_delete_routine():
    engine = RoutineEngine()
    assert engine.delete_routine("123") == False
    
    cli = MagicMock()
    cli.memory.delete.return_value = True
    engine = RoutineEngine(cli)
    assert engine.delete_routine("123") == True

@pytest.mark.asyncio
async def test_start_stop():
    engine = RoutineEngine()
    engine.start()
    engine.start() # should return early
    await asyncio.sleep(0.1) # allow task to run a bit
    await engine.stop()
    await engine.stop() # should not fail

@pytest.mark.asyncio
async def test_loop():
    cli = MagicMock()
    engine = RoutineEngine(cli)
    engine._is_running = True
    
    routines = [
        {"id": "1", "is_active": False},
        {"id": "2", "is_active": True, "cron_expression": "invalid"},
        {"id": "3", "is_active": True, "cron_expression": "* * * * *", "last_run": 0},
    ]
    engine.list_routines = MagicMock(return_value=routines)
    engine._execute_routine = AsyncMock()
    
    async def mock_sleep(t):
        engine._is_running = False # break the loop
        
    with patch("asyncio.sleep", side_effect=mock_sleep):
        await engine._loop()
        
    engine._execute_routine.assert_called_once()
    
    engine._is_running = True
    engine.list_routines = MagicMock(side_effect=Exception("error"))
    with patch("asyncio.sleep", side_effect=mock_sleep):
        await engine._loop()

@pytest.mark.asyncio
async def test_execute_routine():
    engine = RoutineEngine()
    await engine._execute_routine({"id": "1", "prompt": "test"})
    
    cli = MagicMock()
    engine = RoutineEngine(cli)
    
    res = MagicMock()
    res.success = True
    res.output = "ok"
    cli.orchestrator.run.return_value = res
    await engine._execute_routine({"id": "1", "prompt": "test"})
    cli.engine.event_bus.emit.assert_called_with('routine.completed', {'routine_id': '1', 'output': 'ok'})
    
    res.success = False
    res.error = "err"
    await engine._execute_routine({"id": "1", "prompt": "test"})
    cli.engine.event_bus.emit.assert_called_with('routine.failed', {'routine_id': '1', 'error': 'err'})
    
    def run_raise(*args, **kwargs):
        raise Exception("Routine requires interactive attention")
        
    cli.orchestrator.run.side_effect = run_raise
    await engine._execute_routine({"id": "1", "prompt": "test"})
    
    cli.orchestrator.run.side_effect = Exception("other error")
    await engine._execute_routine({"id": "1", "prompt": "test"})
