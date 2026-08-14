"""ScreenCaptureTool — autonomous eyes for the AXIOM agent.

Takes a screenshot using the best available method on the host Linux desktop
(Wayland via grim, Wayland via pyautogui, or X11 fallback), saves it to a
temp file, and returns the absolute filepath so the LLM can reference it.

Registered on the LOCAL client only — not on headless Swarm Nodes.
"""
import logging
import shutil
import subprocess
import tempfile
import os
from pathlib import Path
from axiom.tools import BaseTool, ToolResult

logger = logging.getLogger(__name__)

_TEMP_DIR = Path(tempfile.gettempdir()) / "axiom_screenshots"
_TEMP_DIR.mkdir(parents=True, exist_ok=True)


class VisionCaptureTool(BaseTool):
    """
    Takes a screenshot of the user's current desktop.
    Returns the absolute filepath to the saved PNG.
    Use this before moving the mouse to understand the screen layout.
    """

    def __init__(self):
        super().__init__(
            tool_id="vision_capture",
            name="VisionCaptureTool",
            description=(
                "Takes a screenshot of the user's current desktop. Returns the absolute filepath "
                "to a temporary PNG file. Use this before moving the mouse to understand the screen "
                "layout, verify the state of the UI, or read text on screen."
            ),
        )
        # No parameters needed — always captures the full primary screen

    async def execute(self) -> ToolResult:
        import asyncio
        from functools import partial
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._capture_sync)

    def _capture_sync(self) -> ToolResult:
        """Run in a thread executor so it doesn't block the async loop."""
        import time
        filename = f"axiom_{int(time.time())}.png"
        out_path = str(_TEMP_DIR / filename)

        image_bytes = None

        # ── Strategy 1: Wayland via distrobox-host grim ──────────────────── #
        if shutil.which("distrobox-host-exec"):
            try:
                res = subprocess.run(
                    "distrobox-host-exec which grim",
                    shell=True, capture_output=True, text=True
                )
                if res.returncode == 0:
                    image_bytes = self._grim("distrobox-host-exec grim")
            except Exception:
                pass

        # ── Strategy 2: Native Wayland grim ──────────────────────────────── #
        if image_bytes is None and shutil.which("grim"):
            image_bytes = self._grim("grim")

        # ── Strategy 3: pyautogui screenshot (works on X11 and some Wayland) #
        if image_bytes is None:
            try:
                import pyautogui
                import io
                img = pyautogui.screenshot()
                buf = io.BytesIO()
                img.save(buf, format="PNG")
                image_bytes = buf.getvalue()
            except (ImportError, OSError, RuntimeError) as e:
                logger.warning(f"pyautogui gracefully disabled (missing X11/Wayland libs): {e}")
            except Exception as e:
                logger.debug(f"pyautogui screenshot failed: {e}")

        # ── Strategy 4: python-mss (X11) ─────────────────────────────────── #
        if image_bytes is None:
            try:
                import mss
                with mss.mss() as sct:
                    monitor = sct.monitors[1]
                    sct_img = sct.grab(monitor)
                    image_bytes = mss.tools.to_png(sct_img.rgb, sct_img.size)
            except (ImportError, OSError, RuntimeError) as e:
                logger.warning(f"mss fallback gracefully disabled (missing X11 libs): {e}")
            except Exception as e:
                logger.debug(f"mss fallback failed: {e}")

        # ── Strategy 5: scrot (X11) ───────────────────────────────────────── #
        if image_bytes is None and shutil.which("scrot"):
            try:
                subprocess.run(["scrot", out_path], check=True)
                return ToolResult(
                    success=True,
                    output=out_path,
                    metadata={"filepath": out_path, "method": "scrot"},
                )
            except Exception as e:
                logger.error(f"scrot fallback failed: {e}")

        if not image_bytes:
            return ToolResult(
                success=False,
                error=(
                    "Failed to capture screen. No suitable capture method available. "
                    "Install 'grim' (Wayland) or 'scrot' (X11) on the host."
                ),
            )

        with open(out_path, "wb") as f:
            f.write(image_bytes)

        logger.info(f"VisionCaptureTool: screenshot saved → {out_path}")
        return ToolResult(
            success=True,
            output=out_path,
            metadata={"filepath": out_path, "size_bytes": len(image_bytes)},
        )

    @staticmethod
    def _grim(cmd_prefix: str):
        try:
            result = subprocess.run(
                f"{cmd_prefix} -t png -o -",
                shell=True,
                capture_output=True,
                check=True,
            )
            return result.stdout
        except Exception as e:
            logger.warning(f"grim capture failed ({cmd_prefix}): {e}")
            return None
