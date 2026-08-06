"""AXIOM - AI Orchestration Framework.

A local-first AI system with modular architecture, event-driven core,
and support for agents, tools, and plugins.
"""

from axiom.core import Engine, EventBus, Event, Registry, ExecutionContext
from axiom.llm import OllamaClient, OllamaConfig
from axiom.memory import SyncMemoryStore
from axiom.planning import ExecutionPlan, PlanError, PlanStep, StepStatus, TaskPlanner
from axiom.agents import BaseAgent, AgentResult, OrchestratorAgent, ShellAgent
from axiom.tools import (
    BaseTool,
    ToolResult,
    EchoTool,
    ShellTool,
    FileReadTool,
    FileWriteTool,
    SystemInfoTool,
    ToolParameter,
    FileTool,
    ShellCommandTool,
    ReadFileTool,
    WriteFileTool,
    PythonExecTool
)
from axiom.tool_registry import ToolRegistry, ToolRegistryError
from axiom.plugins import BasePlugin, NXBTPlugin, AutomationPlugin
from axiom.config import AxiomConfig, get_config, set_config

__version__ = "8.2.0"
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
    "SyncMemoryStore",
    # Planning
    "ExecutionPlan",
    "PlanError",
    "PlanStep",
    "StepStatus",
    "TaskPlanner",
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
    "ToolParameter",
    "FileTool",
    "ShellCommandTool",
    "ReadFileTool",
    "WriteFileTool",
    "PythonExecTool",
    "ToolRegistry",
    "ToolRegistryError",
    # Plugins
    "BasePlugin",
    "NXBTPlugin",
    "AutomationPlugin",
    # Config
    "AxiomConfig",
    "get_config",
    "set_config",
    # Metadata
    "__version__",
    "__author__",
    "__description__",
]
