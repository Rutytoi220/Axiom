"""Memory Paging & Cloud Infrastructure Dashboard.

PySide6 dialogue displaying live token paging across the 4 memory tiers
and active AWS Spot Instances with cost estimates.
"""
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QGroupBox,
    QProgressBar,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
)
from PySide6.QtCore import Qt, QTimer
import logging
import random

logger = logging.getLogger(__name__)

class InfrastructureTopologyDialog(QDialog):
    """Visualizes Memory Paging and Cloud Bursting."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("☁️ Infrastructure & Memory Topology")
        self.setMinimumSize(700, 500)
        self._init_ui()
        
        # Simulation timers
        self._mock_timer = QTimer(self)
        self._mock_timer.timeout.connect(self._simulate_telemetry)
        self._mock_timer.start(2000)

    def _init_ui(self):
        layout = QVBoxLayout(self)

        # Header
        header = QLabel("<h2>AXIOM Infrastructure Topology</h2>")
        header.setStyleSheet("color: #89b4fa;")
        layout.addWidget(header)

        # Memory Pager Group
        pager_group = QGroupBox("Hierarchical Memory Pager")
        pager_group.setStyleSheet("QGroupBox { font-weight: bold; color: #cdd6f4; border: 1px solid #45475a; margin-top: 10px; }")
        pager_layout = QVBoxLayout()
        
        # L1
        l1_layout = QHBoxLayout()
        l1_layout.addWidget(QLabel("L1 Active Prompt (Raw):"))
        self.l1_bar = QProgressBar()
        self.l1_bar.setMaximum(128000)
        self.l1_bar.setValue(45000)
        self.l1_bar.setStyleSheet("QProgressBar::chunk { background-color: #f38ba8; }")
        self.l1_label = QLabel("45,000 / 128,000 Tokens")
        l1_layout.addWidget(self.l1_bar)
        l1_layout.addWidget(self.l1_label)
        pager_layout.addLayout(l1_layout)
        
        # L2
        l2_layout = QHBoxLayout()
        l2_layout.addWidget(QLabel("L2 Predictive Cache (Summaries):"))
        self.l2_bar = QProgressBar()
        self.l2_bar.setMaximum(1000)
        self.l2_bar.setValue(120)
        self.l2_bar.setStyleSheet("QProgressBar::chunk { background-color: #fab387; }")
        self.l2_label = QLabel("120 Pages")
        l2_layout.addWidget(self.l2_bar)
        l2_layout.addWidget(self.l2_label)
        pager_layout.addLayout(l2_layout)
        
        # L3
        l3_layout = QHBoxLayout()
        l3_layout.addWidget(QLabel("L3 GraphRAG SQLite (Disk):"))
        self.l3_bar = QProgressBar()
        self.l3_bar.setMaximum(10000)
        self.l3_bar.setValue(4500)
        self.l3_bar.setStyleSheet("QProgressBar::chunk { background-color: #a6e3a1; }")
        self.l3_label = QLabel("4,500 Pages")
        l3_layout.addWidget(self.l3_bar)
        l3_layout.addWidget(self.l3_label)
        pager_layout.addLayout(l3_layout)

        pager_group.setLayout(pager_layout)
        layout.addWidget(pager_group)

        # Cloud Burst Group
        cloud_group = QGroupBox("AWS Cloud-Bursting (Spot Instances)")
        cloud_group.setStyleSheet("QGroupBox { font-weight: bold; color: #cdd6f4; border: 1px solid #45475a; margin-top: 10px; }")
        cloud_layout = QVBoxLayout()
        
        self.cloud_table = QTableWidget(0, 4)
        self.cloud_table.setHorizontalHeaderLabels(["Instance ID", "Type", "Status", "Cost/Hr"])
        self.cloud_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.cloud_table.setStyleSheet("QTableWidget { background-color: #1e1e2e; color: #a6adc8; gridline-color: #313244; }")
        cloud_layout.addWidget(self.cloud_table)
        
        btn_layout = QHBoxLayout()
        self.btn_burst = QPushButton("Trigger Manual Burst (t3.micro)")
        self.btn_burst.clicked.connect(self._trigger_burst)
        btn_layout.addWidget(self.btn_burst)
        cloud_layout.addLayout(btn_layout)
        
        cloud_group.setLayout(cloud_layout)
        layout.addWidget(cloud_group)

    def _simulate_telemetry(self):
        """Simulate live token paging fluctuations."""
        val = self.l1_bar.value() + random.randint(-5000, 10000)
        if val > 128000:
            val = 120000
            # Simulate page out
            l2_val = self.l2_bar.value() + random.randint(10, 50)
            self.l2_bar.setValue(l2_val)
            self.l2_label.setText(f"{l2_val} Pages")
        elif val < 10000:
            val = 20000
            
        self.l1_bar.setValue(val)
        self.l1_label.setText(f"{val:,} / 128,000 Tokens")

    def _trigger_burst(self):
        """Mock triggering a cloud burst."""
        row = self.cloud_table.rowCount()
        self.cloud_table.insertRow(row)
        
        items = [
            QTableWidgetItem(f"i-mock_{random.randint(10000,99999)}"),
            QTableWidgetItem("t3.micro"),
            QTableWidgetItem("Running"),
            QTableWidgetItem("$0.0042")
        ]
        
        for col, item in enumerate(items):
            item.setForeground(Qt.GlobalColor.white)
            if col == 2:
                item.setStyleSheet("color: #a6e3a1; font-weight: bold;")
            self.cloud_table.setItem(row, col, item)
