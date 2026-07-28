# AXIOM Quickstart

Welcome to AXIOM v5.3.0! This guide will get you from zero to your first autonomous swarm directive in 5 minutes.

## 1. Installation

AXIOM is optimized for Linux but supports all major platforms.

```bash
# Clone and install in editable mode
git clone https://github.com/rutytoi/axiom.git
cd axiom
pip install -e .
```

Ensure you have **Ollama** installed and running:
```bash
ollama run llama3.1
```

## 2. Launching the Sovereign Kernel

Start the AXIOM master daemon in your terminal:

```bash
axiom --daemon
```

This will initialize the IPC EventBus and mount **AxiomFS** at `~/AxiomFS`.

## 3. Interacting via the HUD

If you are on Wayland (GNOME/KDE/Sway), launch the floating HUD:

```bash
axiom-hud
```

You can now use the overlay to issue voice commands or monitor swarm activity.

## 4. First Directive

Open the AXIOM CLI and ask your first question:

```bash
axiom ask "Analyze the security of the current directory and suggest improvements."
```

AXIOM will:
1. **Decompose** the request.
2. **Sandbox** the analysis in a `bwrap` container.
3. **Reason** using local LLMs.
4. **Present** a verified plan.

## 5. Next Steps

- Explore [**ARCHITECTURE.md**](ARCHITECTURE.md) to understand the kernel internals.
- Check [**SDK_GUIDE.md**](SDK_GUIDE.md) to start building your own AXIOM-powered apps.
