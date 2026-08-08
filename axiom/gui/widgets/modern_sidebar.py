from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QCursor
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QFrame, QTreeWidget, QTreeWidgetItem, QSizePolicy, QToolButton
)

class ModeSelector(QFrame):
    """A sleek pill-shaped segmented control for mode selection."""
    mode_changed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("""
            QFrame {
                background-color: #262626;
                border-radius: 16px;
                padding: 4px;
            }
            QPushButton {
                background-color: transparent;
                border: none;
                color: #A0A0A0;
                font-family: 'Inter', sans-serif;
                font-size: 13px;
                font-weight: 500;
                padding: 6px 12px;
                border-radius: 12px;
            }
            QPushButton:hover {
                color: #FFFFFF;
            }
            QPushButton:checked {
                color: #FFFFFF;
                font-weight: bold;
            }
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.btn_basic = QPushButton("Basic")
        self.btn_basic.setCheckable(True)
        self.btn_basic.setCursor(Qt.PointingHandCursor)
        self.btn_basic.clicked.connect(lambda: self.select_mode("basic"))

        self.btn_strict = QPushButton("Strict")
        self.btn_strict.setCheckable(True)
        self.btn_strict.setCursor(Qt.PointingHandCursor)
        self.btn_strict.clicked.connect(lambda: self.select_mode("strict"))

        self.btn_autopilot = QPushButton("Autopilot")
        self.btn_autopilot.setCheckable(True)
        self.btn_autopilot.setCursor(Qt.PointingHandCursor)
        self.btn_autopilot.clicked.connect(lambda: self.select_mode("autopilot"))

        layout.addWidget(self.btn_basic)
        layout.addWidget(self.btn_strict)
        layout.addWidget(self.btn_autopilot)
        
        # Default selection
        self.select_mode("autopilot")

    def select_mode(self, mode: str):
        self.btn_basic.setChecked(mode == "basic")
        self.btn_strict.setChecked(mode == "strict")
        self.btn_autopilot.setChecked(mode == "autopilot")

        # Apply specific accent colors when checked
        self.btn_basic.setStyleSheet("QPushButton:checked { background-color: #4B5563; }")
        self.btn_strict.setStyleSheet("QPushButton:checked { background-color: #D97706; }")
        self.btn_autopilot.setStyleSheet("QPushButton:checked { background-color: #2563EB; }")
        
        self.mode_changed.emit(mode)


class ModernSidebar(QFrame):
    """The sleek, modern left sidebar for navigation and mode selection."""
    
    new_chat_requested = Signal()
    new_project_requested = Signal()
    conversation_selected = Signal(str, str) # project_id, chat_id
    mode_changed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(260)
        self.setStyleSheet("""
            QFrame {
                background-color: #171717;
                border-right: 1px solid #2E2E2E;
            }
            QLabel {
                color: #888888;
                font-family: 'Inter', sans-serif;
                font-size: 12px;
                font-weight: 600;
                text-transform: uppercase;
                margin-top: 10px;
                margin-bottom: 4px;
                border: none;
            }
            QTreeWidget {
                background: transparent;
                border: none;
                color: #D1D5DB;
                font-family: 'Inter', sans-serif;
                font-size: 13px;
                outline: 0;
            }
            QTreeWidget::item {
                padding: 6px 4px;
                border-radius: 6px;
            }
            QTreeWidget::item:hover {
                background-color: #262626;
                color: #FFFFFF;
            }
            QTreeWidget::item:selected {
                background-color: #333333;
                color: #FFFFFF;
                font-weight: bold;
            }
            QTreeWidget::branch:has-children:!has-siblings:closed,
            QTreeWidget::branch:closed:has-children:has-siblings {
                border-image: none;
                image: none;
            }
            QTreeWidget::branch:open:has-children:!has-siblings,
            QTreeWidget::branch:open:has-children:has-siblings {
                border-image: none;
                image: none;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 20, 16, 20)
        layout.setSpacing(10)

        # New Chat Button
        self.btn_new_chat = QPushButton("+ New Chat")
        self.btn_new_chat.setCursor(Qt.PointingHandCursor)
        self.btn_new_chat.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.btn_new_chat.setStyleSheet("""
            QPushButton {
                background-color: #2D2D2D;
                color: #FFFFFF;
                border: 1px solid #404040;
                border-radius: 8px;
                padding: 10px;
                font-family: 'Inter', sans-serif;
                font-size: 14px;
                font-weight: 500;
                text-align: left;
            }
            QPushButton:hover {
                background-color: #383838;
            }
        """)
        self.btn_new_chat.clicked.connect(self.new_chat_requested.emit)
        
        # New Project Button
        self.btn_new_project = QPushButton("+ New Project")
        self.btn_new_project.setCursor(Qt.PointingHandCursor)
        self.btn_new_project.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.btn_new_project.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #A0A0A0;
                border: 1px solid #333333;
                border-radius: 8px;
                padding: 8px 10px;
                font-family: 'Inter', sans-serif;
                font-size: 13px;
                font-weight: 500;
                text-align: left;
            }
            QPushButton:hover {
                background-color: #262626;
                color: #FFFFFF;
                border: 1px solid #404040;
            }
        """)
        self.btn_new_project.clicked.connect(self.new_project_requested.emit)
        
        layout.addWidget(self.btn_new_chat)
        layout.addWidget(self.btn_new_project)

        # Tree Widget for Projects -> Conversations
        layout.addWidget(QLabel("Projects"))
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setIndentation(15)
        layout.addWidget(self.tree)
        
        self.tree.itemSelectionChanged.connect(self._on_item_selected)
        
        layout.addStretch()

        # Mode Selector
        self.mode_selector = ModeSelector()
        self.mode_selector.mode_changed.connect(self.mode_changed.emit)
        layout.addWidget(self.mode_selector)

    def populate_projects(self, projects_with_chats: list):
        """Populate the tree with projects and their conversations.
        Format: [{'project': meta_dict, 'chats': [chat_dict, ...]}, ...]
        """
        self.tree.clear()
        for item_data in projects_with_chats:
            proj = item_data['project']
            chats = item_data['chats']
            
            # Create Project Node
            proj_item = QTreeWidgetItem(self.tree)
            proj_item.setText(0, f"📁 {proj['title']}")
            proj_item.setData(0, Qt.ItemDataRole.UserRole, {"type": "project", "id": proj["id"]})
            
            # Create Chat Nodes
            for chat in chats:
                chat_item = QTreeWidgetItem(proj_item)
                chat_item.setText(0, f"💬 {chat['title']}")
                chat_item.setData(0, Qt.ItemDataRole.UserRole, {"type": "chat", "project_id": proj["id"], "id": chat["id"]})
                
            self.tree.expandItem(proj_item)

    def _on_item_selected(self):
        selected = self.tree.selectedItems()
        if not selected:
            return
            
        item = selected[0]
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if data and data.get("type") == "chat":
            self.conversation_selected.emit(data["project_id"], data["id"])
