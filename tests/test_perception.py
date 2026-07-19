import pytest
import time
import sys
from unittest.mock import patch, MagicMock
from axiom.tools.os_assist import CaptureScreenContextTool
from axiom.perception.watcher import ActiveWindowContext

@pytest.mark.asyncio
async def test_capture_screen_context_execution_time_and_privacy():
    """Verify screenshot tool executes under 150ms and does not write to disk."""
    tool = CaptureScreenContextTool()
    
    mock_pyautogui = MagicMock()
    # Create a mock PIL image
    from PIL import Image
    mock_img = Image.new('RGB', (1920, 1080), color = (73, 109, 137))
    mock_pyautogui.screenshot.return_value = mock_img
    
    with patch.dict(sys.modules, {"pyautogui": mock_pyautogui}):
        start_time = time.perf_counter()
        result = await tool.execute({})
        end_time = time.perf_counter()
        
        execution_time_ms = (end_time - start_time) * 1000
        
        assert result.success is True
        assert "image_data" in result.output
        assert "data:image/jpeg;base64" in result.output["image_data"]
        assert result.output["status"] == "secure_in_memory_only"
        
        # Verify it runs under 150ms (in memory compression should be very fast)
        assert execution_time_ms < 150.0

def test_active_window_context_fallback():
    """Verify ActiveWindowContext gracefully handles missing xdotool."""
    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = FileNotFoundError("xdotool not found")
        
        title = ActiveWindowContext.get_active_window_title()
        assert title == "Unknown Window"

def test_active_window_context_success():
    """Verify ActiveWindowContext correctly parses xdotool output."""
    with patch("subprocess.run") as mock_run:
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "Mozilla Firefox\n"
        mock_run.return_value = mock_result
        
        title = ActiveWindowContext.get_active_window_title()
        assert title == "Mozilla Firefox"
