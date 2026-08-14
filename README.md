# AXIOM: Sovereign AI Operating System & Distributed Swarm (V11)

AXIOM is a PySide6, local-first AI orchestrator equipped with Zero-Trust Tailscale Swarm capabilities, native desktop automation, multimodal vision, and real-time audio. Built for privacy, speed, and deep system integration, AXIOM transitions from a simple chat interface into a fully autonomous distributed AI operating system.

## 🚀 The V11 Feature Matrix

- 🌐 **The Swarm:** Headless Debian node execution over encrypted Tailscale mesh (`100.x.x.x`).
- 👻 **Ghost in the Machine:** Native Linux desktop automation (mouse/keyboard control) via PyAutoGUI with strict failsafes.
- 👁️ **Multimodal Vision:** 5-tier OS-level screen capture (Wayland/X11) routed to local vision models (`qwen3-vl`).
- 🎙️ **Real-Time Audio:** Offline Push-to-Talk via `faster-whisper` and non-blocking `pyttsx3` TTS.

## 📥 Download & Installation (End Users)

> [!IMPORTANT]
> **Ollama Prerequisite**  
> AXIOM is a fully local-first interface and **requires** the Ollama system daemon to be installed and running on your host machine prior to launch. Install it via:  
> ```bash
> curl -fsSL https://ollama.com/install.sh | sh
> ```

[🚀 Download the v11.2.0 AXIOM Linux AppImage](https://github.com/Rutytoi220/Axiom/releases/tag/v11.2.0)

### How to Run:
To launch the universal Linux AppImage, simply run:
```bash
chmod +x AXIOM-v11.2.0-x86_64.AppImage && ./AXIOM-v11.2.0-x86_64.AppImage
```

---

## 🛠️ Advanced Users: Node Setup

To run a headless node for The Swarm over your Tailscale mesh:
```bash
uv run python axiom-node.py
```

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
