import sys, os
sys.path.insert(0, os.getcwd())
import asyncio

# 1. JIT Generative UI Compiler
from axiom.gui.jit_gui_compiler import GenerativeUIEngine
from PySide6.QtWidgets import QApplication
app = QApplication.instance() or QApplication(sys.argv)

engine = GenerativeUIEngine()
mock_code = """
class MyTestWidget(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        self.btn = QPushButton("Click Me")
        layout.addWidget(self.btn)
"""
widget = engine.compile_widget("MyTestWidget", mock_code)
assert widget is not None
assert hasattr(widget, "btn")
assert widget.btn.text() == "Click Me"
print("JIT Compiler test passed")

# 2. Power Governor
from axiom.services.power_governor import PowerStateService
from axiom.core.events import EventBus
eb = EventBus()
pg = PowerStateService(eb)

state_changed = []
def _on_critical(e):
    state_changed.append(e.data)

eb.subscribe("power.state.critical", _on_critical)
pg.mock_battery_event(percent=15.0, plugged=False)
assert len(state_changed) == 1
assert state_changed[0]["target_model"] == "llama3.2:1b"
print("Power Governor test passed")

# 3. Hardware Interceptor
from axiom.security.hardware_interceptor import HardwareInterceptorService
hi = HardwareInterceptorService(eb)
assert hasattr(hi, "start")
assert hasattr(hi, "stop")
print("Hardware Interceptor test passed")

# 4. Hardware Matrix Dialog
from axiom.gui.widgets.hardware_dialog import HardwareMatrixDialog
dlg = HardwareMatrixDialog(None, eb)
assert dlg.windowTitle() == "🔌 Hardware I/O & Power Matrix"
print("Hardware Dialog test passed")

