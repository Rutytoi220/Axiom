import sys
from PySide6.QtWidgets import QApplication
from axiom.gui.main_window import MainWindow

app = QApplication(sys.argv)
class MockBridge:
    def __init__(self):
        self.client = None

window = MainWindow(bridge=MockBridge())
window._open_scheduler_dialog()
print("Success! UI spawned.")
