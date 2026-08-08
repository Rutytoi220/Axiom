import ast

with open('axiom/gui/main_window.py', 'r') as f:
    source = f.read()

tree = ast.parse(source)

methods_to_remove = [
    '_add_sep',
    '_check', # nested async
    '_prompt_update',
    '_update_memory_count',
    '_apply_profile',
    '_submit_task_from_service',
    '_set_auth_mode',
    '_refresh_auth_ui',
    '_add_bubble',
    '_scroll_to_bottom',
]

class UIStripper(ast.NodeTransformer):
    def visit_ClassDef(self, node):
        if node.name == 'MainWindow':
            new_body = []
            for n in node.body:
                if isinstance(n, ast.FunctionDef):
                    if n.name.startswith('_build_') or \
                       n.name.startswith('_open_') or \
                       n.name.startswith('_toggle_') or \
                       n.name.startswith('update_model_label') or \
                       n.name in methods_to_remove:
                        continue
                    
                    if n.name == '__init__':
                        init_body_source = """
def __init__(self, bridge: "AxiomBridge", parent: QWidget | None = None) -> None:
    super().__init__(parent)
    self._bridge = bridge
    self._streaming_bubble = None
    self._streaming_text = ""
    
    self.setWindowTitle("AXIOM Pro — Sovereign AI")
    self.setMinimumSize(800, 600)
    self.resize(1000, 750)
    self.setStyleSheet("QMainWindow { background-color: #121212; }")
    
    from axiom.gui.widgets.modern_chat import ModernChatDisplay
    self._chat_display = ModernChatDisplay(self)
    self.setCentralWidget(self._chat_display)
    
    self._input = self._chat_display.input_bar.input_edit
    self._chat_display.input_bar.message_ready.connect(lambda t: self._on_send())
    
    self._connect_bridge()
    self._init_audio()
    self._init_tray()
    self._init_hotkey()
    
    # Needs to go to the new method
    self._chat_display.add_bubble("assistant", "⚡ AXIOM Pro Online.")
                        """
                        init_ast = ast.parse(init_body_source.strip()).body[0]
                        new_body.append(init_ast)
                        continue
                new_body.append(n)
            node.body = new_body
        return self.generic_visit(node)

tree = UIStripper().visit(tree)
ast.fix_missing_locations(tree)

with open('axiom/gui/main_window.py', 'w') as f:
    f.write(ast.unparse(tree))
