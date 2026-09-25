import os
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QPushButton, QTreeWidget, 
    QTreeWidgetItem, QLabel, QHBoxLayout, QFrame
)
from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QIcon
from axiom.gui.styles.theme_manager import ThemeManager

from axiom.gui.styles.squircle import SquirclePath, AnimatedSquircleButton
from PySide6.QtCore import QVariantAnimation, QEasingCurve, QRectF
from PySide6.QtGui import QPainter, QBrush, QPen, QColor

class SegmentedControl(QFrame):
    value_changed = Signal(str)

    def __init__(self, theme_manager: ThemeManager):
        super().__init__()
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setObjectName("segmented_control")
        self.theme_manager = theme_manager
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(4, 4, 4, 4)
        self.layout.setSpacing(4)
        
        self.buttons = []
        self.active_btn = None
        self._pill_x = 4.0
        self._pill_w = 60.0
        
        self._anim = QVariantAnimation(self)
        self._anim.setDuration(180)
        self._anim.setEasingCurve(QEasingCurve.Type.OutExpo)
        self._anim.valueChanged.connect(self._on_anim_val)
        
        modes = ["Basic", "Strict", "Autopilot"]
        for i, mode in enumerate(modes):
            btn = QPushButton(mode)
            btn.setObjectName("segmented_btn")
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setProperty("status", "inactive")
            
            if i == 0:
                btn.setProperty("position", "first")
            elif i == len(modes) - 1:
                btn.setProperty("position", "last")
            else:
                btn.setProperty("position", "middle")
                
            btn.clicked.connect(lambda checked, b=btn: self._on_toggled(b))
            self.buttons.append(btn)
            self.layout.addWidget(btn)
            
        self.buttons[0].setChecked(True)
        self.buttons[0].setProperty("status", "active")
        self.active_btn = self.buttons[0]
        self._apply_theme()

    def _on_anim_val(self, val):
        self._pill_x = val[0]
        self._pill_w = val[1]
        self.update()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.active_btn:
            self._pill_x = float(self.active_btn.x())
            self._pill_w = float(self.active_btn.width())

    def _on_toggled(self, clicked_btn):
        start_x = self._pill_x
        start_w = self._pill_w
        target_x = float(clicked_btn.x())
        target_w = float(clicked_btn.width())

        self._anim.stop()
        self._anim.setStartValue([start_x, start_w])
        self._anim.setEndValue([target_x, target_w])
        self._anim.start()

        for btn in self.buttons:
            if btn != clicked_btn:
                btn.setChecked(False)
                btn.setProperty("status", "inactive")
                btn.style().unpolish(btn)
                btn.style().polish(btn)
        clicked_btn.setChecked(True)
        clicked_btn.setProperty("status", "active")
        clicked_btn.style().unpolish(clicked_btn)
        clicked_btn.style().polish(clicked_btn)
        self.active_btn = clicked_btn
        self.value_changed.emit(clicked_btn.text().lower())
        self._apply_theme()

    def _apply_theme(self):
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        if rect.width() <= 0 or rect.height() <= 0:
            return

        # Background container squircle (n ≈ 3.2, radius 16)
        path = SquirclePath(rect, n=3.2, radius=16.0)
        tokens = getattr(self.theme_manager, 'theme', {}) if hasattr(self, 'theme_manager') and self.theme_manager else {}
        surface = QColor(tokens.get("bg_surface", "#161B22"))
        borders = QColor(tokens.get("borders", "#30363D"))
        primary = QColor(tokens.get("primary", "#8B5CF6"))

        painter.fillPath(path, QBrush(surface))
        pen = QPen(borders, 1.0)
        painter.setPen(pen)
        painter.drawPath(path)

        # Sliding indicator squircle pill (n ≈ 3.2, radius 12)
        if self._pill_w > 0:
            pill_rect = QRectF(self._pill_x, 4.0, self._pill_w, float(self.height()) - 8.0)
            pill_path = SquirclePath(pill_rect, n=3.2, radius=12.0)
            painter.fillPath(pill_path, QBrush(primary))

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
        
        self.setFixedWidth(280)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(12, 12, 12, 12)
        self.layout.setSpacing(16)

        self.mode_selector = SegmentedControl(self.theme_manager)
        self.mode_selector.value_changed.connect(self.mode_changed.emit)
        self.layout.addWidget(self.mode_selector)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)
        
        self.new_chat_btn = AnimatedSquircleButton("+ New Chat", radius=14.0, n=3.2, duration_ms=180)
        self.new_chat_btn.setObjectName("sidebar_action_btn")
        self.new_chat_btn.clicked.connect(self.new_chat_requested.emit)

        self.new_proj_btn = AnimatedSquircleButton("+ Project", radius=14.0, n=3.2, duration_ms=180)
        self.new_proj_btn.setObjectName("sidebar_action_btn")
        self.new_proj_btn.clicked.connect(self.new_project_requested.emit)

        btn_layout.addWidget(self.new_chat_btn)
        btn_layout.addWidget(self.new_proj_btn)
        self.layout.addLayout(btn_layout)

        self.tree = QTreeWidget()
        self.tree.setColumnCount(1)
        self.tree.setHeaderHidden(True)
        self.tree.setRootIsDecorated(False)
        self.tree.setIndentation(10)
        self.tree.setUniformRowHeights(True)
        self.tree.setAnimated(True)
        self.tree.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.tree.setAttribute(Qt.WidgetAttribute.WA_MacShowFocusRect, False)
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._show_context_menu)

        self.layout.addWidget(self.tree)
        self.tree.itemSelectionChanged.connect(self._on_tree_selection)

        self.layout.addStretch(1)

        self.hub_btn = AnimatedSquircleButton("⬡  AXIOM Hub", radius=14.0, n=3.2, duration_ms=180)
        self.hub_btn.setObjectName("sidebar_action_btn")
        self.layout.addWidget(self.hub_btn)

        self.settings_btn = AnimatedSquircleButton("⚙  Settings", radius=14.0, n=3.2, duration_ms=180)
        self.settings_btn.setObjectName("sidebar_action_btn")
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
            new_chat_action = menu.addAction("+ New Chat in Project")
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
        pass
