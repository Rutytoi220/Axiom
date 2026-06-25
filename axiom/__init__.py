"""AXIOM - AI Orchestration Framework.

A local-first AI system with modular architecture, event-driven core,
and support for agents, tools, and plugins.
"""

from axiom.core import Engine, EventBus, Event, Registry, ExecutionContext
from axiom.llm import OllamaClient, OllamaConfig
from axiom.memory import Database, MemoryManager
from axiom.agents import BaseAgent, AgentResult, OrchestratorAgent, ShellAgent
from axiom.tools import (
    BaseTool,
    ToolResult,
    EchoTool,
    ShellTool,
    FileReadTool,
    FileWriteTool,
    SystemInfoTool
)
from axiom.plugins import BasePlugin, NXBTPlugin, AutomationPlugin
from axiom.config import AxiomConfig, get_config, set_config
from axiom.api import CLI

__version__ = "1.0.0"
__author__ = "AXIOM Team"
__description__ = "Local-first AI orchestration framework"

__all__ = [
    # Core
    "Engine",
    "EventBus",
    "Event",
    "Registry",
    "ExecutionContext",
    # LLM
    "OllamaClient",
    "OllamaConfig",
    # Memory
    "Database",
    "MemoryManager",
    # Agents
    "BaseAgent",
    "AgentResult",
    "OrchestratorAgent",
    "ShellAgent",
    # Tools
    "BaseTool",
    "ToolResult",
    "EchoTool",
    "ShellTool",
    "FileReadTool",
    "FileWriteTool",
    "SystemInfoTool",
    # Plugins
    "BasePlugin",
    "NXBTPlugin",
    "AutomationPlugin",
    # Config
    "AxiomConfig",
    "get_config",
    "set_config",
    # API
    "CLI",
    # Metadata
    "__version__",
    "__author__",
    "__description__",
]
