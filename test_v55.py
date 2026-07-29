import sys, os
sys.path.insert(0, os.getcwd())

# 1. eBPF Firewall
from axiom.security.ebpf_firewall import AxiomEBPFFirewall
from axiom.core.events import EventBus
eb = EventBus()
fw = AxiomEBPFFirewall(eb)
assert hasattr(fw, "start")
assert hasattr(fw, "stop")
print("eBPF Firewall test passed")

# 2. Temporal Debugger
from axiom.engine.temporal_debugger import TemporalDebuggerService
debugger = TemporalDebuggerService()
def test_func():
    a = 10
    b = 0
    return a / b

res = debugger.execute_with_time_travel(test_func)
assert res["success"] == False
assert len(res["temporal_trace"]) > 0
print("Temporal Debugger test passed")

# 3. Docker Swarm Replication
from axiom.engine.swarm_replicator import DistributedSwarmManager
sm = DistributedSwarmManager(eb)
assert hasattr(sm, "distribute_workload")
print("Docker Swarm Manager test passed")

# 4. GUI Dashboard
from axiom.gui.widgets.firewall_dialog import FirewallControlDialog
import PySide6.QtWidgets as QtWidgets
app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
dlg = FirewallControlDialog()
assert dlg.windowTitle() == "🛡️ eBPF Firewall & Swarm Hub"
print("Firewall Dialog test passed")
