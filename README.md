# AXIOM: Local-First AI Operating System for Linux

AXIOM (`axiom-core`) is a professional, local-first Linux developer utility and AI operating system. Built from the ground up for privacy, speed, and deep system integration, AXIOM acts as a native desktop AI that thinks, remembers, and executes autonomously.

## 🚀 Core Features

- **🧠 Neural Routing & Swarm Architecture**: Dynamically spawns background specialist agents (Coders, Researchers) depending on task complexity using a resilient ReAct Tool Chaining loop.
- **📚 Vector Memory**: Persistent, distributed memory storage via ChromaDB and a dedicated SQLite Session database to effortlessly recall past conversations and deep context.
- **👁️ Sensory Engine**: Built-in, 100% offline Voice capabilities. Use privacy-first Push-to-Talk or JARVIS-style Wake Word ("Hey AXIOM") powered by `faster-whisper` and `openwakeword`, with responses synthesized directly via Linux native `espeak`/`pyttsx3`.
- **💻 Native Linux UI**: A dense, PySide6-powered interface designed for professionals. Dynamic QSS dark-mode theming, terminal-style log output, and a non-intrusive Swarm HUD.

## ⚡ Quickstart

AXIOM is designed to be installed easily into any Python environment.

### 1. Install via pip
```bash
# Clone the repository
git clone https://github.com/Rutytoi220/Axiom.git
cd Axiom

# Install dependencies (or use pip install .)
pip install -r requirements.txt
pip install .
```

### 2. Start the Daemon
AXIOM runs its heavy inference loops, memory routing, and agent swarms in a headless daemon to keep the UI buttery smooth.
```bash
axiomd &
```

### 3. Launch the UI
```bash
axiom
```

On your first launch, the Out-Of-Box Experience (OOBE) will guide you through selecting your UI accent color and setting up your Voice interaction preferences (Push-to-Talk vs Wake Word).

---

*AXIOM v1.0.0 LTS — Developed by the Open-Source Community.*
