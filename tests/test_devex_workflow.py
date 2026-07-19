import pytest
from unittest.mock import MagicMock, patch
from axiom.cli.interactive import InteractiveWorkflowRunner
from axiom.agents.base import AgentResult

class MockOrchestrator:
    def __init__(self):
        self.runs = []

    def run(self, prompt, use_tools=True, session_id=None, timeout=None):
        self.runs.append(prompt)
        if "fail" in prompt.lower():
            return AgentResult(success=False, error="Simulated failure", output="")
        return AgentResult(success=True, error=None, output="Did the refactor")

@pytest.fixture
def mock_engine():
    engine = MagicMock()
    engine.event_bus = MagicMock()
    # explicitly clear it so hasattr doesn't return a mock
    del engine.active_transactions
    return engine

def test_interactive_workflow_success(mock_engine):
    orchestrator = MockOrchestrator()
    runner = InteractiveWorkflowRunner(engine=mock_engine, orchestrator=orchestrator)
    
    with patch("axiom.cli.interactive.CodeGraphIndex") as MockIndex, \
         patch("axiom.cli.interactive.WorkspaceTransactionManager") as MockTxn:
        
        runner.run("Fix everything")
        
        # AST graph was indexed
        MockIndex.return_value.index_workspace.assert_called_once()
        
        # Transaction was staged
        MockTxn.return_value.begin.assert_called_once()
        
        # Orchestrator was called
        assert "Fix everything" in orchestrator.runs
        
        # We explicitly leave it uncommitted so user can run axiom commit
        MockTxn.return_value.commit.assert_not_called()
        
        # Store active transaction globally
        assert hasattr(mock_engine, 'active_transactions')
        assert len(mock_engine.active_transactions) == 1

def test_interactive_workflow_failure(mock_engine):
    orchestrator = MockOrchestrator()
    runner = InteractiveWorkflowRunner(engine=mock_engine, orchestrator=orchestrator)
    
    with patch("axiom.cli.interactive.CodeGraphIndex") as MockIndex, \
         patch("axiom.cli.interactive.WorkspaceTransactionManager") as MockTxn:
        
        # Set transaction as active to test rollback logic
        MockTxn.return_value._active = True

        with pytest.raises(RuntimeError, match="Simulated failure"):
            runner.run("Please fail this task")
        
        # Orchestrator was called
        assert "Please fail this task" in orchestrator.runs
        
        # Rollback was called due to failure
        MockTxn.return_value.rollback.assert_called()
