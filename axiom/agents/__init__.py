"""AXIOM agents module for task execution and delegation."""

from axiom.agents.base import BaseAgent, AgentResult
from axiom.agents.simple_base import SimpleBaseAgent
from axiom.agents.echo_agent import EchoAgent
from axiom.agents.regex_router import RegexRouter
from axiom.agents.orchestrator_agent import OrchestratorAgent
from axiom.agents.shell_agent import ShellAgent

__all__ = [
    "BaseAgent",
    "AgentResult",
    "SimpleBaseAgent",
    "EchoAgent",
    "RegexRouter",
    "OrchestratorAgent",
    "ShellAgent",
]
