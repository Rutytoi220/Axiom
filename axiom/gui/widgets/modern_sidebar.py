import os
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QPushButton, QTreeWidget, 
    QTreeWidgetItem, QLabel, QHBoxLayout, QFrame
)
from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QIcon
from axiom.gui.styles.theme_manager import ThemeManager

class SegmentedControl(QFrame):
    value_changed = Signal(str)

    def __init__(self, theme_manager: ThemeManager):
        super().__init__()
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.t = theme_manager.theme
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(4, 4, 4, 4)
        self.layout.setSpacing(4)
        
        self.buttons = []
        self.active_btn = None
        
        for mode in ["Basic", "Strict", "Autopilot"]:
            btn = QPushButton(mode)
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda checked, b=btn: self._on_toggled(b))
            self.buttons.append(btn)
            self.layout.addWidget(btn)
            
        self.buttons[0].setChecked(True)
        self.active_btn = self.buttons[0]
        self._apply_theme()

    def _on_toggled(self, clicked_btn):
        for btn in self.buttons:
            if btn != clicked_btn:
                btn.setChecked(False)
        clicked_btn.setChecked(True)
        self.active_btn = clicked_btn
        self.value_changed.emit(clicked_btn.text().lower())
        self._apply_theme()

    def _apply_theme(self):
        self.setStyleSheet(f"""
            SegmentedControl {{
                background-color: #0E0E17;
                border-radius: 18px;
                border: 1px solid #2D2B3D;
                padding: 2px;
            }}
            QPushButton {{
                background: transparent;
                color: {self.t.colors.text_secondary};
                border: none;
                padding: 6px 12px;
                border-radius: 14px;
                font-family: {self.t.typography.font_main};
                font-size: {self.t.typography.size_sm}px;
                font-weight: 500;
            }}
            QPushButton:checked {{
                background-color: #2D2B3D;
                color: #FFFFFF;
            }}
            QPushButton:hover:!checked {{
                color: {self.t.colors.text_primary};
            }}
        """)

class ModernSidebar(QFrame):
    new_chat_requested = Signal()
    new_project_requested = Signal()
    new_project_chat_requested = Signal(str)
    conversation_selected = Signal(str, str)
    mode_changed = Signal(str)
    chat_selected = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.theme_manager = getattr(parent, 'theme_manager', ThemeManager())
        self.t = self.theme_manager.theme
        
        self.setFixedWidth(280)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(12, 12, 12, 12)
        self.layout.setSpacing(16)

        self.mode_selector = SegmentedControl(self.theme_manager)
        self.mode_selector.value_changed.connect(self.mode_changed.emit)
        self.layout.addWidget(self.mode_selector)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)
        
        self.new_chat_btn = QPushButton("+ New Chat")
        self.new_chat_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.new_chat_btn.setFixedHeight(40)
        self.new_chat_btn.clicked.connect(self.new_chat_requested.emit)
        
        self.new_proj_btn = QPushButton("+ Project")
        self.new_proj_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.new_proj_btn.setFixedHeight(40)
        self.new_proj_btn.clicked.connect(self.new_project_requested.emit)

        btn_layout.addWidget(self.new_chat_btn)
        btn_layout.addWidget(self.new_proj_btn)
        self.layout.addLayout(btn_layout)

        self.tree = QTreeWidget()
        self.tree.setColumnCount(1)
        self.tree.setHeaderHidden(True)
        self.tree.setIndentation(16)
        self.tree.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.tree.setAttribute(Qt.WidgetAttribute.WA_MacShowFocusRect, False)
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._show_context_menu)
        
        self.layout.addWidget(self.tree)
        self.tree.itemSelectionChanged.connect(self._on_tree_selection)

        self.layout.addStretch(1)

        self.settings_btn = QPushButton("⚙ Settings")
        self.settings_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.settings_btn.setFixedHeight(36)
        self.layout.addWidget(self.settings_btn)

        self._apply_theme()

    def _on_tree_selection(self):
        items = self.tree.selectedItems()
        if not items:
            return
        item = items[0]
        if item.parent():
            chat_id = item.data(0, Qt.ItemDataRole.UserRole)
            project_id = item.parent().data(0, Qt.ItemDataRole.UserRole)
            self.conversation_selected.emit(project_id, chat_id)

    def _show_context_menu(self, pos):
        from PySide6.QtWidgets import QMenu
        item = self.tree.itemAt(pos)
        if item and not item.parent():
            project_id = item.data(0, Qt.ItemDataRole.UserRole)
            menu = QMenu(self)
            new_chat_action = menu.addAction("➕ New Chat in Project")
            action = menu.exec(self.tree.mapToGlobal(pos))
            if action == new_chat_action:
                self.new_project_chat_requested.emit(project_id)

    def populate_projects(self, projects_data: list) -> None:
        self.tree.clear()
        
        for p_data in projects_data:
            proj = p_data["project"]
            chats = p_data["chats"]
            
            proj_item = QTreeWidgetItem(self.tree)
            proj_item.setText(0, proj.get("name", "Unnamed Project"))
            proj_item.setData(0, Qt.ItemDataRole.UserRole, proj.get("id"))
            proj_item.setExpanded(True)
            proj_item.setSizeHint(0, QSize(0, 44))
            
            font = proj_item.font(0)
            font.setBold(True)
            proj_item.setFont(0, font)
            proj_item.setFlags(proj_item.flags() & ~Qt.ItemFlag.ItemIsSelectable)
            
            for chat in chats:
                chat_item = QTreeWidgetItem(proj_item)
                chat_item.setText(0, chat.get("title", "New Chat"))
                chat_item.setData(0, Qt.ItemDataRole.UserRole, chat.get("id"))
                chat_item.setSizeHint(0, QSize(0, 44))

    def _apply_theme(self):
        self.setStyleSheet(f"""
            ModernSidebar {{
                background-color: {self.t.colors.bg_base};
                border-right: 1px solid {self.t.colors.border_default};
            }}
            QPushButton {{
                background-color: #1E1E2E;
                color: {self.t.colors.text_primary};
                border: 1px solid {self.t.colors.border_default};
                border-radius: 18px;
                font-family: {self.t.typography.font_main};
                font-size: {self.t.typography.size_sm}px;
                font-weight: 500;
            }}
            QPushButton:hover {{
                background-color: #2D2B3D;
                border: 1px solid {self.t.colors.accent};
            }}
            QTreeView {{
                show-decoration-selected: 0;
                outline: none;
            }}
            QTreeWidget {{
                background: transparent;
                border: none;
                outline: none;
            }}
            QTreeWidget::item {{
                color: {self.t.colors.text_secondary};
                padding: 0px 16px;
                border-radius: 12px;
                margin: 2px 4px;
                border: none;
                outline: none;
            }}
            QTreeWidget::item:hover {{
                background-color: {self.t.colors.bg_surface};
                color: {self.t.colors.text_primary};
            }}
            QTreeWidget::item:selected {{
                background-color: {self.t.colors.bg_surface_active};
                color: {self.t.colors.text_primary};
                border: none;
                outline: none;
            }}
            QTreeWidget::item:focus {{ outline: none; border: none; }}
            QTreeWidget::item:selected:active {{ outline: none; border: none; }}
            QTreeView::branch {{
                background: transparent;
                border: none;
                border-image: none;
                image: none;
            }}
        """)
