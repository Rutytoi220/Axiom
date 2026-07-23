"""Vision Pipeline Substrate for AXIOM v2.

Provides rapid screen-grabbing capabilities augmented with a
Set-of-Mark (SoM) grid for precise spatial reasoning by Vision Language Models.
"""

import base64
from io import BytesIO
import logging
from typing import Optional

try:
    import mss
    from PIL import Image, ImageDraw, ImageFont
except ImportError as e:
    logging.getLogger(__name__).warning(f"VisionPipeline core dependencies missing: {e}")
    mss = None

try:
    import pygetwindow as gw
except (ImportError, NotImplementedError, Exception) as e:
    logging.getLogger(__name__).debug(f"pygetwindow not available (Linux fallback enabled): {e}")
    gw = None

logger = logging.getLogger(__name__)

class VisionPipeline:
    def __init__(self):
        self.is_available = mss is not None

    def _apply_som_grid(self, img: "Image.Image", grid_size: int = 4) -> "Image.Image":
        """Overlay a Set-of-Mark (SoM) coordinate grid onto the image."""
        if not self.is_available:
            return img

        draw = ImageDraw.Draw(img)
        width, height = img.size
        
        cell_width = width / grid_size
        cell_height = height / grid_size
        
        # Draw high-contrast grid lines
        for i in range(1, grid_size):
            x = int(i * cell_width)
            draw.line([(x, 0), (x, height)], fill=(255, 0, 0, 128), width=2)
            y = int(i * cell_height)
            draw.line([(0, y), (width, y)], fill=(255, 0, 0, 128), width=2)
            
        # Draw labels (A1 - D4)
        cols = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        
        # Load a default font or fallback
        try:
            # Pillow's default font might be small, try loading a standard one
            # If unavailable, use the default bitmap font.
            font = ImageFont.load_default()
        except:
            font = None
            
        for row in range(grid_size):
            for col in range(grid_size):
                label = f"{cols[col]}{row + 1}"
                x_center = int(col * cell_width + cell_width / 2)
                y_center = int(row * cell_height + cell_height / 2)
                
                # Draw a high-contrast background box for the text
                # We'll approximate the text size since load_default() doesn't support getsize in newer PIL well
                # We can use textbbox
                try:
                    bbox = draw.textbbox((0, 0), label, font=font)
                    tw = bbox[2] - bbox[0]
                    th = bbox[3] - bbox[1]
                except AttributeError:
                    tw, th = 20, 15
                
                rect_x1 = x_center - tw / 2 - 2
                rect_y1 = y_center - th / 2 - 2
                rect_x2 = x_center + tw / 2 + 2
                rect_y2 = y_center + th / 2 + 2
                
                draw.rectangle([rect_x1, rect_y1, rect_x2, rect_y2], fill=(0, 0, 0, 180))
                draw.text((x_center - tw / 2, y_center - th / 2), label, fill=(255, 255, 255), font=font)

        return img

    def capture_active_window(self, with_grid: bool = True) -> Optional[str]:
        """Capture active window or primary monitor, apply grid, compress and return base64."""
        if not self.is_available:
            logger.error("VisionPipeline dependencies not met.")
            return None

        monitor = None
        
        # Try to find the active window
        try:
            if gw is not None:
                active_win = gw.getActiveWindow()
                if active_win is not None:
                    # bounding box: left, top, width, height
                    monitor = {
                        "top": int(active_win.top),
                        "left": int(active_win.left),
                        "width": int(active_win.width),
                        "height": int(active_win.height)
                    }
        except (ImportError, NotImplementedError, Exception) as e:
            logger.debug(f"Failed to get active window: {e}")

        try:
            with mss.mss() as sct:
                if monitor is None:
                    # Fallback to primary monitor
                    monitor = sct.monitors[1]
                
                # Ensure width/height are positive to avoid MSS errors
                if monitor["width"] <= 0 or monitor["height"] <= 0:
                    monitor = sct.monitors[1]
                    
                sct_img = sct.grab(monitor)
                img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
                
                if with_grid:
                    img = self._apply_som_grid(img)
                    
                # Compress to JPEG
                buffered = BytesIO()
                img.save(buffered, format="JPEG", quality=85)
                return base64.b64encode(buffered.getvalue()).decode("utf-8")
        except Exception as e:
            logger.error(f"Screen capture failed: {e}")
            return None
