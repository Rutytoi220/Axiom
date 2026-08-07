import logging
logger = logging.getLogger("axiom.automation")

try:
    import pyautogui
    pyautogui.FAILSAFE = True
    HAS_PYAUTOGUI = True
except BaseException as e:
    logger.error(f"Motor Cortex: pyautogui could not be loaded. Automation disabled. ({e})")
    HAS_PYAUTOGUI = False

class MotorService:
    """Service to handle mouse and keyboard automation safely."""

    @staticmethod
    def mouse_move(x: int, y: int, duration: float = 0.5):
        """Move the mouse to a specific coordinate."""
        if not HAS_PYAUTOGUI: return False, "Motor Cortex is offline (pyautogui not loaded)."
        try:
            logger.info(f"Motor Cortex: Moving mouse to ({x}, {y})")
            pyautogui.moveTo(x, y, duration=duration)
            return True, f"Mouse moved to {x}, {y}"
        except pyautogui.FailSafeException:
            logger.warning("Motor Cortex: FailSafeException triggered during move!")
            return False, "FailSafe triggered! Action aborted by user."
        except Exception as e:
            logger.error(f"Motor Cortex: Failed to move mouse: {e}")
            return False, str(e)

    @staticmethod
    def mouse_click(x: int, y: int, button: str = "left"):
        """Click the mouse at a specific coordinate."""
        if not HAS_PYAUTOGUI: return False, "Motor Cortex is offline (pyautogui not loaded)."
        try:
            logger.info(f"Motor Cortex: Clicking {button} at ({x}, {y})")
            pyautogui.click(x=x, y=y, button=button)
            return True, f"Clicked {button} at {x}, {y}"
        except pyautogui.FailSafeException:
            logger.warning("Motor Cortex: FailSafeException triggered during click!")
            return False, "FailSafe triggered! Action aborted by user."
        except Exception as e:
            logger.error(f"Motor Cortex: Failed to click mouse: {e}")
            return False, str(e)

    @staticmethod
    def keyboard_type(text: str, interval: float = 0.05):
        """Type text using the keyboard."""
        if not HAS_PYAUTOGUI: return False, "Motor Cortex is offline (pyautogui not loaded)."
        try:
            logger.info(f"Motor Cortex: Typing text: '{text}'")
            pyautogui.write(text, interval=interval)
            return True, f"Typed text successfully"
        except pyautogui.FailSafeException:
            logger.warning("Motor Cortex: FailSafeException triggered during typing!")
            return False, "FailSafe triggered! Action aborted by user."
        except Exception as e:
            logger.error(f"Motor Cortex: Failed to type text: {e}")
            return False, str(e)

    @staticmethod
    def keyboard_press(key: str):
        """Press a specific key."""
        if not HAS_PYAUTOGUI: return False, "Motor Cortex is offline (pyautogui not loaded)."
        try:
            logger.info(f"Motor Cortex: Pressing key: {key}")
            pyautogui.press(key)
            return True, f"Pressed key {key}"
        except pyautogui.FailSafeException:
            logger.warning("Motor Cortex: FailSafeException triggered during key press!")
            return False, "FailSafe triggered! Action aborted by user."
        except Exception as e:
            logger.error(f"Motor Cortex: Failed to press key: {e}")
            return False, str(e)
