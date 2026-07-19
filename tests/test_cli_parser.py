import pytest
from axiom.api.cli import CLI

@pytest.fixture
def cli():
    return CLI()

def test_precmd_slash_commands(cli):
    """Test that slash commands are routed natively to their underlying functions."""
    assert cli.precmd("/status") == "status"
    assert cli.precmd("/help") == "help"
    assert cli.precmd("/routine add 'test'") == "routine add 'test'"
    assert cli.precmd("/tools") == "tools"

def test_precmd_conversational_default(cli):
    """Test that conversational text is prepended with 'ask '."""
    assert cli.precmd("Hello AXIOM") == "ask Hello AXIOM"
    assert cli.precmd("What is the meaning of life?") == "ask What is the meaning of life?"
    assert cli.precmd("status of the system") == "ask status of the system"

def test_precmd_backward_compatibility(cli):
    """Test that legacy 'ask' and 'run' prefixes are handled cleanly."""
    assert cli.precmd("ask Are you there") == "ask Are you there"
    assert cli.precmd("run magical command") == "run magical command"

def test_precmd_empty_and_eof(cli):
    """Test that empty lines and EOF are unmodified."""
    assert cli.precmd("") == ""
    assert cli.precmd("EOF") == "EOF"
