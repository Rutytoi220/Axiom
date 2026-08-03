import os
import sys
import shutil
import subprocess
from axiom.sdk.plugin import tool

def _is_wayland() -> bool:
    """Check if the current display server is Wayland."""
    is_linux = sys.platform.startswith("linux")
    return is_linux and os.environ.get("WAYLAND_DISPLAY") is not None

@tool(
    name="move_mouse",
    description="Moves the mouse cursor to the specified absolute (x, y) coordinates on the screen."
)
def move_mouse(x: int, y: int) -> str:
    """Moves the mouse cursor to absolute (x, y)."""
    if _is_wayland():
        if not shutil.which("ydotool"):
            return "Error: 'ydotool' is required on Linux Wayland for mouse control. Please install it and ensure the ydotool daemon (ydotoold) is running."
        try:
            # -a for absolute positioning
            subprocess.run(["ydotool", "mousemove", "-a", "-x", str(x), "-y", str(y)], check=True, capture_output=True, text=True)
            return f"Mouse moved to ({x}, {y}) via ydotool."
        except subprocess.CalledProcessError as e:
            return f"Error executing ydotool: {e.stderr}"
    else:
        try:
            import pyautogui
            pyautogui.moveTo(x, y)
            return f"Mouse moved to ({x}, {y}) via pyautogui."
        except ImportError:
            return "Error: 'pyautogui' is required on this platform for mouse control. Please install it."
        except Exception as e:
            return f"Error moving mouse: {str(e)}"

@tool(
    name="click_mouse",
    description="Clicks the mouse. button can be 'left', 'right', or 'middle'."
)
def click_mouse(button: str = 'left') -> str:
    """Clicks the mouse."""
    if _is_wayland():
        if not shutil.which("ydotool"):
            return "Error: 'ydotool' is required on Linux Wayland for mouse control. Please install it and ensure the ydotool daemon (ydotoold) is running."
        try:
            # ydotool uses hex codes for mouse buttons: 0xC0=left, 0xC1=right, 0xC2=middle
            ydotool_btn = "0xC0"
            if button.lower() == "right":
                ydotool_btn = "0xC1"
            elif button.lower() == "middle":
                ydotool_btn = "0xC2"
                
            subprocess.run(["ydotool", "click", ydotool_btn], check=True, capture_output=True, text=True)
            return f"Clicked {button} mouse button via ydotool."
        except subprocess.CalledProcessError as e:
            return f"Error executing ydotool: {e.stderr}"
    else:
        try:
            import pyautogui
            pyautogui.click(button=button)
            return f"Clicked {button} mouse button via pyautogui."
        except ImportError:
            return "Error: 'pyautogui' is required on this platform for mouse control. Please install it."
        except Exception as e:
            return f"Error clicking mouse: {str(e)}"

@tool(
    name="type_text",
    description="Types the given string of text on the keyboard as if it were typed manually."
)
def type_text(text: str) -> str:
    """Types text on the keyboard."""
    if _is_wayland():
        if not shutil.which("ydotool"):
            return "Error: 'ydotool' is required on Linux Wayland for keyboard control. Please install it and ensure the ydotool daemon (ydotoold) is running."
        try:
            subprocess.run(["ydotool", "type", text], check=True, capture_output=True, text=True)
            return "Text typed successfully via ydotool."
        except subprocess.CalledProcessError as e:
            return f"Error executing ydotool: {e.stderr}"
    else:
        try:
            import pyautogui
            pyautogui.write(text)
            return "Text typed successfully via pyautogui."
        except ImportError:
            return "Error: 'pyautogui' is required on this platform for keyboard control. Please install it."
        except Exception as e:
            return f"Error typing text: {str(e)}"
