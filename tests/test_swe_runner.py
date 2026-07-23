import pytest
import json
import os
from unittest.mock import Mock, patch, AsyncMock
from axiom.evals.swe_runner import SWERunner, BenchmarkProblem

@pytest.fixture
def mock_engine():
    engine = Mock()
    engine.event_bus = Mock()
    engine.registry = Mock()
    return engine

@pytest.mark.asyncio
async def test_swe_runner_evaluation_loop(mock_engine, tmp_path):
    # Setup mock repo
    repo_dir = tmp_path / "test_repo"
    repo_dir.mkdir()
    
    # Write a dummy problem JSON
    problem_json = tmp_path / "problem.json"
    problem_json.write_text(json.dumps({
        "problem_statement": "Fix the bug",
        "repo_path": str(repo_dir),
        "test_command": "pytest"
    }))
    
    runner = SWERunner(mock_engine)
    
    # Mock LLM to return a valid JSON array of tool calls
    runner.llm.chat = Mock(return_value='[{"name": "write_file", "arguments": {"path": "' + str(repo_dir / "file.py") + '", "content": "print(1)"}}]')
    
    problem = runner.ingest_problem(str(problem_json))
    assert problem.problem_statement == "Fix the bug"
    assert problem.repo_path == str(repo_dir)
    
    # Mock subprocess.run to fail once, then pass
    # Also we need to mock ConsensusEngine
    
    mock_subprocess_run = Mock()
    # First call: fail, Second call: pass
    mock_subprocess_run.side_effect = [
        Mock(returncode=1, stdout="fail", stderr="error"),
        Mock(returncode=0, stdout="pass", stderr="")
    ]
    
    with patch("axiom.evals.swe_runner.subprocess.run", mock_subprocess_run):
        with patch("axiom.evals.swe_runner.ConsensusEngine") as MockConsensusEngine:
            mock_consensus_instance = MockConsensusEngine.return_value
            mock_consensus_instance.run_debate = AsyncMock(return_value=True)
            
            result = await runner.run_evaluation(problem)
            
            assert result["success"] is True
            assert result["retry_count"] == 2
            assert mock_subprocess_run.call_count == 2
            assert mock_consensus_instance.run_debate.call_count == 1
            
            # Verify file was written
            assert (repo_dir / "file.py").exists()
            assert (repo_dir / "file.py").read_text() == "print(1)"
