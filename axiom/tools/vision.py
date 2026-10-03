import os
import subprocess
import shutil
import logging
import io
import time
from typing import Any, Dict, Optional
from PIL import Image

from axiom.tools.core import BaseTool, ToolResult, ToolParameter
from axiom.core.vision_engine.singleton import get_grounding_engine

logger = logging.getLogger(__name__)

class InteractWithUITool(BaseTool):
    """Interacts with the UI using the AXIOM Grounding Engine."""

    def __init__(self):
        super().__init__(
            tool_id="interact_with_ui",
            name="interact_with_ui",
            description="Autonomously finds and interacts with a UI element on the screen based on a text instruction. Used for clicking buttons, typing into fields, etc.",
            parameters=[
                ToolParameter(
                    name="instruction",
                    type="string",
                    description="Precise text instruction of what to interact with (e.g., 'Click the submit button', 'Type \"hello\" into the search bar').",
                    required=True
                )
            ]
        )

    def _capture_wayland_grim(self, cmd: str) -> Optional[bytes]:
        logger.info(f"Triggering grim screenshot... ({cmd})")
        try:
            result = subprocess.run(f"{cmd} -c -", shell=True, capture_output=True, check=True, timeout=3.0)
            return result.stdout
        except subprocess.TimeoutExpired:
            logger.error(f"TimeoutExpired: grim screenshot hung for command {cmd}")
            raise RuntimeError(f"grim screenshot timeout for command {cmd}")
        except Exception as e:
            logger.warning(f"Failed to capture with {cmd}: {e}")
            return None

    def execute(self, params: Dict[str, Any]) -> ToolResult:
        instruction = params.get("instruction")
        if not instruction:
            return ToolResult(False, error="instruction is required.")

        image_bytes = None
        
        # 1. Capture screen
        if shutil.which("distrobox-host-exec"):
            try:
                res = subprocess.run("distrobox-host-exec which grim", shell=True, capture_output=True, text=True)
                if res.returncode == 0:
                    try:
                        image_bytes = self._capture_wayland_grim("distrobox-host-exec grim")
                    except RuntimeError as e:
                        return ToolResult(False, error=str(e))
            except Exception:
                pass
                
        if image_bytes is None and shutil.which("grim"):
            try:
                image_bytes = self._capture_wayland_grim("grim")
            except RuntimeError as e:
                return ToolResult(False, error=str(e))
            
        if not image_bytes:
            # Fallback to saving to a file via grim
            screenshot_path = "/tmp/screen.png"
            if os.path.exists(screenshot_path):
                os.remove(screenshot_path)
            try:
                subprocess.run(["grim", screenshot_path], check=True)
                with open(screenshot_path, "rb") as f:
                    image_bytes = f.read()
            except Exception as e:
                return ToolResult(False, error=f"Failed to capture screen: {e}")

        logger.info("Screenshot captured. Passing to Grounding Engine...")
        
        try:
            img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
            
            engine = get_grounding_engine()
            
            start_time = time.time()
            result = engine.predict_action(img, instruction, k=4)
            latency = (time.time() - start_time) * 1000
            
            action = result.get("action")
            point = result.get("point")
            text = result.get("text")
            
            if action == "unknown" or not point:
                return ToolResult(False, error=f"Engine failed to parse action from raw output: {result.get('raw_output')}")
            
            x, y = point[0], point[1]
            logger.info(f"Engine returned action '{action}' at ({x}, {y}) in {latency:.2f}ms")
            
            # Execute via ydotool
            if action == "click" or action == "hover":
                # Move mouse
                os.system(f"ydotool mousemove --absolute {x} {y}")
                time.sleep(0.1)
                
                if action == "click":
                    os.system("ydotool click 0xC0") # Left click
                    
                msg = f"Action '{action}' executed at coordinates [{x}, {y}]."
                return ToolResult(True, output=msg)
                
            elif action == "type":
                os.system(f"ydotool mousemove --absolute {x} {y}")
                time.sleep(0.1)
                os.system("ydotool click 0xC0") # Focus
                time.sleep(0.1)
                
                # Type text
                if text:
                    import shlex
                    safe_text = shlex.quote(text)
                    os.system(f"ydotool type {safe_text}")
                
                msg = f"Action 'type' executed at coordinates [{x}, {y}] with text '{text}'."
                return ToolResult(True, output=msg)
                
            else:
                return ToolResult(False, error=f"Unknown action: {action}")
                
        except Exception as e:
            return ToolResult(False, error=f"UI interaction failed: {e}")
