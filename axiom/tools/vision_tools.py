import base64
import os
import subprocess
import shutil
import logging
import io
from typing import Any, Dict, Optional
from PIL import Image

from axiom.tools.core import BaseTool, ToolResult, ToolParameter

logger = logging.getLogger(__name__)

class ScreenCaptureTool(BaseTool):
    """Captures the current desktop screen and returns it as a base64 encoded image."""

    def __init__(self):
        super().__init__(
            tool_id="screen_capture",
            name="screen_capture",
            description="Captures the user's current screen and returns it as a base64 encoded JPEG image for visual analysis."
        )

    def _capture_wayland_grim(self, cmd: str) -> Optional[bytes]:
        logger.info(f"Triggering grim screenshot... ({cmd})")
        try:
            # -c includes cursor, the final '-' outputs to stdout
            result = subprocess.run(f"{cmd} -c -", shell=True, capture_output=True, check=True, timeout=3.0)
            return result.stdout
        except subprocess.TimeoutExpired:
            logger.error(f"TimeoutExpired: grim screenshot hung for command {cmd}")
            raise RuntimeError(f"grim screenshot timeout for command {cmd}")
        except Exception as e:
            logger.warning(f"Failed to capture with {cmd}: {e}")
            return None

    def execute(self, params: Dict[str, Any]) -> ToolResult:
        image_bytes = None
        
        # 1. Check for Distrobox host execution of grim
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
                
        # 2. Check for native Wayland grim
        if image_bytes is None and shutil.which("grim"):
            try:
                image_bytes = self._capture_wayland_grim("grim")
            except RuntimeError as e:
                return ToolResult(False, error=str(e))
            
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
                            subprocess.run(["scrot", tmp.name], check=True, timeout=3.0)
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

        logger.info("Screenshot captured. Resizing image...")
        
        try:
            # Load into PIL
            img = Image.open(io.BytesIO(image_bytes))
            img = img.convert("RGB")
            
            # Downscale to max 1024 longest edge
            max_size = 1024
            width, height = img.size
            if max(width, height) > max_size:
                if width > height:
                    new_width = max_size
                    new_height = int((height / width) * max_size)
                else:
                    new_height = max_size
                    new_width = int((width / height) * max_size)
                img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                
            logger.info("Image resized. Sending payload to Ollama VLM...")
            
            # Compress to JPEG
            out_buffer = io.BytesIO()
            img.save(out_buffer, format="JPEG", quality=85)
            jpeg_bytes = out_buffer.getvalue()
            
            b64 = base64.b64encode(jpeg_bytes).decode("utf-8")
            logger.info("VLM response received.") # Although technically this is pre-send, but requested by user as checkpoint
            return ToolResult(True, output={"image_b64": b64, "format": "jpeg", "message": "Screen captured successfully."})
        except Exception as e:
            return ToolResult(False, error=f"Failed to process image payload: {e}")

