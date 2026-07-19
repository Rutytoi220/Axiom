"""Interactive Magic DevEx Runner."""

import logging
import uuid
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.status import Status

from axiom.core.events import EventBus
from axiom.core.transaction import WorkspaceTransactionManager
from axiom.indexer.graph_engine import CodeGraphIndex
from axiom.agents.orchestrator_agent import OrchestratorAgent

logger = logging.getLogger(__name__)


class InteractiveWorkflowRunner:
    """Coordinates complex workflow steps and reports progress interactively."""

    def __init__(self, engine: Any, orchestrator: OrchestratorAgent):
        self.engine = engine
        self.orchestrator = orchestrator
        self.bus: EventBus = engine.event_bus
        self.console = Console()

    def run(self, prompt: str) -> None:
        """Run the magic DevEx workflow for a single prompt."""
        self.console.print(f"\n[bold blue]axiom run[/bold blue] '{prompt}'\n")

        # 1. AST Indexing
        with self.console.status("[bold cyan]Indexing AST Workspace...[/bold cyan]") as status:
            index = CodeGraphIndex()
            # We assume current working directory is the workspace root
            workspace_dir = Path.cwd()
            index.index_workspace(workspace_dir)
            num_nodes = len(index.graph.nodes)
            
            # Since the tools are shared, we could technically inject this index into the registry,
            # but for now we just verify we can run the indexer and prime the data.
            self.console.print(f"[green][✓][/green] AST Graph Indexed (Found {num_nodes} nodes)")

        # 2. Transaction Manager
        session_id = str(uuid.uuid4())
        txn = WorkspaceTransactionManager(bus=self.bus, transaction_id=session_id)
        
        # Store for the CLI to use later
        if not hasattr(self.engine, 'active_transactions'):
            self.engine.active_transactions = []
        self.engine.active_transactions.append(txn)

        try:
            txn.begin()
            self.console.print("[green][✓][/green] Transaction Staged (Copy-on-write backup active)")

            # 3. Agent Execution
            with self.console.status("[bold magenta][⏳] OrchestratorAgent analyzing and refactoring...[/bold magenta]") as status:
                # Let the orchestrator run
                result = self.orchestrator.run(prompt, use_tools=True, session_id=session_id)
            
            # Check outcome
            if result.success:
                self.console.print(f"[green][✓][/green] Orchestrator completed successfully.")
                self.console.print("[yellow][!][/yellow] Ready to commit. Run 'axiom commit' to apply.")
                # We intentionally do NOT call txn.commit() here so the user can verify.
            else:
                self.console.print(f"[red][✗][/red] Orchestrator failed: {result.error}")
                txn.rollback()
                raise RuntimeError(result.error)

        except Exception as e:
            # 4. Error Recovery
            if txn._active:
                txn.rollback()
            self.console.print(f"\n[bold red]Task Failed[/bold red]: {e}")
            self.console.print("[green][✓][/green] Workspace safely restored to its prior state.")
            raise
