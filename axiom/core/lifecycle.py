from enum import Enum

class LifecycleState(str, Enum):
    """Lifecycle states for the AXIOM Daemon and subsystems."""
    BOOTING = "BOOTING"
    GUI_READY = "GUI_READY"
    CORE_INITIALIZING = "CORE_INITIALIZING"
    READY = "READY"
    DEGRADED = "DEGRADED"
