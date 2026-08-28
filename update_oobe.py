import re

with open('axiom/gui/widgets/oobe_wizard.py', 'r') as f:
    content = f.read()

new_persona_and_directives = """    def _build_persona_page(self):
        page = QWidget()
        l = QVBoxLayout(page)
        
        title = QLabel("Persona: Identity & Cognition")
        title.setObjectName("TitleLabel")
        l.addWidget(title)
        l.addSpacing(20)
        
        l.addWidget(QLabel("Presets:"))
        preset_layout = QHBoxLayout()
        presets = [
            ("The Assistant", "AXIOM", "Desktop Agent", "balanced", "standard", "standard", "standard"),
            ("The Engineer", "AXIOM", "Senior Linux Engineer", "highly_formal", "concise", "developer", "heavy_code"),
            ("The Buddy", "Buddy", "Helpful Friend", "casual_snarky", "explain_like_im_5", "layman", "standard")
        ]
        
        for p_name, n, r, t, v, td, fp in presets:
            btn = QPushButton(p_name)
            btn.clicked.connect(lambda checked, n_=n, r_=r, t_=t, v_=v, td_=td, fp_=fp: self._apply_persona_preset(n_, r_, t_, v_, td_, fp_))
            preset_layout.addWidget(btn)
            
        l.addLayout(preset_layout)
        l.addSpacing(30)
        
        from PySide6.QtWidgets import QGridLayout, QLineEdit
        grid = QGridLayout()
        grid.setSpacing(15)
        
        self.name_input = QLineEdit()
        self.role_input = QLineEdit()
        self.tone_combo = QComboBox()
        self.tone_combo.addItems(["Highly Formal", "Balanced", "Casual/Snarky"])
        
        self.verbosity_combo = QComboBox()
        self.verbosity_combo.addItems(["Concise", "Standard", "Explain like I'm 5"])
        
        self.tech_depth_combo = QComboBox()
        self.tech_depth_combo.addItems(["Layman", "Standard", "Developer", "Systems Architect"])
        
        self.formatting_combo = QComboBox()
        self.formatting_combo.addItems(["Standard Markdown", "Heavy Code Blocks", "Bullet-Point Strict"])
        
        grid.addWidget(QLabel("Name:"), 0, 0)
        grid.addWidget(self.name_input, 0, 1)
        grid.addWidget(QLabel("Role:"), 1, 0)
        grid.addWidget(self.role_input, 1, 1)
        grid.addWidget(QLabel("Tone:"), 2, 0)
        grid.addWidget(self.tone_combo, 2, 1)
        grid.addWidget(QLabel("Verbosity:"), 3, 0)
        grid.addWidget(self.verbosity_combo, 3, 1)
        grid.addWidget(QLabel("Technical Depth:"), 4, 0)
        grid.addWidget(self.tech_depth_combo, 4, 1)
        grid.addWidget(QLabel("Formatting:"), 5, 0)
        grid.addWidget(self.formatting_combo, 5, 1)
        
        l.addLayout(grid)
        l.addStretch()
        
        self._apply_persona_preset("AXIOM", "Desktop Agent", "balanced", "standard", "standard", "standard_markdown")
        
        btn = QPushButton("Next")
        btn.setObjectName("PrimaryBtn")
        btn.setFixedWidth(150)
        btn.clicked.connect(lambda: self.stack.setCurrentIndex(3))
        
        h_btn = QHBoxLayout()
        h_btn.addStretch()
        h_btn.addWidget(btn)
        l.addLayout(h_btn)
        
        self.stack.addWidget(page)
        
    def _apply_persona_preset(self, name: str, role: str, tone: str, verbosity: str, tech_depth: str, formatting: str):
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
        tech_map = {
            "layman": "Layman",
            "standard": "Standard",
            "developer": "Developer",
            "systems_architect": "Systems Architect"
        }
        format_map = {
            "standard_markdown": "Standard Markdown",
            "heavy_code": "Heavy Code Blocks",
            "bullet_point": "Bullet-Point Strict"
        }
        self.name_input.setText(name)
        self.role_input.setText(role)
        self.tone_combo.setCurrentText(tone_map.get(tone, "Balanced"))
        self.verbosity_combo.setCurrentText(verbosity_map.get(verbosity, "Standard"))
        self.tech_depth_combo.setCurrentText(tech_map.get(tech_depth, "Standard"))
        self.formatting_combo.setCurrentText(format_map.get(formatting, "Standard Markdown"))

    def _build_directives_page(self):
        page = QWidget()
        l = QVBoxLayout(page)
        
        title = QLabel("Advanced Behavior & Directives")
        title.setObjectName("TitleLabel")
        l.addWidget(title)
        
        sub = QLabel("Configure strict operational behaviors.")
        sub.setObjectName("SubtitleLabel")
        l.addWidget(sub)
        l.addSpacing(20)
        
        from PySide6.QtWidgets import QCheckBox, QGridLayout
        grid = QGridLayout()
        grid.setSpacing(15)
        
        self.initiative_combo = QComboBox()
        self.initiative_combo.addItems(["Reactive (Wait for prompt)", "Proactive (Suggest next steps)"])
        
        self.confirmation_combo = QComboBox()
        self.confirmation_combo.addItems(["Auto-execute all", "Ask before destructive", "Ask before ANY terminal command"])
        self.confirmation_combo.setCurrentText("Ask before destructive")
        
        grid.addWidget(QLabel("Initiative:"), 0, 0)
        grid.addWidget(self.initiative_combo, 0, 1)
        grid.addWidget(QLabel("Confirmation Policy:"), 1, 0)
        grid.addWidget(self.confirmation_combo, 1, 1)
        
        l.addLayout(grid)
        l.addSpacing(15)
        
        self.cb_monologue = QCheckBox("Show Inner Monologue (<thought> block)")
        self.cb_confidence = QCheckBox("Provide Confidence %")
        self.cb_explain = QCheckBox("Explain dangerous commands")
        self.cb_explain.setChecked(True)
        self.cb_emojis = QCheckBox("Use emojis")
        
        l.addWidget(self.cb_monologue)
        l.addWidget(self.cb_confidence)
        l.addWidget(self.cb_explain)
        l.addWidget(self.cb_emojis)
        l.addSpacing(20)
        
        l.addWidget(QLabel("Global System Instructions (Directives):"))
        self.directives_input = QPlainTextEdit()
        self.directives_input.setPlaceholderText("e.g., Never hallucinate. Format lists with dashes.")
        l.addWidget(self.directives_input)
        
        l.addStretch()
        
        btn = QPushButton("Boot AXIOM")
        btn.setObjectName("PrimaryBtn")
        btn.setFixedWidth(200)
        btn.clicked.connect(self._on_finish)
        
        h_btn = QHBoxLayout()
        h_btn.addStretch()
        h_btn.addWidget(btn)
        l.addLayout(h_btn)
        
        self.stack.addWidget(page)

    def _on_finish(self):
        init_map = {
            "Reactive (Wait for prompt)": "reactive",
            "Proactive (Suggest next steps)": "proactive"
        }
        conf_map = {
            "Auto-execute all": "auto_execute",
            "Ask before destructive": "ask_before_destructive",
            "Ask before ANY terminal command": "ask_before_any"
        }
        
        persona = {
            "identity": {
                "name": self.name_input.text(),
                "role": self.role_input.text()
            },
            "communication": {
                "tone": self.tone_combo.currentText().lower(),
                "verbosity": self.verbosity_combo.currentText().lower(),
                "technical_depth": self.tech_depth_combo.currentText().lower(),
                "formatting_preference": self.formatting_combo.currentText().lower()
            },
            "behavior": {
                "initiative": init_map.get(self.initiative_combo.currentText(), "reactive"),
                "confirmation_policy": conf_map.get(self.confirmation_combo.currentText(), "ask_before_destructive"),
                "show_inner_monologue": self.cb_monologue.isChecked(),
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

content = re.sub(r'    def _build_persona_page\(self\):.*?def _on_finish\(self\):.*?self\.accept\(\)', new_persona_and_directives, content, flags=re.DOTALL)

with open('axiom/gui/widgets/oobe_wizard.py', 'w') as f:
    f.write(content)
