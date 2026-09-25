import os, sys
os.environ["QT_QPA_PLATFORM"] = "offscreen"
from PySide6.QtWidgets import QApplication
from axiom.gui.styles.theme_manager import get_theme_manager
from axiom.gui.widgets.modern_chat import ModernChatDisplay

app = QApplication(sys.argv)
tm = get_theme_manager()
tm.apply_theme(app, "axiom_pro")

widget = ModernChatDisplay()
widget.resize(800, 400)

# Add a mock bubble to test pill shape
widget.add_bubble("user", "Hello, AXIOM! This should be a nice pill shape.")
widget.add_bubble("assistant", "I am fully operational. My buttons are circles.")

widget.show()

# Grab the offscreen render
pixmap = widget.grab()
pixmap.save("/tmp/axiom_render.png", "PNG")
print("Saved /tmp/axiom_render.png")
