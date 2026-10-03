import subprocess
import time
from typing import Dict, Any

class HyprlandActionDispatcher:
    """Dispatches validated AXIOM grounding actions directly to Hyprland via ydotool."""
    
    @staticmethod
    def execute(action_dict: Dict[str, Any]) -> bool:
        action = action_dict.get("action")
        point = action_dict.get("point")
        text = action_dict.get("text")

        if not point or len(point) != 2:
            return False

        x, y = int(point[0]), int(point[1])

        # 1. Move pointer to absolute coordinates
        subprocess.run(["ydotool", "mousemove", "--absolute", str(x), str(y)], check=True)
        time.sleep(0.05)

        # 2. Dispatch action
        if action == "click":
            # 0xC0 = Left click (button 1 down + up)
            subprocess.run(["ydotool", "click", "0xC0"], check=True)
            return True

        elif action == "type":
            # Click to focus input field first, then type text
            subprocess.run(["ydotool", "click", "0xC0"], check=True)
            time.sleep(0.05)
            if text:
                subprocess.run(["ydotool", "type", text], check=True)
            return True

        elif action == "hover":
            # Movement alone satisfies hover
            return True

        return False
