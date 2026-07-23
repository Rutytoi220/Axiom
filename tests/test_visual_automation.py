import pytest
from unittest.mock import Mock, patch
from axiom.plugins.visual_automation import VisualAutomationPlugin

@pytest.fixture
def mock_engine():
    engine = Mock()
    engine.event_bus = Mock()
    
    mock_registry = Mock()
    mock_automation_plugin = Mock()
    mock_automation_plugin.execute_action.return_value = True
    
    mock_registry.get_plugin.return_value = mock_automation_plugin
    engine.registry = mock_registry
    
    return engine

def test_visual_automation_extraction(mock_engine):
    plugin = VisualAutomationPlugin(engine=mock_engine)
    
    # Mock VisionPipeline
    plugin.vision.capture_active_window = Mock(return_value="fake_b64_image_data")
    
    # Mock LLM to return valid JSON
    plugin.llm.chat = Mock(return_value='{"target": "C2", "action": "click"}')
    
    # Prevent actual sleep during tests
    with patch("axiom.plugins.visual_automation.time.sleep"):
        success = plugin.execute_visual_task("click the submit button")
        
        assert success is True
        
        # Verify the AutomationPlugin was called with the correct extracted parameters
        automation_plugin = mock_engine.registry.get_plugin("automation")
        automation_plugin.execute_action.assert_called_once_with("C2", "click", None)
        
        # Verify the event bus was called
        assert mock_engine.event_bus.publish.call_count == 1
        event = mock_engine.event_bus.publish.call_args[0][0]
        assert event.event_type == "visual.act"
        assert event.data["target"] == "C2"
        assert event.data["action"] == "click"

def test_automation_plugin_execute_action_mock():
    from axiom.plugins.automation_plugin import AutomationPlugin
    
    plugin = AutomationPlugin()
    
    # In headless environment without pyautogui, it should mock gracefully and return True
    with patch.dict("sys.modules", {"pyautogui": None}):
        # Mock the ImportError to trigger fallback
        with patch("builtins.__import__", side_effect=ImportError):
            success = plugin.execute_action("A1", "click")
            assert success is True
