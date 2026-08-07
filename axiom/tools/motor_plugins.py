import logging
from axiom.tools.base import axiom_tool, ToolResult
from axiom.services.motor_service import MotorService

logger = logging.getLogger("axiom.automation")

@axiom_tool("mouse_click", "Clicks the mouse at the specified (x, y) coordinates on the screen.", {
    "x": {"type": "integer", "description": "The X coordinate in pixels."},
    "y": {"type": "integer", "description": "The Y coordinate in pixels."},
    "button": {"type": "string", "description": "The mouse button to click. Options: 'left', 'right', 'middle'. Defaults to 'left'."}
})
def mouse_click(x: int, y: int, button: str = "left"):
    success, msg = MotorService.mouse_click(x, y, button)
    return ToolResult(success, msg)

@axiom_tool("mouse_move", "Moves the mouse cursor to the specified (x, y) coordinates.", {
    "x": {"type": "integer", "description": "The X coordinate in pixels."},
    "y": {"type": "integer", "description": "The Y coordinate in pixels."}
})
def mouse_move(x: int, y: int):
    success, msg = MotorService.mouse_move(x, y)
    return ToolResult(success, msg)

@axiom_tool("keyboard_type", "Types a string of text using the keyboard.", {
    "text": {"type": "string", "description": "The text to type out."}
})
def keyboard_type(text: str):
    success, msg = MotorService.keyboard_type(text)
    return ToolResult(success, msg)

@axiom_tool("keyboard_press", "Presses a specific keyboard key (e.g., 'enter', 'tab', 'super').", {
    "key": {"type": "string", "description": "The name of the key to press."}
})
def keyboard_press(key: str):
    success, msg = MotorService.keyboard_press(key)
    return ToolResult(success, msg)
