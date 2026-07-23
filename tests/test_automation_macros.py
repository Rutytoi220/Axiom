import pytest
import json
from unittest.mock import Mock, patch
from axiom.plugins.automation_plugin import AutomationPlugin

class MockEvent:
    def __init__(self, data):
        self.data = data

@pytest.fixture
def mock_engine(tmp_path):
    engine = Mock()
    engine.event_bus = Mock()
    engine.registry = Mock()
    return engine

@pytest.fixture
def automation_plugin(mock_engine, tmp_path):
    plugin = AutomationPlugin(engine=mock_engine)
    # Redirect macros_dir to tmp_path
    plugin.macros_dir = tmp_path / "macros"
    plugin.macros_dir.mkdir(parents=True, exist_ok=True)
    plugin.initialize()
    return plugin

def test_macro_recording_flow(automation_plugin):
    # 1. Start recording
    assert automation_plugin.start_recording() is True
    assert automation_plugin.is_recording is True
    
    # 2. Simulate tool executions via event bus
    automation_plugin._on_tool_executed(MockEvent({
        "tool_name": "click_element",
        "arguments": {"x": 100, "y": 200}
    }))
    
    automation_plugin._on_tool_executed(MockEvent({
        "tool_name": "type_text",
        "arguments": {"text": "hello"}
    }))
    
    # 3. Stop recording
    macro_id = automation_plugin.stop_recording("Test Macro")
    assert macro_id is not None
    assert automation_plugin.is_recording is False
    
    # Verify file is saved
    file_path = automation_plugin.macros_dir / f"{macro_id}.json"
    assert file_path.exists()
    
    data = json.loads(file_path.read_text())
    assert data["name"] == "Test Macro"
    assert len(data["steps"]) == 2
    assert data["steps"][0]["tool"] == "click_element"
    assert data["steps"][0]["arguments"] == {"x": 100, "y": 200}

def test_macro_execution_flow(automation_plugin):
    # Pre-populate a macro
    automation_plugin.start_recording()
    automation_plugin._on_tool_executed(MockEvent({
        "tool_name": "test_tool",
        "arguments": {"arg1": "val1"}
    }))
    macro_id = automation_plugin.stop_recording("Exec Test")
    
    # Execute the macro
    with patch('threading.Thread.start') as mock_thread_start:
        assert automation_plugin.execute_macro(macro_id) is True
        assert mock_thread_start.called

def test_stop_recording_empty(automation_plugin):
    automation_plugin.start_recording()
    macro_id = automation_plugin.stop_recording("Empty Macro")
    assert macro_id is None
