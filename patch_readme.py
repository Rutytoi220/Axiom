with open('README.md', 'r') as f:
    content = f.read()

matrix = """## 📊 Architecture Status Matrix

| Subsystem | Status | Notes |
| :--- | :--- | :--- |
| **ReAct Orchestration** | `IMPLEMENTED` | Core autonomous loop resolving complex tasks. |
| **Theme Engine & JIT UI** | `IMPLEMENTED` | Declarative UI rendering and styling. |
| **bwrap Execution Sandbox** | `IMPLEMENTED` | Strict native Linux namespace isolation for untrusted code. |
| **SQLite Semantic Memory** | `IMPLEMENTED` | WAL-enabled, high-concurrency vector store (No GraphRAG). |
| **Desktop Automation** | `PARTIAL` | Requires X11 or wlroots/Hyprland. Fails safely on GNOME/KWin Wayland. |
| **P2P LAN Synchronization** | `PARTIAL` | Explicit IP pairing required, no mDNS discovery yet. |
| **OTA Updater & Rollback** | `IMPLEMENTED` | Cryptographic SHA256 + Health Checks & automated rollbacks. |
| **AppImage Distribution** | `IMPLEMENTED` | Aggressive pruning with host C-library checks. |

## 🚀 Planned / Future Enhancements
* **eBPF / Kernel Security**: `PLANNED` - Future kernel-level network and filesystem telemetry.
* **QEMU Micro-VMs**: `PLANNED` - Future hypervisor integration for ultra-secure sandboxing.
* **Universal Wayland**: `PLANNED` - Exploring broader Wayland input injection capabilities.

"""

content = content.replace("## ⚔️ The Arsenal (Feature Matrix)", matrix + "## ⚔️ The Arsenal (Feature Matrix)")

with open('README.md', 'w') as f:
    f.write(content)
