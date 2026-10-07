# AXIOM

A local-first AI assistant and automation layer for Linux.

AXIOM runs local models through Ollama and gives them access to
your desktop through a set of tools. It can control Linux,
interact with websites, use your clipboard/media/network tools,
and fall back to visual interaction when a program doesn't expose
a better interface.

The project is mainly built around Linux + Wayland/Hyprland,
but some components work independently of the desktop environment.

## How it works

AXIOM uses three levels of interaction:

1. Tier 1 — OS / IPC
   Uses deterministic Linux interfaces when possible:
   Hyprland IPC, processes, clipboard, MPRIS, notifications,
   files, network tools, etc.

2. Tier 2 — Browser
   Uses a browser extension bridge to inspect and interact with
   web pages through their DOM/accessibility information.

3. Tier 3 — Vision
   Used as a fallback for graphical applications where AXIOM
   doesn't have a usable semantic interface.

The goal is simple: use the most reliable interface available
instead of making a vision model click everything.

## Current status

| Component | Status |
|---|---|
| Local LLM / Ollama | Working |
| ReAct tool execution | Working |
| Tier 1 tools | Working |
| Browser bridge | Working |
| Vision fallback | Experimental |
| Plugin system | Working |
| Themes | Working |
| Memory | In development |
| Remote/LAN features | In development |

## Requirements

- Linux
- Python 3.11+
- Ollama
- ...
