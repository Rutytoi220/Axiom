# AXIOM: Local-First AI Operating System for Linux

AXIOM (`axiom-core`) is a professional, local-first Linux developer utility and AI operating system. Built from the ground up for privacy, speed, and deep system integration, AXIOM acts as a native desktop AI that thinks, remembers, and executes autonomously.

## 🚀 Core Features

- **🧠 Neural Routing & Swarm Architecture**: Dynamically spawns background specialist agents (Coders, Researchers) depending on task complexity using a resilient ReAct Tool Chaining loop.
- **📚 Vector Memory**: Persistent, distributed memory storage via ChromaDB and a dedicated SQLite Session database to effortlessly recall past conversations and deep context.
- **👁️ Sensory Engine**: Built-in, 100% offline Voice capabilities. Use privacy-first Push-to-Talk or JARVIS-style Wake Word ("Hey AXIOM") powered by `faster-whisper` and `openwakeword`, with responses synthesized directly via Linux native `espeak`/`pyttsx3`.
- **💻 Native Linux UI**: A dense, PySide6-powered interface designed for professionals. Dynamic QSS dark-mode theming, terminal-style log output, and a non-intrusive Swarm HUD.

## 📥 Download & Installation (End Users)

> [!IMPORTANT]
> **Ollama Prerequisite**  
> AXIOM is a fully local-first interface and **requires** the Ollama system daemon to be installed and running on your host machine prior to launch. Install it via:  
> ```bash
> curl -fsSL https://ollama.com/install.sh | sh
> ```

[🚀 Download the latest AXIOM Linux AppImage here](https://github.com/Rutytoi220/Axiom/releases/latest)

### How to Run:
1. Download the `AXIOM_Pro-x86_64.AppImage` file.
2. Right-click the file -> **Properties** -> **Permissions** -> Check **"Allow executing file as program"** (or simply run `chmod +x AXIOM_Pro-x86_64.AppImage` in your terminal).
3. Double-click the file to launch the sovereign UI!

---

## 🛠️ Developer Setup (Source Installation)

AXIOM is designed to be installed easily into any Python environment for development.

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

*AXIOM v10.8.0 LTS — Developed by the Open-Source Community.*
