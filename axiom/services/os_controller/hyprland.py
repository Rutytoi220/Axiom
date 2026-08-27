import subprocess
import logging
from axiom.services.os_controller.base import BaseOSController

logger = logging.getLogger(__name__)

class HyprlandController(BaseOSController):
    """OS Controller for Wayland + Hyprland."""

    def click(self, x: int, y: int, button: str = "left", clicks: int = 1) -> None:
        try:
            subprocess.run(["hyprctl", "dispatch", "movecursor", f"{x} {y}"], check=True)
            btn_code = "3" if button == "right" else "1"
            for _ in range(clicks):
                subprocess.run(["hyprctl", "dispatch", "click", btn_code], check=True)
        except subprocess.CalledProcessError as e:
            logger.error("Hyprland click failed: %s", e)
            raise RuntimeError(f"Hyprland click failed: {e}")

    def type_text(self, text: str) -> None:
        try:
            subprocess.run(["wtype", text], check=True)
        except subprocess.CalledProcessError as e:
            logger.error("wtype text failed: %s", e)
            raise RuntimeError(f"wtype text failed: {e}")

    def press_key(self, key: str) -> None:
        try:
            subprocess.run(["wtype", "-k", key], check=True)
        except subprocess.CalledProcessError as e:
            logger.error("wtype key press failed: %s", e)
            raise RuntimeError(f"wtype key press failed: {e}")
