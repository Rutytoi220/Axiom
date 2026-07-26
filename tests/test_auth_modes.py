import pytest
from unittest.mock import MagicMock, patch
from axiom.config import AxiomConfig, AuthMode, set_config
from axiom.tools import ShellTool, ShellCommandTool

def test_auth_mode_basic_prompts():
    config = AxiomConfig()
    config.auth_mode = AuthMode.BASIC
    set_config(config)

    tool = ShellCommandTool()
    # Replace the Confirm.ask to simulate user typing NO
    with patch('rich.prompt.Confirm.ask', return_value=False) as mock_ask:
        result = tool.execute("echo test")
        assert not result.success
        assert result.error == 'Command execution aborted by user'
        mock_ask.assert_called_once()

def test_auth_mode_autopilot_skips_prompt():
    config = AxiomConfig()
    config.auth_mode = AuthMode.AUTOPILOT
    set_config(config)

    tool = ShellCommandTool()
    with patch('rich.prompt.Confirm.ask') as mock_ask:
        # Mock subprocess to avoid real execution
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout='test', stderr='')
            result = tool.execute("echo test")
            assert result.success
            assert mock_ask.call_count == 0

def test_auth_mode_strict_prompts():
    config = AxiomConfig()
    config.auth_mode = AuthMode.STRICT
    set_config(config)

    tool = ShellCommandTool()
    with patch('rich.prompt.Confirm.ask', return_value=False) as mock_ask:
        result = tool.execute("echo test")
        assert not result.success
        assert result.error == 'Command execution aborted by user'
        mock_ask.assert_called_once()

@pytest.mark.asyncio
async def test_shell_tool_autopilot():
    config = AxiomConfig()
    config.auth_mode = AuthMode.AUTOPILOT
    set_config(config)

    tool = ShellTool()
    with patch('rich.prompt.Confirm.ask') as mock_ask:
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout='test', stderr='')
            result = await tool.execute({"command": "echo test"})
            # If autopilot works, it skips the prompt
            assert mock_ask.call_count == 0
