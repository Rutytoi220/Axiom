import os
import logging
from axiom.services.os_controller.base import BaseOSController
from axiom.services.os_controller.hyprland import HyprlandController
from axiom.services.os_controller.standard import StandardController

logger = logging.getLogger(__name__)

def get_os_controller() -> BaseOSController:
    """Auto-detect the OS environment and return the appropriate controller."""
    session_type = os.environ.get("XDG_SESSION_TYPE", "").lower()
    current_desktop = os.environ.get("XDG_CURRENT_DESKTOP", "").lower()

    if session_type == "wayland" and "hyprland" in current_desktop:
        logger.info("Detected Wayland+Hyprland. Using HyprlandController.")
        return HyprlandController()
    else:
        # Fallback for X11, Windows, macOS, or unknown Wayland
        logger.info("Detected standard OS environment. Using StandardController.")
        return StandardController()
