import subprocess
import base64
import os
import shutil
import tempfile
from axiom.sdk.plugin import tool

@tool(
    name="capture_screen",
    description="Captures the current desktop screen and returns it as a Base64 encoded string. Crucial for visual UI analysis before taking physical mouse actions."
)
def capture_screen() -> str:
    """
    Captures the current desktop screen and returns it as a Base64 encoded string.
    Crucial for visual UI analysis before taking physical mouse actions.
    """
    try:
        temp_dir = tempfile.gettempdir()
        screenshot_path = os.path.join(temp_dir, "axiom_vision_buffer.png")
        
        if shutil.which("spectacle"):
            subprocess.run(['spectacle', '-b', '-n', '-o', screenshot_path], check=True)
        elif shutil.which("grim"):
            subprocess.run(['grim', '-c', screenshot_path], check=True)
        else:
            return "Failed to capture screen. Neither 'spectacle' nor 'grim' is installed."
        
        with open(screenshot_path, "rb") as image_file:
            encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
            
        os.remove(screenshot_path)
        
        return f"SCREENSHOT_BASE64:{encoded_string}"
        
    except subprocess.CalledProcessError as e:
        return f"Failed to capture screen due to subprocess error: {e}"
    except Exception as e:
        return f"Unexpected error during screen capture: {e}"
