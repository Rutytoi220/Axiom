import asyncio
from PySide6.QtCore import Qt, Slot, QTimer
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QFrame, QScrollArea, QWidget, QMessageBox
)
from axiom.memory.schedules import ScheduleDatabase
import logging

logger = logging.getLogger(__name__)

class TemporalSchedulerDialog(QDialog):
    """UI for managing active Temporal Engine semantic tasks."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("📅 Temporal Engine")
        self.setMinimumSize(600, 500)
        self.setStyleSheet("""
            QDialog {
                background-color: #1e1e2e;
                color: #cdd6f4;
            }
            QLabel {
                font-size: 14px;
            }
        """)

        self.db = ScheduleDatabase()
        
        layout = QVBoxLayout(self)
        
        # Header
        header = QLabel("<h2>Semantic Scheduler (Temporal Engine)</h2>")
        header.setStyleSheet("color: #fab387; font-weight: bold;")
        layout.addWidget(header)
        
        desc = QLabel("Manage background AI tasks scheduled via natural language.")
        desc.setStyleSheet("color: #a6adc8; margin-bottom: 20px;")
        desc.setWordWrap(True)
        layout.addWidget(desc)

        # Scroll Area for tasks
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        
        self.tasks_container = QWidget()
        self.tasks_layout = QVBoxLayout(self.tasks_container)
        self.tasks_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.scroll.setWidget(self.tasks_container)
        
        layout.addWidget(self.scroll)
        
        # Refresh Button
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        refresh_btn = QPushButton("🔄 Refresh")
        refresh_btn.setStyleSheet("""
            QPushButton {
                background-color: #89b4fa;
                color: #11111b;
                font-weight: bold;
                border-radius: 8px;
                padding: 6px 12px;
            }
        """)
        refresh_btn.clicked.connect(self.load_tasks)
        btn_layout.addWidget(refresh_btn)
        layout.addLayout(btn_layout)

        # Ensure DB is initialized before loading
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.create_task(self.db.initialize())
        else:
            loop.run_until_complete(self.db.initialize())
            
        # Defer load to give layout time
        QTimer.singleShot(100, self.load_tasks)

    @Slot()
    def load_tasks(self):
        """Fetch tasks from DB and populate UI."""
        # Clear layout
        while self.tasks_layout.count():
            child = self.tasks_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
                
        # Fetch data async
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            future = asyncio.run_coroutine_threadsafe(self.db.get_schedules(), loop)
            future.add_done_callback(lambda f: QTimer.singleShot(0, lambda: self._populate_ui(f.result())))
        else:
            tasks = loop.run_until_complete(self.db.get_schedules())
            self._populate_ui(tasks)
            
    def _populate_ui(self, tasks):
        if not tasks:
            empty = QLabel("No semantic tasks scheduled. Tell AXIOM to 'schedule a task...'")
            empty.setStyleSheet("color: #6c7086; font-style: italic;")
            self.tasks_layout.addWidget(empty)
            return
            
        for t in tasks:
            row = QFrame()
            row.setStyleSheet("""
                QFrame {
                    background-color: #313244;
                    border-radius: 8px;
                    padding: 10px;
                    margin-bottom: 10px;
                }
            """)
            row_layout = QHBoxLayout(row)
            
            text_layout = QVBoxLayout()
            t_label = QLabel(f"<b>Prompt:</b> {t['user_prompt']}")
            t_label.setStyleSheet("color: #cdd6f4; font-size: 14px;")
            t_label.setWordWrap(True)
            
            d_label = QLabel(f"<b>Cron:</b> <code>{t['cron_expression']}</code> | <b>Active:</b> {t['is_active']}")
            d_label.setStyleSheet("color: #a6adc8; font-size: 12px;")
            
            text_layout.addWidget(t_label)
            text_layout.addWidget(d_label)
            row_layout.addLayout(text_layout)
            
            row_layout.addStretch()
            
            # Action Buttons
            btn_layout = QVBoxLayout()
            
            toggle_btn = QPushButton("Pause" if t['is_active'] else "Resume")
            toggle_btn.setStyleSheet("""
                QPushButton {
                    background-color: #f9e2af;
                    color: #11111b;
                    font-weight: bold;
                    border-radius: 4px;
                    padding: 4px 8px;
                }
            """ if t['is_active'] else """
                QPushButton {
                    background-color: #a6e3a1;
                    color: #11111b;
                    font-weight: bold;
                    border-radius: 4px;
                    padding: 4px 8px;
                }
            """)
            toggle_btn.clicked.connect(lambda _, t_id=t['id'], state=t['is_active']: self.toggle_task(t_id, not state))
            
            del_btn = QPushButton("Delete")
            del_btn.setStyleSheet("""
                QPushButton {
                    background-color: #f38ba8;
                    color: #11111b;
                    font-weight: bold;
                    border-radius: 4px;
                    padding: 4px 8px;
                }
            """)
            del_btn.clicked.connect(lambda _, t_id=t['id']: self.delete_task(t_id))
            
            btn_layout.addWidget(toggle_btn)
            btn_layout.addWidget(del_btn)
            
            row_layout.addLayout(btn_layout)
            self.tasks_layout.addWidget(row)

    @Slot(str, bool)
    def toggle_task(self, task_id, new_state):
        loop = asyncio.get_event_loop()
        if loop.is_running():
            future = asyncio.run_coroutine_threadsafe(self.db.toggle_schedule(task_id, new_state), loop)
            future.add_done_callback(lambda f: QTimer.singleShot(0, self.load_tasks))
        else:
            loop.run_until_complete(self.db.toggle_schedule(task_id, new_state))
            self.load_tasks()

    @Slot(str)
    def delete_task(self, task_id):
        confirm = QMessageBox.question(
            self, "Delete Task", 
            "Are you sure you want to delete this scheduled task?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if confirm == QMessageBox.StandardButton.Yes:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                future = asyncio.run_coroutine_threadsafe(self.db.delete_schedule(task_id), loop)
                future.add_done_callback(lambda f: QTimer.singleShot(0, self.load_tasks))
            else:
                loop.run_until_complete(self.db.delete_schedule(task_id))
                self.load_tasks()
