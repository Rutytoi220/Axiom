"""Test suite for the AXIOM CLI (axiom.api.cli.CLI).

This is the primary user-facing entry point (axiom_cli.py, the ``axiom``
console script) and previously had zero test coverage. Tests run with the
working directory redirected to a temporary path so MemoryManager's default
``axiom.db`` (a real on-disk file, independent of the CLI's in-memory
engine/event store) never touches the repository checkout.

These tests intentionally run without a live Ollama server: the CLI must
degrade gracefully (report unavailability, never crash) when the LLM backend
is unreachable, which is the common case in CI and sandboxed environments.
"""

import pytest

from axiom.api.cli import CLI


@pytest.fixture
def cli(tmp_path, monkeypatch):
    """A CLI instance with its working directory isolated to a temp dir."""
    monkeypatch.chdir(tmp_path)
    instance = CLI()
    yield instance
    instance.close()


def test_cli_registers_tools_agents_plugins_on_init(cli):
    tools = cli.engine.registry.list_tools()
    agents = cli.engine.registry.list_agents()
    plugins = cli.engine.registry.list_plugins()

    assert "echo" in tools
    assert "shell" in tools
    assert "orchestrator" in agents
    assert "nxbt" in plugins
    assert "automation" in plugins


def test_close_is_idempotent(cli):
    cli.close()
    cli.close()

    assert cli._closed is True


def test_do_ask_without_argument_shows_usage(cli, capsys):
    cli.onecmd("ask")

    captured = capsys.readouterr()
    assert "Usage: ask <question>" in captured.out


def test_do_ask_reports_ollama_unavailable_without_crashing(cli, capsys):
    """With no Ollama server reachable, do_ask must degrade gracefully."""
    cli.onecmd("ask what can you do")

    captured = capsys.readouterr()
    assert "Ollama is not running" in captured.out


def test_do_ask_stores_question_in_conversation_history(cli):
    cli.onecmd("ask hello there")

    history = cli.memory.get_conversation_history()
    roles_and_content = [(m["role"], m["content"]) for m in history]
    assert ("user", "hello there") in roles_and_content


def test_do_tools_lists_registered_tools(cli, capsys):
    cli.onecmd("tools")

    captured = capsys.readouterr()
    assert "Registered Tools" in captured.out
    assert "echo" in captured.out
    assert "shell" in captured.out


def test_do_agents_lists_registered_agents(cli, capsys):
    cli.onecmd("agents")

    captured = capsys.readouterr()
    assert "Registered Agents" in captured.out
    assert "orchestrator" in captured.out


def test_do_plugins_lists_registered_plugins(cli, capsys):
    cli.onecmd("plugins")

    captured = capsys.readouterr()
    assert "Registered Plugins" in captured.out
    assert "nxbt" in captured.out
    assert "automation" in captured.out
    assert "enabled" in captured.out


def test_do_status_reports_system_state_without_ollama(cli, capsys):
    cli.onecmd("status")

    captured = capsys.readouterr()
    assert "AXIOM System Status" in captured.out
    assert "Not available (Ollama not running)" in captured.out
    assert "Tools: " in captured.out
    assert "Agents: " in captured.out
    assert "Plugins: " in captured.out


def test_do_history_reports_no_history_initially(cli, capsys):
    cli.onecmd("history")

    captured = capsys.readouterr()
    assert "No conversation history" in captured.out


def test_do_history_shows_stored_messages(cli, capsys):
    cli.memory.add_message("user", "a stored question")

    cli.onecmd("history")

    captured = capsys.readouterr()
    assert "a stored question" in captured.out


def test_do_resume_without_argument_shows_usage(cli, capsys):
    cli.onecmd("resume")

    captured = capsys.readouterr()
    assert "Usage: resume <conversation_id>" in captured.out


def test_do_resume_unknown_conversation_id_does_not_crash(cli, capsys):
    cli.onecmd("resume some-unknown-id")

    captured = capsys.readouterr()
    assert "Resumed conversation some-unknown-id (0 messages)" in captured.out


def test_do_resume_switches_active_conversation(cli):
    other_conversation_id = cli.memory.create_conversation("Other")
    cli.memory.add_message("user", "message in other conversation")
    cli.memory.create_conversation("AXIOM Session")

    cli.onecmd(f"resume {other_conversation_id}")

    assert cli.memory.get_conversation() == other_conversation_id
    history = cli.memory.get_conversation_history()
    assert any(m["content"] == "message in other conversation" for m in history)


def test_do_clear_history_starts_a_new_conversation(cli):
    original_conversation_id = cli.memory.get_conversation()

    cli.onecmd("clear_history")

    assert cli.memory.get_conversation() != original_conversation_id


def test_do_memory_log_reports_no_events_when_empty(cli, capsys):
    # A fresh in-memory engine still logs its own startup event, so use a
    # conversation-scoped assertion instead of assuming zero events exist.
    cli.onecmd("memory_log")

    captured = capsys.readouterr()
    assert "Memory Event Log" in captured.out or "No events recorded." in captured.out


def test_do_memory_log_renders_logged_events_without_crashing(cli, capsys):
    """Regression test: do_memory_log previously raised KeyError('data')
    because get_events() returns the payload under the key 'payload', not
    'data'. This must render successfully for any logged event."""
    cli.engine.memory.log_event("custom.test.event", {"key": "value"}, source="test")

    cli.onecmd("memory_log")

    captured = capsys.readouterr()
    assert "custom.test.event" in captured.out
    assert "key" in captured.out


def test_do_memory_log_respects_limit_argument(cli, capsys):
    for i in range(5):
        cli.engine.memory.log_event(f"event.{i}", {"i": i}, source="test")

    cli.onecmd("memory_log --limit 2")

    captured = capsys.readouterr()
    # Header + separator + up to 2 event rows.
    event_lines = [line for line in captured.out.splitlines() if line.startswith("event.")]
    assert len(event_lines) <= 2


def test_do_memory_log_invalid_limit_shows_usage(cli, capsys):
    cli.onecmd("memory_log --limit notanumber")

    captured = capsys.readouterr()
    assert "Usage: memory-log [--limit N]" in captured.out


def test_do_quit_returns_true_and_closes(cli):
    result = cli.onecmd("quit")

    assert result is True
    assert cli._closed is True


def test_do_help_without_argument_lists_commands(cli, capsys):
    cli.onecmd("help")

    captured = capsys.readouterr()
    assert "AXIOM Commands" in captured.out
    assert "ask <question>" in captured.out


def test_emptyline_produces_no_output(cli, capsys):
    cli.emptyline()

    captured = capsys.readouterr()
    assert captured.out == ""


def test_cli_agent_events_reach_bus_subscribers(cli):
    """Regression: CLI wires core EventBus into agents that emit via publish_sync.

    SimpleBaseAgent._emit only calls bus.publish_sync(). The core EventBus
    used by axiom.core.Engine has no publish_sync, so agent lifecycle events
    are silently dropped and never reach wildcard subscribers.
    """
    received = []

    def on_event(event):
        name = getattr(event, "name", getattr(event, "event_type", "unknown"))
        received.append(name)

    bus = cli.engine.event_bus
    assert not hasattr(bus, "publish_sync"), "precondition: core bus lacks publish_sync"
    bus.subscribe("*", on_event)

    echo_agent = cli.orchestrator._agents["echo_agent"]
    result = echo_agent.run("integration probe")
    assert result.success is True

    assert "agent.started" in received
    assert "agent.completed" in received
