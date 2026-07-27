"""Scheduler Dialog UI for managing background jobs."""

from PySide6.QtCore import Qt, Slot
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QLabel, QInputDialog, QMessageBox, QComboBox, QLineEdit
)

class SchedulerDialog(QDialog):
    """UI for managing scheduled tasks."""

    def __init__(self, scheduler_service, parent=None):
        super().__init__(parent)
        self.scheduler_service = scheduler_service
        self.setWindowTitle("AXIOM Automation - Background Scheduler")
        self.setMinimumSize(700, 400)
        self.setStyleSheet("background-color: #1e1e24; color: #d1d1d6;")

        layout = QVBoxLayout(self)
        
        # Header
        header = QLabel("<b>Background Jobs</b>")
        header.setStyleSheet("font-size: 16px; color: #facc15;")
        layout.addWidget(header)
        
        # Table
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Name", "Prompt", "Type", "Schedule", "Next Run"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.setStyleSheet("""
            QTableWidget { background-color: #2a2a35; border: 1px solid #4b4b60; border-radius: 4px; }
            QHeaderView::section { background-color: #1f1f28; color: #a8a8b3; padding: 4px; border: 1px solid #4b4b60; }
        """)
        layout.addWidget(self.table)
        
        # Toolbar
        toolbar = QHBoxLayout()
        
        self.btn_add = QPushButton("➕ Add Job")
        self.btn_add.setStyleSheet("background-color: #10b981; color: white; padding: 6px; border-radius: 4px; font-weight: bold;")
        self.btn_add.clicked.connect(self._on_add)
        
        self.btn_pause = QPushButton("⏸️ Pause/Resume")
        self.btn_pause.setStyleSheet("background-color: #f59e0b; color: white; padding: 6px; border-radius: 4px; font-weight: bold;")
        self.btn_pause.clicked.connect(self._on_pause)
        
        self.btn_delete = QPushButton("🗑️ Delete")
        self.btn_delete.setStyleSheet("background-color: #ef4444; color: white; padding: 6px; border-radius: 4px; font-weight: bold;")
        self.btn_delete.clicked.connect(self._on_delete)
        
        toolbar.addWidget(self.btn_add)
        toolbar.addWidget(self.btn_pause)
        toolbar.addWidget(self.btn_delete)
        toolbar.addStretch()
        
        layout.addLayout(toolbar)
        
        self._refresh_table()

    def _refresh_table(self):
        self.table.setRowCount(0)
        jobs = self.scheduler_service.get_jobs()
        for i, job in enumerate(jobs):
            self.table.insertRow(i)
            
            # Store job ID in the name item for reference
            name_item = QTableWidgetItem(job["name"])
            name_item.setData(Qt.UserRole, job["id"])
            
            self.table.setItem(i, 0, name_item)
            self.table.setItem(i, 1, QTableWidgetItem(job["prompt"]))
            self.table.setItem(i, 2, QTableWidgetItem(job["trigger_type"]))
            self.table.setItem(i, 3, QTableWidgetItem(job["schedule"]))
            self.table.setItem(i, 4, QTableWidgetItem(job["next_run_time"]))

    def _get_selected_job_id(self):
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            QMessageBox.warning(self, "Selection Error", "Please select a job first.")
            return None
        return self.table.item(rows[0].row(), 0).data(Qt.UserRole)

    @Slot()
    def _on_add(self):
        # We can implement a simple custom dialog or rely on QInputDialog for MVP
        # Using a custom basic dialog layout for adding
        dlg = QDialog(self)
        dlg.setWindowTitle("Add Job")
        l = QVBoxLayout(dlg)
        
        l.addWidget(QLabel("Job Name:"))
        name_input = QLineEdit()
        l.addWidget(name_input)
        
        l.addWidget(QLabel("Prompt Description:"))
        prompt_input = QLineEdit()
        l.addWidget(prompt_input)
        
        l.addWidget(QLabel("Trigger Type:"))
        type_input = QComboBox()
        type_input.addItems(["interval", "cron"])
        l.addWidget(type_input)
        
        l.addWidget(QLabel("Schedule (Seconds for interval, Cron exp for cron):"))
        sched_input = QLineEdit()
        l.addWidget(sched_input)
        
        btn_box = QHBoxLayout()
        ok_btn = QPushButton("Save")
        ok_btn.clicked.connect(dlg.accept)
        btn_box.addWidget(ok_btn)
        l.addLayout(btn_box)
        
        if dlg.exec() == QDialog.Accepted:
            if name_input.text() and prompt_input.text() and sched_input.text():
                try:
                    self.scheduler_service.add_job(
                        name=name_input.text(),
                        prompt=prompt_input.text(),
                        trigger_type=type_input.currentText(),
                        schedule=sched_input.text()
                    )
                    self._refresh_table()
                except Exception as e:
                    QMessageBox.critical(self, "Error", f"Failed to add job: {e}")

    @Slot()
    def _on_pause(self):
        job_id = self._get_selected_job_id()
        if job_id:
            # Check current status
            jobs = self.scheduler_service.get_jobs()
            job = next((j for j in jobs if j["id"] == job_id), None)
            if job:
                if job["next_run_time"] == "Paused":
                    self.scheduler_service.resume_job(job_id)
                else:
                    self.scheduler_service.pause_job(job_id)
                self._refresh_table()

    @Slot()
    def _on_delete(self):
        job_id = self._get_selected_job_id()
        if job_id:
            reply = QMessageBox.question(self, "Delete Job", "Are you sure you want to delete this job?", QMessageBox.Yes | QMessageBox.No)
            if reply == QMessageBox.Yes:
                self.scheduler_service.remove_job(job_id)
                self._refresh_table()
