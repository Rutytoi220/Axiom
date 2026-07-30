import sys, os
sys.path.insert(0, os.getcwd())
import asyncio

async def test_all():
    # Test SchedulerDialog UI Instantiation
    from axiom.gui.widgets.scheduler_dialog import SchedulerDialog
    from axiom.core.events import EventBus
    import PySide6.QtWidgets as QtWidgets
    
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
    eb = EventBus()
    
    dlg = SchedulerDialog(scheduler_service=None, parent=None, event_bus=eb)
    
    # Track emitted events
    events = []
    def _on_toggle(e):
        events.append(e)
        
    eb.subscribe("system.toggle.rem_sleep", _on_toggle)
    
    # Manually trigger a button click if possible
    btn = dlg.findChild(QtWidgets.QPushButton)
    if btn:
        btn.click()
        
    assert dlg.windowTitle() == "⏱️ AXIOM Automation Triggers"
    print(f"Captured events: {events}")
    print("Automation UI Refactor test passed")

if __name__ == "__main__":
    asyncio.run(test_all())
