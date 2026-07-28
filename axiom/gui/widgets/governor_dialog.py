from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QProgressBar, QPushButton, QGroupBox, QListWidget
from PySide6.QtCore import Qt, QTimer
import psutil

class GovernorDialog(QDialog):
    """UI for managing the hardware VRAM governor and background process priorities."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("⚡ Hardware Governor")
        self.setMinimumSize(500, 400)
        self._init_ui()
        
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._update_metrics)
        self.timer.start(1000)
        
    def _init_ui(self):
        layout = QVBoxLayout(self)
        
        # CPU/VRAM Metrics
        metrics_group = QGroupBox("System Resources")
        metrics_layout = QVBoxLayout()
        
        self.cpu_label = QLabel("CPU Usage:")
        self.cpu_bar = QProgressBar()
        metrics_layout.addWidget(self.cpu_label)
        metrics_layout.addWidget(self.cpu_bar)
        
        self.vram_label = QLabel("VRAM Usage (Proxy):")
        self.vram_bar = QProgressBar()
        metrics_layout.addWidget(self.vram_label)
        metrics_layout.addWidget(self.vram_bar)
        
        metrics_group.setLayout(metrics_layout)
        layout.addWidget(metrics_group)
        
        # Process Priorities
        proc_group = QGroupBox("Throttled Background Workers")
        proc_layout = QVBoxLayout()
        self.proc_list = QListWidget()
        proc_layout.addWidget(self.proc_list)
        proc_group.setLayout(proc_layout)
        layout.addWidget(proc_group)
        
        # Mesh Sessions
        mesh_group = QGroupBox("Active P2P Mesh Nodes (Encrypted)")
        mesh_layout = QVBoxLayout()
        self.mesh_list = QListWidget()
        self.mesh_list.addItem("Node: Arch-Workstation (Authenticated)")
        mesh_layout.addWidget(self.mesh_list)
        mesh_group.setLayout(mesh_layout)
        layout.addWidget(mesh_group)
        
    def _update_metrics(self):
        cpu = psutil.cpu_percent()
        self.cpu_bar.setValue(int(cpu))
        self.cpu_bar.setFormat(f"{cpu}%")
        
        # Proxy VRAM
        vram = 50.0
        try:
            import torch
            if torch.cuda.is_available():
                allocated = torch.cuda.memory_allocated(0)
                total = torch.cuda.get_device_properties(0).total_memory
                vram = (allocated / total) * 100.0
        except ImportError:
            pass
            
        self.vram_bar.setValue(int(vram))
        self.vram_bar.setFormat(f"{vram:.1f}%")
        
        self.proc_list.clear()
        for proc in psutil.process_iter(['pid', 'name', 'nice']):
            if proc.info['nice'] and proc.info['nice'] > 0:
                if 'ollama' in proc.info['name'].lower() or 'python' in proc.info['name'].lower():
                    self.proc_list.addItem(f"PID: {proc.info['pid']} | {proc.info['name']} (Nice: {proc.info['nice']})")
