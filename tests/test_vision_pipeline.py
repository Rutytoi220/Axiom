import pytest
from unittest.mock import patch, MagicMock
import base64
from PIL import Image
from axiom.perception.vision_pipeline import VisionPipeline

def test_apply_som_grid():
    pipeline = VisionPipeline()
    # Skip if dependencies aren't loaded (e.g. testing in headless without MSS/Pillow)
    if not pipeline.is_available:
        pytest.skip("Vision pipeline dependencies not available")
        
    # Create a dummy image 800x600
    img = Image.new("RGB", (800, 600), color="white")
    
    # Apply grid
    processed_img = pipeline._apply_som_grid(img, grid_size=4)
    
    # Verify dimensions are unchanged
    assert processed_img.size == (800, 600)
    
    # We can't easily assert the pixels changed in a meaningful way without OCR,
    # but we can check it didn't throw an exception and returned an Image.
    assert isinstance(processed_img, Image.Image)

@patch("axiom.perception.vision_pipeline.mss")
@patch("axiom.perception.vision_pipeline.gw")
def test_capture_active_window(mock_gw, mock_mss):
    pipeline = VisionPipeline()
    # Mock availability to force it to run even if missing deps locally
    pipeline.is_available = True
    
    # Mock active window
    mock_win = MagicMock()
    mock_win.top = 10
    mock_win.left = 10
    mock_win.width = 800
    mock_win.height = 600
    mock_gw.getActiveWindow.return_value = mock_win
    
    # Mock MSS grab
    mock_sct = MagicMock()
    mock_sct_img = MagicMock()
    mock_sct_img.size = (800, 600)
    mock_sct_img.bgra = b'\x00' * (800 * 600 * 4) # dummy raw BGRA data
    mock_sct.grab.return_value = mock_sct_img
    
    # Need to mock MSS context manager
    mock_mss_instance = MagicMock()
    mock_mss_instance.__enter__.return_value = mock_sct
    mock_mss.mss.return_value = mock_mss_instance
    
    # Disable grid to avoid PIL issues with mock data
    with patch.object(pipeline, "_apply_som_grid") as mock_grid:
        mock_grid.side_effect = lambda x: x # return unmodified
        
        result = pipeline.capture_active_window(with_grid=False)
        
        # Verify a base64 string was returned
        assert isinstance(result, str)
        # Attempt to decode it
        decoded = base64.b64decode(result)
        assert len(decoded) > 0
