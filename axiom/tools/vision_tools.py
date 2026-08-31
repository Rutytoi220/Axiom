import base64
import os
import subprocess
import shutil
import logging
from typing import Any, Dict, Optional

from axiom.tools.core import BaseTool, ToolResult, ToolParameter

logger = logging.getLogger(__name__)

class ScreenCaptureTool(BaseTool):
    """Captures the current desktop screen and returns it as a base64 encoded image."""

    def __init__(self):
        super().__init__(
            tool_id="screen_capture",
            name="screen_capture",
            description="Captures the user's current screen and returns it as a base64 encoded PNG image for visual analysis."
        )

    def _capture_wayland_grim(self, cmd: str) -> Optional[bytes]:
        try:
            # -t png sets type to png, -o - outputs to stdout
            result = subprocess.run(f"{cmd} -t png -o -", shell=True, capture_output=True, check=True)
            return result.stdout
        except Exception as e:
            logger.warning(f"Failed to capture with {cmd}: {e}")
            return None

    def execute(self, params: Dict[str, Any]) -> ToolResult:
        image_bytes = None
        
        # 1. Check for Distrobox host execution of grim
        if shutil.which("distrobox-host-exec"):
            try:
                # Need to check if host has grim
                res = subprocess.run("distrobox-host-exec which grim", shell=True, capture_output=True, text=True)
                if res.returncode == 0:
                    image_bytes = self._capture_wayland_grim("distrobox-host-exec grim")
            except Exception:
                pass
                
        # 2. Check for native Wayland grim
        if image_bytes is None and shutil.which("grim"):
            image_bytes = self._capture_wayland_grim("grim")
            
        # 3. Fallback to X11 python-mss
        if image_bytes is None:
            try:
                import mss
                with mss.mss() as sct:
                    monitor = sct.monitors[1]
                    sct_img = sct.grab(monitor)
                    image_bytes = mss.tools.to_png(sct_img.rgb, sct_img.size)
            except ImportError:
                # 4. Final fallback to scrot for X11
                if shutil.which("scrot"):
                    try:
                        import tempfile
                        with tempfile.NamedTemporaryFile(suffix=".png") as tmp:
                            subprocess.run(["scrot", tmp.name], check=True)
                            tmp.seek(0)
                            image_bytes = tmp.read()
                    except Exception as e:
                        logger.error(f"Scrot fallback failed: {e}")
                else:
                    return ToolResult(False, error="No screen capture utility available (grim/mss/scrot).")
            except Exception as e:
                return ToolResult(False, error=f"python-mss fallback failed: {e}")

        if not image_bytes:
            return ToolResult(False, error="Failed to capture screen: No image data returned.")

        b64 = base64.b64encode(image_bytes).decode("utf-8")
        return ToolResult(True, output={"image_b64": b64, "format": "png", "message": "Screen captured successfully."})

