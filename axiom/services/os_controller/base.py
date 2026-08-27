from abc import ABC, abstractmethod

class BaseOSController(ABC):
    """Abstract base class for OS-specific desktop automation."""

    @abstractmethod
    def click(self, x: int, y: int, button: str = "left", clicks: int = 1) -> None:
        """Click at a specific coordinate."""
        pass

    @abstractmethod
    def type_text(self, text: str) -> None:
        """Type a string of text into the currently focused window."""
        pass

    @abstractmethod
    def press_key(self, key: str) -> None:
        """Press a specific key (e.g., 'Return', 'Tab')."""
        pass
