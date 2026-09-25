import sys
import os
os.environ["QT_QPA_PLATFORM"] = "offscreen"
from PySide6.QtWidgets import QApplication, QWidget
from PySide6.QtGui import QPixmap
from axiom.gui.styles.theme_manager import get_theme_manager
from axiom.gui.widgets.modern_sidebar import ModernSidebar, SegmentedControl
from axiom.gui.widgets.modern_chat import ModernChatDisplay

app = QApplication(sys.argv)
theme_manager = get_theme_manager()
theme_manager.apply_theme(app, "axiom_pro")

def render_widget(widget, name):
    widget.show()
    widget.resize(widget.sizeHint().width() or 400, widget.sizeHint().height() or 600)
    pix = widget.grab()
    pix.save(f"/tmp/axiom_render_test/{name}.png")
    print(f"Rendered {name}")

class MockParent(QWidget):
    def __init__(self):
        super().__init__()
        self.theme_manager = theme_manager

parent = MockParent()

sidebar = ModernSidebar(parent)
render_widget(sidebar, "sidebar")

seg_control = SegmentedControl(theme_manager)
render_widget(seg_control, "segmented_control")

chat_display = ModernChatDisplay(parent)
render_widget(chat_display, "chat_display")


print("All rendering done.")
sys.exit(0)
