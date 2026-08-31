# AXIOM Desktop

![PySide6](https://img.shields.io/badge/PySide6-GUI-41CD52?style=for-the-badge&logo=qt&logoColor=white)
![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Ollama](https://img.shields.io/badge/Ollama-Local%20LLMs-FFFFFF?style=for-the-badge&logo=ollama&logoColor=black)
![Tailscale](https://img.shields.io/badge/Tailscale-Mesh%20Network-383938?style=for-the-badge&logo=tailscale&logoColor=white)

**A Sovereign, Local-First AI Desktop OS.**

AXIOM Desktop transforms your machine into an autonomous, locally-hosted AI operating system. Designed for maximum reliability and privacy, it securely executes complex tasks, automates your desktop environment, and scales across your network without relying on cloud APIs.

Getting started is effortless: Upon first launch, an interactive **PySide6 OOBE (Out-Of-Box-Experience) Wizard** will guide you through a seamless setup, configuring your local LLMs (Ollama) and preparing your workspace in minutes.

---

## 📊 Architecture Status Matrix

| Subsystem | Status | Notes |
| :--- | :--- | :--- |
| **ReAct Orchestration** | `IMPLEMENTED` | Core autonomous loop resolving complex tasks. |
| **Theme Engine & JIT UI** | `IMPLEMENTED` | Declarative UI rendering and styling. |
| **bwrap Execution Sandbox** | `IMPLEMENTED` | Strict native Linux namespace isolation for untrusted code. |
| **SQLite Semantic Memory** | `IMPLEMENTED` | WAL-enabled, high-concurrency vector store . |
| **Desktop Automation** | `PARTIAL` | Requires X11 or wlroots/Hyprland. Fails safely on GNOME/KWin Wayland. |
| **P2P LAN Synchronization** | `PARTIAL` | Explicit IP pairing required, no mDNS discovery yet. |
| **OTA Updater & Rollback** | `IMPLEMENTED` | Cryptographic SHA256 + Health Checks & automated rollbacks. |
| **AppImage Distribution** | `IMPLEMENTED` | Aggressive pruning with host C-library checks. |

## 🚀 Planned / Future Enhancements
* **eBPF / Kernel Security**: `PLANNED` - Future kernel-level network and filesystem telemetry.
* **QEMU Micro-VMs**: `PLANNED` - Future hypervisor integration for ultra-secure sandboxing.
* **Universal Wayland**: `PLANNED` - Exploring broader Wayland input injection capabilities.

## ⚔️ The Arsenal (Feature Matrix)

AXIOM's core engines are built for extreme resilience and extensibility:

*   🌐 **The Swarm:** Headless Debian node execution over an encrypted Tailscale mesh (`100.x.x.x`). Securely push/pull payloads and command remote agents across your private network.
*   👻 **Ghost in the Machine:** Native Linux desktop automation with strict failsafes. *(Note: Mouse and Keyboard automation currently requires X11 or a wlroots-based Wayland compositor like Hyprland).*
*   👁️ **Multimodal Vision:** OS-level screen capture directly routed to local vision models (like `qwen3-vl`), granting the AI genuine context of your graphical interface.
*   🎙️ **Real-Time Audio:** Hands-free JARVIS-style wake word detection (`openwakeword`), lightning-fast local transcription (`faster-whisper`), and non-blocking text-to-speech (`pyttsx3`).

*(Plus everything from the V10 architecture: The Dynamic Hub, Declarative Theme Engine, and autonomous ReAct scheduling loops!)*

---

## 🚀 Installation (The AppImage)

AXIOM is designed to be completely zero-config for end-users. We distribute it as an immutable, portable `.AppImage`.

1. **Download:** Grab the latest `AXIOM-*.AppImage` directly from the [GitHub Releases](../../releases/latest) page.
2. **Make it executable:**
   ```bash
   chmod +x AXIOM-*.AppImage
   ```
3. **Double-click** the file from your Linux file manager, or launch it via terminal:
   ```bash
   ./AXIOM-*.AppImage
   ```

That's it! The OOBE Wizard will launch automatically and take it from there.

---

## 💻 Headless CLI

AXIOM can operate completely detached from the GUI for server deployments or Swarm nodes.

```bash
# Check daemon status
./AXIOM-*.AppImage status

# List installed tools
./AXIOM-*.AppImage tool list
```

## 🏗️ Development & Building

We use `uv` and PyInstaller for isolated, declarative builds.

To compile the raw binary and generate your own AppImage locally (requires the new Universal Packager):
```bash
python3 -m axiom.api.cli package --target all
```
*(Or use the legacy script: `bash scripts/build_appimage.sh`)*
