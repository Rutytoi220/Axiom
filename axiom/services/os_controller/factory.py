import os
import shutil
import logging
from axiom.services.os_controller.base import BaseOSController
from axiom.services.os_controller.hyprland import HyprlandController
from axiom.services.os_controller.standard import StandardController
from axiom.services.os_controller.unsupported import UnsupportedController

logger = logging.getLogger(__name__)

def get_os_controller() -> BaseOSController:
    """Auto-detect the OS environment and return the appropriate controller."""
    session_type = os.environ.get("XDG_SESSION_TYPE", "").lower()
    current_desktop = os.environ.get("XDG_CURRENT_DESKTOP", "").lower()

    if session_type == "wayland":
        if "hyprland" in current_desktop:
            logger.info("Detected Wayland+Hyprland. Using HyprlandController.")
            return HyprlandController()
        else:
            # We are on Wayland but not Hyprland. PyAutoGUI doesn't work well here without Xwayland focus.
            # E.g. GNOME, Sway, KDE.
            logger.warning(f"Detected unsupported Wayland compositor: {current_desktop}. Using UnsupportedController.")
            return UnsupportedController()
    else:
        # Fallback for X11, Windows, macOS
        logger.info("Detected standard OS environment (or X11). Using StandardController.")
        return StandardController()
