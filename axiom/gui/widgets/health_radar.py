from PySide6.QtWidgets import QDialog, QVBoxLayout, QTextEdit, QLabel
from PySide6.QtCore import Qt, Slot
from axiom.client.ipc_client import AxiomDaemonClient

class HealthRadarDialog(QDialog):
    """UI displaying real-time system health logs and autonomous healing actions."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("❤️ AXIOM System Health Radar")
        self.setMinimumSize(800, 500)
        
        self.client = AxiomDaemonClient()
        self.client.on_event = self._on_event
        
        self._init_ui()
        
    def _init_ui(self):
        layout = QVBoxLayout(self)
        
        header = QLabel("Real-Time Autonomous Healing & Kernel Log")
        header.setStyleSheet("font-weight: bold; color: #10b981; font-size: 16px;")
        layout.addWidget(header)
        
        self.log_viewer = QTextEdit()
        self.log_viewer.setReadOnly(True)
        self.log_viewer.setStyleSheet("""
            QTextEdit {
                background-color: #11111b;
                color: #cdd6f4;
                font-family: monospace;
            }
        """)
        self.log_viewer.append("[SYSTEM] Health Radar Online. Listening for critical kernel/systemd events...")
        layout.addWidget(self.log_viewer)

    @Slot(dict)
    def _on_event(self, event_data: dict):
        topic = event_data.get("topic", "")
        payload = event_data.get("payload", {})
        
        if topic == "os.incident.detected":
            reason = payload.get("reason", "")
            unit = payload.get("unit", "")
            msg = payload.get("message", "")
            self.log_viewer.append(f"\n<span style='color: #f38ba8;'>[🚨 CRITICAL INCIDENT DETECTED]</span>")
            self.log_viewer.append(f"<span style='color: #f38ba8;'>Unit: {unit} | Reason: {reason}</span>")
            self.log_viewer.append(f"<span style='color: #f38ba8;'>Message: {msg}</span>")
            self.log_viewer.append(f"<span style='color: #f9e2af;'>[⚡ AXIOM Self-Healer engaging...]</span>")
            
        elif topic == "os.incident.healed":
            unit = payload.get("unit", "")
            status = payload.get("status", "")
            details = payload.get("details", "")
            color = "#a6e3a1" if status == "SUCCESS" else "#f38ba8"
            self.log_viewer.append(f"\n<span style='color: {color};'>[🛡️ REMEDIATION {status}]</span>")
            self.log_viewer.append(f"<span style='color: {color};'>Unit: {unit}</span>")
            self.log_viewer.append(f"<span style='color: {color};'>Details: {details}</span>")
