import sys, os
sys.path.insert(0, os.getcwd())
import asyncio

async def test_all():
    # 1. Update Manager
    from axiom.services.updater import AxiomUpdateManager
    updater = AxiomUpdateManager("v5.0.0") # Pretend we are on v5.0.0
    res = await updater.check_for_updates()
    print(f"Update Check Result: {res}")
    # The API might hit rate limits on GitHub actions, so we just check it doesn't crash.
    assert "update_available" in res
    
    # Mock Git Pull
    pull_success = await updater.perform_update(mock_mode=True)
    assert pull_success is True
    print("Update Manager test passed")

    # 2. System Hub Dialog
    from axiom.gui.widgets.system_hub_dialog import SystemHubDialog
    import PySide6.QtWidgets as QtWidgets
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
    
    class MockMainWindow(QtWidgets.QMainWindow):
        pass
        
    dlg = SystemHubDialog(MockMainWindow())
    assert dlg.windowTitle() == "⚙️ AXIOM System Hub"
    print("System Hub test passed")

if __name__ == "__main__":
    asyncio.run(test_all())
