from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QLabel, QPushButton, QHBoxLayout, 
    QComboBox, QGraphicsOpacityEffect, QButtonGroup, QSpacerItem, QSizePolicy,
    QFrame
)
from PySide6.QtCore import Qt, QPropertyAnimation, QTimer, QEasingCurve, Slot
from PySide6.QtGui import QFont, QColor
from axiom.config import get_config
from axiom.services.profile_service import ProfileService, ProfileLevel

class OnboardingWindow(QMainWindow):
    def __init__(self, bridge, completion_callback):
        super().__init__()
        self.bridge = bridge
        self.completion_callback = completion_callback
        
        # Borderless, dark-themed
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.resize(900, 600)
        self.setStyleSheet("background-color: #000000; color: #cdd6f4;") # Pure black
        
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        
        self.main_layout = QVBoxLayout(self.central_widget)
        self.main_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.main_layout.setSpacing(30)
        
        # --- Phase 1: Logo ---
        self.logo_label = QLabel("AXIOM")
        self.logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.logo_label.setStyleSheet("font-family: monospace; font-size: 64px; font-weight: 800; color: #10b981; letter-spacing: 0.2em;")
        
        self.logo_effect = QGraphicsOpacityEffect()
        self.logo_effect.setOpacity(0)
        self.logo_label.setGraphicsEffect(self.logo_effect)
        self.main_layout.addWidget(self.logo_label)
        
        # --- Phase 2: Typewriter text ---
        self.dialogue_label = QLabel("")
        self.dialogue_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.dialogue_label.setStyleSheet("font-family: monospace; font-size: 16px; color: #a6adc8;")
        self.dialogue_label.setWordWrap(True)
        self.dialogue_label.setMinimumHeight(60)
        
        self.dialogue_effect = QGraphicsOpacityEffect()
        self.dialogue_effect.setOpacity(1)
        self.dialogue_label.setGraphicsEffect(self.dialogue_effect)
        self.main_layout.addWidget(self.dialogue_label)
        
        # --- Phase 3: Setup Pane ---
        self.setup_pane = QWidget()
        self.setup_layout = QVBoxLayout(self.setup_pane)
        self.setup_layout.setSpacing(20)
        
        # Profile Selector
        prof_layout = QHBoxLayout()
        prof_label = QLabel("UI Profile:")
        prof_label.setStyleSheet("font-size: 14px; font-weight: bold;")
        prof_layout.addWidget(prof_label)
        
        self.btn_group = QButtonGroup(self)
        self.btn_group.setExclusive(True)
        
        self.btn_std = QPushButton("Standard")
        self.btn_adv = QPushButton("Advanced")
        self.btn_dev = QPushButton("Developer")
        
        self.btn_std.setCheckable(True)
        self.btn_adv.setCheckable(True)
        self.btn_dev.setCheckable(True)
        self.btn_std.setChecked(True)
        
        for b in [self.btn_std, self.btn_adv, self.btn_dev]:
            b.setStyleSheet("""
                QPushButton { background-color: #181825; color: #a0a0b0; padding: 10px 20px; border-radius: 4px; border: 1px solid #313244; font-size: 14px;}
                QPushButton:checked { background-color: #10b981; color: #11111b; font-weight: bold; }
            """)
            self.btn_group.addButton(b)
            prof_layout.addWidget(b)
            
        self.setup_layout.addLayout(prof_layout)
        
        # LLM Complexity
        comp_layout = QHBoxLayout()
        comp_label = QLabel("AI Complexity:")
        comp_label.setStyleSheet("font-size: 14px; font-weight: bold;")
        comp_layout.addWidget(comp_label)
        
        self.comp_dropdown = QComboBox()
        self.comp_dropdown.addItems(["Concise", "Detailed", "Academic"])
        self.comp_dropdown.setCurrentText("Detailed")
        self.comp_dropdown.setStyleSheet("""
            QComboBox { background-color: #181825; color: #cdd6f4; padding: 8px; border-radius: 4px; border: 1px solid #313244; font-size: 14px;}
        """)
        comp_layout.addWidget(self.comp_dropdown)
        
        self.setup_layout.addLayout(comp_layout)
        
        # Initialize Button
        self.init_btn = QPushButton("Initialize Local Environment")
        self.init_btn.setStyleSheet("""
            QPushButton { background-color: #89b4fa; color: #11111b; padding: 12px; border-radius: 6px; font-weight: bold; font-size: 16px;}
            QPushButton:hover { background-color: #b4befe; }
        """)
        self.init_btn.clicked.connect(self._on_initialize)
        self.setup_layout.addWidget(self.init_btn)
        
        self.setup_effect = QGraphicsOpacityEffect()
        self.setup_effect.setOpacity(0)
        self.setup_pane.setGraphicsEffect(self.setup_effect)
        self.main_layout.addWidget(self.setup_pane)
        
        # Animation states
        self._typewriter_text = ""
        self._typewriter_index = 0
        self._typewriter_timer = QTimer(self)
        self._typewriter_timer.timeout.connect(self._typewriter_tick)
        
        # Start Sequence
        QTimer.singleShot(500, self._start_phase_1)
        
    def _start_phase_1(self):
        """Fade in Logo."""
        self.anim1 = QPropertyAnimation(self.logo_effect, b"opacity")
        self.anim1.setDuration(2000)
        self.anim1.setStartValue(0.0)
        self.anim1.setEndValue(1.0)
        self.anim1.setEasingCurve(QEasingCurve.Type.InOutSine)
        self.anim1.finished.connect(lambda: QTimer.singleShot(1000, self._start_phase_2))
        self.anim1.start()
        
    def _start_phase_2(self):
        """Typewriter Dialogue."""
        self._typewriter_text = "Hello. I am AXIOM.\nBefore I initialize your local environment, I need to know how to configure your HUD."
        self._typewriter_index = 0
        self._typewriter_timer.start(40) # 40ms per char
        
    @Slot()
    def _typewriter_tick(self):
        if self._typewriter_index < len(self._typewriter_text):
            # Check for pause
            if self._typewriter_text[self._typewriter_index] == "\n":
                self._typewriter_timer.stop()
                QTimer.singleShot(1500, lambda: self._typewriter_timer.start(40))
                
            self.dialogue_label.setText(self._typewriter_text[:self._typewriter_index + 1])
            self._typewriter_index += 1
        else:
            self._typewriter_timer.stop()
            QTimer.singleShot(1000, self._start_phase_3)
            
    def _start_phase_3(self):
        """Fade in setup pane."""
        self.anim3 = QPropertyAnimation(self.setup_effect, b"opacity")
        self.anim3.setDuration(1500)
        self.anim3.setStartValue(0.0)
        self.anim3.setEndValue(1.0)
        self.anim3.setEasingCurve(QEasingCurve.Type.InOutSine)
        self.anim3.start()
        
    @Slot()
    def _on_initialize(self):
        self.init_btn.setEnabled(False)
        self.init_btn.setText("Initializing...")
        
        # Save config
        config = get_config()
        config.first_launch = False
        config.llm_complexity = self.comp_dropdown.currentText().lower()
        
        level = ProfileLevel.STANDARD
        if self.btn_adv.isChecked():
            level = ProfileLevel.ADVANCED
        elif self.btn_dev.isChecked():
            level = ProfileLevel.DEVELOPER
            
        config.ui_profile_level = level.value
        config.save()
        
        # Fade out whole window
        self.fade_out = QPropertyAnimation(self, b"windowOpacity")
        self.fade_out.setDuration(1500)
        self.fade_out.setStartValue(1.0)
        self.fade_out.setEndValue(0.0)
        self.fade_out.setEasingCurve(QEasingCurve.Type.OutQuad)
        self.fade_out.finished.connect(self._handoff)
        self.fade_out.start()
        
    def _handoff(self):
        self.close()
        self.completion_callback()
