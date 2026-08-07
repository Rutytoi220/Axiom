import base64
import logging
import os
from axiom.tools.base import axiom_tool, ToolResult
from axiom.services.vision_service import VisionService

logger = logging.getLogger(__name__)

@axiom_tool("capture_screen", "Captures a screenshot of the user's primary display and returns it for visual analysis.", {})
def capture_screen():
    try:
        path = VisionService.capture_screen()
        if path and os.path.exists(path):
            with open(path, "rb") as f:
                b64 = base64.b64encode(f.read()).decode("utf-8")
            return ToolResult(True, f"![screenshot](data:image/png;base64,{b64})")
        return ToolResult(False, "Failed to capture screen: VisionService returned empty path.")
    except Exception as e:
        logger.error(f"Error in capture_screen tool: {e}")
        return ToolResult(False, f"Failed to capture screen: {e}")
