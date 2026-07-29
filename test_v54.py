import sys, os
sys.path.insert(0, os.getcwd())

# 1. Predictive Caching
from axiom.engine.predictive_cache import PredictiveComputeService
from axiom.core.events import EventBus
eb = EventBus()
pcs = PredictiveComputeService(eb, ".")
assert hasattr(pcs, "query_cache")
print("Predictive Cache test passed")

# 2. ZKP Enclaves & Memory TX
from axiom.engine.memory_tx import TransactionalMemoryManager
tmm = TransactionalMemoryManager()
assert hasattr(tmm, "enclave")
# Check the ZKP mock verification
assert tmm.enclave.verify_zkp_access("proof_contains_TOP_SECRET", "TOP_SECRET") == True
assert tmm.enclave.verify_zkp_access("proof_contains_PUBLIC", "TOP_SECRET") == False
print("ZKP Enclave test passed")

# 3. IoT MQTT
from axiom.tools.iot_mqtt import IoTActuatorTool
tool = IoTActuatorTool()
assert tool.get_info()["name"] == "iot_actuate"
from axiom.agents.iot_agent import PhysicalWorldAgent
agent = PhysicalWorldAgent()
assert "PhysicalWorldAgent" in agent._system_prompt()
print("IoT MQTT test passed")

# 4. GUI Dashboard
from axiom.gui.widgets.iot_dialog import IoTControlDialog
import PySide6.QtWidgets as QtWidgets
app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
dlg = IoTControlDialog()
assert dlg.windowTitle() == "💡 IoT / Physical Environment"
print("IoT Dialog test passed")
