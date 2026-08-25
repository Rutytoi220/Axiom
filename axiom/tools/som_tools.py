"""AXIOM Tools — Vimium-style SoM Click Tool.

Exposes two tools to the LLM orchestrator:

  capture_som_screen
      Captures the current desktop, runs the SoM overlay pipeline, and
      returns the annotated screenshot as a base64 string together with
      the list of visible tags.  The VLM should call this first to "see"
      the screen with tags before issuing any click_tag calls.

  click_tag
      Looks up a 2-letter tag (e.g. "AB") in the SoMManager's active_tags
      table and fires a pyautogui click at the stored (x, y) coordinate.
      Returns a plain-English success/error string to guide the next step.

Both tools share a single module-level SoMManager singleton so the tag table
produced by capture_som_screen remains valid until the next capture.
"""

import asyncio
import base64
import logging
import os
import subprocess
import tempfile
from functools import partial
from pathlib import Path
from typing import Optional

from axiom.tools import BaseTool, ToolParameter, ToolResult
from axiom.vision.som_manager import SoMManager

logger = logging.getLogger(__name__)

# ── Singleton SoMManager ──────────────────────────────────────────────────────
# Shared between both tools so click_tag always sees the tags from the most
# recent capture_som_screen call, no matter which order the orchestrator
# invokes them.
_som: SoMManager = SoMManager()


# ─────────────────────────────────────────────────────────────────────────────
# Tool 1 — capture_som_screen
# ─────────────────────────────────────────────────────────────────────────────

class CaptureSomScreenTool(BaseTool):
    """Capture the desktop, overlay Vimium-style two-letter tags, return image.

    Call this tool before click_tag so the VLM can read the tags from the
    annotated screenshot and decide which element to interact with.

    Returns a JSON object with:
      - image_b64:  Base64-encoded PNG of the annotated screen.
      - tags:       List of all visible tag strings (e.g. ["AA", "AB", "AC"]).
      - tag_count:  Number of detected UI elements.
      - overlay_path: Filesystem path of the saved overlay image (optional use).
    """

    def __init__(self) -> None:
        super().__init__(
            tool_id="capture_som_screen",
            name="CaptureSomScreenTool",
            description=(
                "Captures the current desktop screen and overlays Vimium-style "
                "two-letter tags (AA, AB, AC …) on every detected UI element. "
                "Returns the annotated screenshot as a base64 image and a list "
                "of visible tags. Always call this tool FIRST before click_tag "
                "so you know which tags are available on the current screen."
            ),
        )

    async def execute(self, **_kwargs) -> ToolResult:  # type: ignore[override]
        """Capture screen, run SoM pipeline, return annotated image + tag list."""

        # ── Step 1: Capture raw screenshot ───────────────────────────────────
        raw_path = await self._capture_screen_to_file()
        if raw_path is None:
            return ToolResult(
                success=False,
                error=(
                    "Screen capture failed. Neither 'grim' (Wayland) nor "
                    "'scrot'/'import' (X11) is available, and python-mss "
                    "could not be imported.  Install one of those utilities."
                ),
            )

        # ── Step 2: Reset tags and run overlay ───────────────────────────────
        _som.clear_tags()                     # invalidate tags from last frame
        overlay_path = _som.generate_overlay(
            raw_path,
            output_path="/tmp/axiom_som_overlay.png",
        )

        if overlay_path is None:
            # Overlay failed (missing cv2?) — still return raw screenshot so
            # the VLM is not left completely blind.
            logger.warning("SoM overlay failed; returning raw screenshot.")
            return await self._build_result_from_path(raw_path, overlay_ok=False)

        return await self._build_result_from_path(overlay_path, overlay_ok=True)

    # ── Private helpers ───────────────────────────────────────────────────────

    @staticmethod
    async def _capture_screen_to_file() -> Optional[str]:
        """Capture the desktop to a temp PNG and return the path, or None."""
        out_path = os.path.join(tempfile.gettempdir(), "axiom_som_raw.png")
        loop = asyncio.get_event_loop()

        # Wayland: try grim first.
        if os.environ.get("WAYLAND_DISPLAY"):
            if _which("grim"):
                ok = await loop.run_in_executor(
                    None,
                    partial(
                        subprocess.run,
                        ["grim", out_path],
                        capture_output=True,
                    ),
                )
                if ok.returncode == 0:
                    return out_path

        # X11 / generic: try scrot, then ImageMagick import.
        for cmd in (["scrot", out_path], ["import", "-window", "root", out_path]):
            if _which(cmd[0]):
                ok = await loop.run_in_executor(
                    None,
                    partial(subprocess.run, cmd, capture_output=True),
                )
                if ok.returncode == 0:
                    return out_path

        # Last resort: python-mss (works on Wayland with XWayland fallback).
        try:
            import mss  # type: ignore

            def _mss_grab():
                with mss.mss() as sct:
                    monitor = sct.monitors[1]   # primary monitor
                    sct_img = sct.grab(monitor)
                    mss.tools.to_png(sct_img.rgb, sct_img.size, output=out_path)

            await loop.run_in_executor(None, _mss_grab)
            return out_path
        except Exception as exc:
            logger.error("mss capture failed: %s", exc)

        return None

    @staticmethod
    async def _build_result_from_path(path: str, *, overlay_ok: bool) -> ToolResult:
        """Read the image at path, encode as base64, and build ToolResult."""
        loop = asyncio.get_event_loop()
        try:
            raw_bytes = await loop.run_in_executor(
                None, Path(path).read_bytes
            )
        except OSError as exc:
            return ToolResult(success=False, error=f"Could not read overlay file: {exc}")

        b64 = base64.b64encode(raw_bytes).decode("utf-8")
        tags = sorted(_som.active_tags.keys())   # e.g. ["AA", "AB", "AC", …]

        return ToolResult(
            success=True,
            output={
                "image_b64": b64,
                "format": "png",
                "tags": tags,
                "tag_count": len(tags),
                "overlay_applied": overlay_ok,
                "overlay_path": path,
                "message": (
                    f"Screen captured with {len(tags)} tagged UI elements. "
                    "Read the tags from the image and call click_tag(tag=...) "
                    "to interact with any element."
                    if overlay_ok
                    else
                    "Raw screenshot returned (SoM overlay unavailable). "
                    "Install opencv-python for element tagging."
                ),
            },
            metadata={"tag_map": dict(_som.active_tags)},
        )


# ─────────────────────────────────────────────────────────────────────────────
# Tool 2 — click_tag
# ─────────────────────────────────────────────────────────────────────────────

class SomClickTool(BaseTool):
    """Deterministically click a UI element by its two-letter SoM tag.

    The tag must come from the most recent capture_som_screen call.
    If the tag is not found, you must call capture_som_screen again to
    refresh the tag table before retrying.
    """

    def __init__(self) -> None:
        super().__init__(
            tool_id="click_tag",
            name="SomClickTool",
            description=(
                "Click a UI element identified by its two-letter Set-of-Mark "
                "tag (e.g. 'AB'). The tag must appear in the most recent "
                "capture_som_screen output. If the tag is not found, call "
                "capture_som_screen again to get an updated tag map."
            ),
        )
        self.add_parameter(ToolParameter(
            name="tag",
            type="string",
            description=(
                "The two-letter tag printed on the UI element you want to click "
                "(e.g. 'AA', 'AB', 'BC'). Case-insensitive."
            ),
            required=True,
        ))
        self.add_parameter(ToolParameter(
            name="button",
            type="string",
            description="Which mouse button to use: 'left' (default) or 'right'.",
            required=False,
            default="left",
        ))
        self.add_parameter(ToolParameter(
            name="clicks",
            type="integer",
            description="Number of clicks (1 = single-click, 2 = double-click). Default: 1.",
            required=False,
            default=1,
        ))

        # Lazy-loaded pyautogui reference.
        self._gui = None

    # ── Public execute ────────────────────────────────────────────────────────

    async def execute(  # type: ignore[override]
        self,
        tag: str,
        button: str = "left",
        clicks: int = 1,
        **_kwargs,
    ) -> ToolResult:
        """Look up tag in active_tags and click the stored coordinate."""

        # ── Validate tag format ───────────────────────────────────────────────
        tag = tag.strip().upper()
        if len(tag) != 2 or not tag.isalpha():
            return ToolResult(
                success=False,
                error=(
                    f"Invalid tag '{tag}'. Tags are exactly two uppercase letters "
                    "(e.g. 'AA', 'BC'). Call capture_som_screen to see current tags."
                ),
            )

        # ── Validate button ───────────────────────────────────────────────────
        if button not in ("left", "right"):
            return ToolResult(
                success=False,
                error=f"Invalid button '{button}'. Use 'left' or 'right'.",
            )

        # ── Look up coordinate ────────────────────────────────────────────────
        coord = _som.lookup(tag)
        if coord is None:
            # Give the VLM a clear, actionable error message.
            available = sorted(_som.active_tags.keys())
            return ToolResult(
                success=False,
                error=(
                    f"Tag '{tag}' not found in the current tag map. "
                    f"Available tags: {available if available else 'none — call capture_som_screen first'}. "
                    "The screen may have changed; call capture_som_screen again."
                ),
                metadata={"available_tags": available},
            )

        x, y = coord

        # ── Perform the click ─────────────────────────────────────────────────
        try:
            self._ensure_gui()
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                partial(
                    self._gui.click,
                    x=x, y=y,
                    button=button,
                    clicks=int(clicks),
                    interval=0.05,
                ),
            )
        except RuntimeError as exc:
            # _ensure_gui() raised — desktop automation not available.
            return ToolResult(success=False, error=str(exc))
        except Exception as exc:
            logger.error("SomClickTool: click failed at (%d, %d): %s", x, y, exc)
            return ToolResult(
                success=False,
                error=f"Click at ({x}, {y}) failed: {exc}",
            )

        logger.info(
            "SomClickTool: %s-clicked tag %s at (%d, %d) × %d",
            button, tag, x, y, clicks,
        )
        return ToolResult(
            success=True,
            output=(
                f"Successfully {button}-clicked element '{tag}' at ({x}, {y})"
                + (f" × {clicks}" if clicks > 1 else "") + "."
            ),
            metadata={"tag": tag, "x": x, "y": y, "button": button, "clicks": clicks},
        )

    # ── Private helpers ───────────────────────────────────────────────────────

    def _ensure_gui(self) -> None:
        """Lazy-import pyautogui with FAILSAFE enabled. Raises RuntimeError if unavailable."""
        if self._gui is not None:
            return
        try:
            import pyautogui  # type: ignore
        except (ImportError, OSError, RuntimeError) as exc:
            raise RuntimeError(
                f"Desktop automation (pyautogui) unavailable on this host: {exc}. "
                "This tool only works on local desktop nodes, not headless Swarm Nodes."
            ) from exc

        pyautogui.FAILSAFE = True   # move mouse to top-left corner to abort
        pyautogui.PAUSE = 0.3       # slight delay between actions prevents race conditions
        self._gui = pyautogui
        logger.info("SomClickTool: pyautogui initialised (FAILSAFE=True).")


# ── Utility ───────────────────────────────────────────────────────────────────

def _which(cmd: str) -> bool:
    """Return True if `cmd` exists on PATH."""
    import shutil
    return shutil.which(cmd) is not None


# ── Public singleton accessors (for external code that needs the shared state) ─

def get_som_manager() -> SoMManager:
    """Return the module-level SoMManager singleton."""
    return _som
