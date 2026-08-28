import re

with open('axiom/gui/widgets/oobe_wizard.py', 'r') as f:
    content = f.read()

# Replace _build_persona_page
new_persona = """    def _build_persona_page(self):
        page = QWidget()
        l = QVBoxLayout(page)
        
        title = QLabel("Persona: Identity & Tone")
        title.setObjectName("TitleLabel")
        l.addWidget(title)
        l.addSpacing(20)
        
        l.addWidget(QLabel("Presets:"))
        preset_layout = QHBoxLayout()
        presets = [
            ("The Assistant", "AXIOM", "Desktop Agent", "balanced", "standard"),
            ("The Engineer", "AXIOM", "Senior Linux Engineer", "highly_formal", "concise"),
            ("The Buddy", "Buddy", "Helpful Friend", "casual_snarky", "explain_like_im_5")
        ]
        
        for p_name, n, r, t, v in presets:
            btn = QPushButton(p_name)
            btn.clicked.connect(lambda checked, n_=n, r_=r, t_=t, v_=v: self._apply_persona_preset(n_, r_, t_, v_))
            preset_layout.addWidget(btn)
            
        l.addLayout(preset_layout)
        l.addSpacing(30)
        
        from PySide6.QtWidgets import QLineEdit
        self.name_input = QLineEdit()
        self.role_input = QLineEdit()
        self.tone_combo = QComboBox()
        self.tone_combo.addItems(["Highly Formal", "Balanced", "Casual/Snarky"])
        
        self.verbosity_combo = QComboBox()
        self.verbosity_combo.addItems(["Concise", "Standard", "Explain like I'm 5"])
        
        l.addWidget(QLabel("Name:"))
        l.addWidget(self.name_input)
        l.addSpacing(10)
        l.addWidget(QLabel("Role:"))
        l.addWidget(self.role_input)
        l.addSpacing(15)
        l.addWidget(QLabel("Tone:"))
        l.addWidget(self.tone_combo)
        l.addSpacing(15)
        l.addWidget(QLabel("Verbosity:"))
        l.addWidget(self.verbosity_combo)
        
        l.addStretch()
        
        self._apply_persona_preset("AXIOM", "Desktop Agent", "balanced", "standard")
        
        btn = QPushButton("Next")
        btn.setObjectName("PrimaryBtn")
        btn.setFixedWidth(150)
        btn.clicked.connect(lambda: self.stack.setCurrentIndex(3))
        
        h_btn = QHBoxLayout()
        h_btn.addStretch()
        h_btn.addWidget(btn)
        l.addLayout(h_btn)
        
        self.stack.addWidget(page)
        
    def _apply_persona_preset(self, name: str, role: str, tone: str, verbosity: str):
        tone_map = {
            "highly_formal": "Highly Formal",
            "balanced": "Balanced",
            "casual_snarky": "Casual/Snarky"
        }
        verbosity_map = {
            "explain_like_im_5": "Explain like I'm 5",
            "standard": "Standard",
            "concise": "Concise"
        }
        self.name_input.setText(name)
        self.role_input.setText(role)
        self.tone_combo.setCurrentText(tone_map.get(tone, "Balanced"))
        self.verbosity_combo.setCurrentText(verbosity_map.get(verbosity, "Standard"))"""

content = re.sub(r'    def _build_persona_page.*?def _build_directives_page', new_persona + '\n\n    def _build_directives_page', content, flags=re.DOTALL)

# Replace _build_directives_page
new_directives = """    def _build_directives_page(self):
        page = QWidget()
        l = QVBoxLayout(page)
        
        title = QLabel("Advanced Behavior & Directives")
        title.setObjectName("TitleLabel")
        l.addWidget(title)
        
        sub = QLabel("Configure strict operational behaviors.")
        sub.setObjectName("SubtitleLabel")
        l.addWidget(sub)
        l.addSpacing(20)
        
        from PySide6.QtWidgets import QCheckBox
        self.cb_confidence = QCheckBox("Provide Confidence %")
        self.cb_confidence.setStyleSheet("")
        self.cb_explain = QCheckBox("Explain dangerous commands")
        self.cb_explain.setStyleSheet("")
        self.cb_explain.setChecked(True)
        self.cb_emojis = QCheckBox("Use emojis")
        self.cb_emojis.setStyleSheet("")
        
        l.addWidget(self.cb_confidence)
        l.addWidget(self.cb_explain)
        l.addWidget(self.cb_emojis)
        l.addSpacing(20)
        
        l.addWidget(QLabel("Global System Instructions (Directives):"))
        self.directives_input = QPlainTextEdit()
        self.directives_input.setPlaceholderText("e.g., Never hallucinate. Format lists with dashes.")
        l.addWidget(self.directives_input)
        
        l.addStretch()
        
        btn = QPushButton("Finish & Boot AXIOM")
        btn.setObjectName("PrimaryBtn")
        btn.setFixedWidth(200)
        btn.clicked.connect(self._on_finish)
        
        h_btn = QHBoxLayout()
        h_btn.addStretch()
        h_btn.addWidget(btn)
        l.addLayout(h_btn)
        
        self.stack.addWidget(page)

    def _on_finish(self):
        # Build the PersonaConfig dict
        persona = {
            "identity": {
                "name": self.name_input.text(),
                "role": self.role_input.text()
            },
            "communication": {
                "tone": self.tone_combo.currentText().lower(),
                "verbosity": self.verbosity_combo.currentText().lower()
            },
            "behavior": {
                "provide_confidence_percentage": self.cb_confidence.isChecked(),
                "explain_dangerous_commands": self.cb_explain.isChecked(),
                "use_emojis": self.cb_emojis.isChecked()
            },
            "directives": [line.strip() for line in self.directives_input.toPlainText().split('\\n') if line.strip()]
        }
        
        self.config.persona = persona
        self.config.oobe_completed = True
        self.config.save()
        
        self.accept()"""

content = re.sub(r'    def _build_directives_page.*', new_directives, content, flags=re.DOTALL)

with open('axiom/gui/widgets/oobe_wizard.py', 'w') as f:
    f.write(content)
