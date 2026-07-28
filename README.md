<div align="center">
  <img src="axiom/gui/assets/logo.png" alt="AXIOM Logo" width="200">
  <h1>AXIOM v5.3.0</h1>
  <p><strong>Sovereign, Self-Patching, Multimodal Linux AI Operating System Layer</strong></p>

  [![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
  [![Platform: Linux/Wayland](https://img.shields.io/badge/Platform-Linux%2FWayland-blue.svg)](#)
  [![Python: 3.11+](https://img.shields.io/badge/Python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
  [![Build Status](https://github.com/rutytoi/axiom/actions/workflows/release.yml/badge.svg)](https://github.com/rutytoi/axiom/actions/workflows/release.yml)
  [![Release](https://img.shields.io/badge/Release-v5.3.0-green.svg)](#)
</div>

---

## 🧠 What is AXIOM?

AXIOM is not just another LLM wrapper. It is a **Sovereign AI Operating System Layer** designed to bridge the gap between local LLMs and deep system integration. Evolving from a simple AI client into a self-evolving kernel, AXIOM provides a secure, private, and multimodal environment for autonomous agents to interact with your Linux desktop, hardware, and local network.

By prioritizing **local-first privacy** and **hybrid federation**, AXIOM allows you to leverage the power of massive cloud models (Anthropic Claude, GPT-4) only when necessary, while keeping the majority of reasoning and data processing on your own silicon via **Ollama**.

---

## 🚀 Key Features Matrix

| Feature | Description | Implementation |
| :--- | :--- | :--- |
| 🧠 **Sovereign Kernel** | Master daemon architecture with live code evolution and self-patching. | `axiom.kernel` |
| 🛡️ **Total Isolation** | Rootless `bwrap` containers & disposable QEMU/KVM micro-VMs for tool execution. | `axiom.security` |
| 📁 **AxiomFS** | Semantic FUSE filesystem. Browse GraphRAG memory as dynamic Linux directories. | `axiom.fs` |
| 🎙️ **Jarvis HUD** | Floating Wayland overlay with GPU-accelerated Whisper STT and Piper TTS. | `axiom.gui` |
| 🌐 **P2P Mesh** | Zero-config LAN task offloading and 4-tier LLM routing with budget guards. | `axiom.swarm` |
| 🔌 **IDE Federation** | Native Model Context Protocol (MCP) Server for Cursor, VS Code, and Neovim. | `axiom.server` |
| 🔄 **OTA Updates** | Cryptographic SHA256 release verification with atomic systemd hot-reloading. | `axiom.security` |

---

## 🛠️ Quick Installation

### 🐧 Linux (Recommended)

**Immutable Linux (Bazzite / Fedora Atomic):**
```bash
rpm-ostree install axiom.rpm
```

**Debian / Ubuntu:**
```bash
sudo dpkg -i axiom.deb
```

**Universal AppImage:**
```bash
chmod +x AXIOM.AppImage && ./AXIOM.AppImage
```

### 🪟 Windows
Download the `AXIOM_v5.3.0_Setup.exe` from the [Releases](https://github.com/rutytoi/axiom/releases) page and follow the wizard.

### 🍎 macOS
Download `AXIOM.dmg`, drag to Applications, and allow permissions for Terminal/Accessibility in System Settings.

---

## 📖 Documentation Index

- [**Architecture Deep-Dive**](ARCHITECTURE.md): Technical mapping of the AXIOM Kernel and Swarm consensus.
- [**Contributing Guide**](CONTRIBUTING.md): Setup your dev environment and join the evolution.
- [**Quickstart Guide**](QUICKSTART.md): Get up and running in 5 minutes.
- [**SDK Guide**](SDK_GUIDE.md): Build your own agents and tools on the AXIOM core.

---

## ⚖️ License

AXIOM is released under the **MIT License**. See [LICENSE](LICENSE) for details.
