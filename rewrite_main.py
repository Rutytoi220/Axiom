import re

with open("axiom/gui/main_window.py", "r") as f:
    text = f.read()

# 1. Replace _build_central_widget
old_build_central = re.search(r'    def _build_central_widget\(self\) -> None:.*?    def _build_bottom_bar', text, re.DOTALL)
if old_build_central:
    new_build_central = """    def _build_central_widget(self) -> None:
        \"\"\"Central chat viewport using the modern chat UI.\"\"\"
        from axiom.gui.widgets.modern_chat import ModernChatDisplay
        self._chat_display = ModernChatDisplay()
        self.setCentralWidget(self._chat_display)
        
        # Proxy old references so existing logic doesn't crash
        self._input = self._chat_display.input_bar.input_edit
        self._input_layout = self._chat_display.input_bar.layout()
        
        # Re-wire signals
        self._chat_display.input_bar.message_ready.connect(self._on_message_ready)
        
    def _on_message_ready(self, text: str) -> None:
        # Our ModernInputBar emits the text. We will temporarily put it back in self._input 
        # so that _on_send() can read it exactly how it used to, preserving complex attachment logic.
        self._input.setPlainText(text)
        self._on_send()

    def _build_bottom_bar"""
    text = text.replace(old_build_central.group(0), new_build_central)

# 2. Nullify _build_bottom_bar completely since ModernChatDisplay handles it
old_bottom = re.search(r'    def _build_bottom_bar\(self\) -> None:.*?    def _build_sidebar', text, re.DOTALL)
if old_bottom:
    new_bottom = """    def _build_bottom_bar(self) -> None:
        pass  # Handled by ModernChatDisplay now

    def _build_sidebar"""
    text = text.replace(old_bottom.group(0), new_bottom)

# 3. Replace _add_bubble logic
old_add_bubble = re.search(r'    def _add_bubble\(self, role: str, text: str\) -> [a-zA-Z0-9_]+:.*?    def _scroll_to_bottom', text, re.DOTALL)
if old_add_bubble:
    new_add_bubble = """    def _add_bubble(self, role: str, text: str):
        return self._chat_display.add_bubble(role, text)

    def _scroll_to_bottom"""
    text = text.replace(old_add_bubble.group(0), new_add_bubble)

# 4. Remove _scroll_to_bottom
old_scroll = re.search(r'    def _scroll_to_bottom\(self\) -> None:.*?    def update_model_label', text, re.DOTALL)
if old_scroll:
    new_scroll = """    def _scroll_to_bottom(self) -> None:
        self._chat_display._scroll_to_bottom()

    def update_model_label"""
    text = text.replace(old_scroll.group(0), new_scroll)


with open("axiom/gui/main_window.py", "w") as f:
    f.write(text)
