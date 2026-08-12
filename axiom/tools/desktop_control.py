"""DesktopAutomationTool — \"Ghost in the Machine\" physical UI control.

Gives the local AXIOM agent the ability to control the host's mouse and
keyboard via pyautogui, with safety guards enforced at init time.

This tool is registered ONLY on the local desktop client, never on headless
Swarm Nodes.
"""
import asyncio
import logging
from functools import partial
from axiom.tools import BaseTool, ToolParameter, ToolResult

logger = logging.getLogger(__name__)

_VALID_ACTIONS = {
    "mouse_move",
    "mouse_click",
    "keyboard_type",
    "keyboard_press",
    "get_screen_size",
}


class DesktopAutomationTool(BaseTool):
    """Allows the LLM to physically control the host's mouse and keyboard."""

    def __init__(self):
        super().__init__(
            tool_id="desktop_control",
            name="DesktopAutomationTool",
            description=(
                "You have physical control over the user's mouse and keyboard on their Linux desktop. "
                "Always call the 'get_screen_size' action first to orient yourself before issuing any "
                "mouse commands. Use this tool cautiously — every action physically moves the cursor "
                "or types on the real screen. The user can abort at any time by moving the mouse to "
                "the top-left corner of the screen (pyautogui failsafe)."
            ),
        )
        self.add_parameter(ToolParameter(
            name="action",
            type="string",
            description=(
                "The action to perform. One of: "
                "'mouse_move' (requires x, y), "
                "'mouse_click' (optional button='left'|'right', optional clicks=1), "
                "'keyboard_type' (requires text), "
                "'keyboard_press' (requires key, e.g. 'enter', 'tab', 'super'), "
                "'get_screen_size' (returns display width and height)."
            ),
        ))
        self.add_parameter(ToolParameter(
            name="x", type="integer",
            description="X coordinate for mouse_move.", required=False,
        ))
        self.add_parameter(ToolParameter(
            name="y", type="integer",
            description="Y coordinate for mouse_move.", required=False,
        ))
        self.add_parameter(ToolParameter(
            name="button", type="string",
            description="Mouse button for mouse_click: 'left' or 'right'. Defaults to 'left'.",
            required=False,
        ))
        self.add_parameter(ToolParameter(
            name="clicks", type="integer",
            description="Number of clicks for mouse_click. Defaults to 1.",
            required=False,
        ))
        self.add_parameter(ToolParameter(
            name="text", type="string",
            description="Text string to type for keyboard_type.", required=False,
        ))
        self.add_parameter(ToolParameter(
            name="key", type="string",
            description="Key name for keyboard_press (e.g. 'enter', 'tab', 'super', 'escape').",
            required=False,
        ))

        # ── Safety configuration ──────────────────────────────────────── #
        self._gui = None  # lazy-loaded

    def _ensure_gui(self):
        """Lazy-import pyautogui and apply safety settings."""
        if self._gui is not None:
            return
        import pyautogui
        pyautogui.FAILSAFE = True
        pyautogui.PAUSE = 0.5
        self._gui = pyautogui
        logger.info("DesktopAutomationTool: pyautogui initialized (FAILSAFE=True, PAUSE=0.5)")

    # ── Dispatcher ────────────────────────────────────────────────────── #

    async def execute(self, action: str, **kwargs) -> ToolResult:
        if action not in _VALID_ACTIONS:
            return ToolResult(
                success=False,
                error=f"Unknown action '{action}'. Valid actions: {', '.join(sorted(_VALID_ACTIONS))}",
            )
        try:
            self._ensure_gui()
            handler = getattr(self, f"_action_{action}")
            return await handler(**kwargs)
        except Exception as e:
            logger.error(f"DesktopAutomationTool error ({action}): {e}")
            return ToolResult(success=False, error=f"Desktop automation error: {e}")

    # ── Action implementations ────────────────────────────────────────── #

    async def _action_get_screen_size(self, **_) -> ToolResult:
        loop = asyncio.get_event_loop()
        size = await loop.run_in_executor(None, self._gui.size)
        return ToolResult(
            success=True,
            output=f"Screen size: {size.width}x{size.height} pixels",
            metadata={"width": size.width, "height": size.height},
        )

    async def _action_mouse_move(self, x: int = None, y: int = None, **_) -> ToolResult:
        if x is None or y is None:
            return ToolResult(success=False, error="mouse_move requires both 'x' and 'y' parameters.")
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, partial(self._gui.moveTo, int(x), int(y), duration=0.3))
        return ToolResult(success=True, output=f"Mouse moved to ({x}, {y})")

    async def _action_mouse_click(self, button: str = "left", clicks: int = 1, **_) -> ToolResult:
        if button not in ("left", "right"):
            return ToolResult(success=False, error="button must be 'left' or 'right'.")
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None, partial(self._gui.click, button=button, clicks=int(clicks))
        )
        return ToolResult(success=True, output=f"Clicked {button} button {clicks} time(s)")

    async def _action_keyboard_type(self, text: str = None, **_) -> ToolResult:
        if not text:
            return ToolResult(success=False, error="keyboard_type requires a 'text' parameter.")
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, partial(self._gui.write, text, interval=0.03))
        return ToolResult(success=True, output=f"Typed {len(text)} characters")

    async def _action_keyboard_press(self, key: str = None, **_) -> ToolResult:
        if not key:
            return ToolResult(success=False, error="keyboard_press requires a 'key' parameter.")
        # Map common aliases
        key_map = {"super": "win", "windows": "win", "cmd": "win"}
        actual_key = key_map.get(key.lower(), key.lower())
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, partial(self._gui.press, actual_key))
        return ToolResult(success=True, output=f"Pressed key: {actual_key}")
