with open('axiom/gui/windows/onboarding.py', 'r') as f:
    content = f.read()

content = content.replace(
    '    def _handoff(self) -> None:\n        self.initialization_complete.emit()\n',
    '    def _handoff(self) -> None:\n        self.initialization_complete.emit()\n        self.accept()\n'
)

with open('axiom/gui/windows/onboarding.py', 'w') as f:
    f.write(content)
