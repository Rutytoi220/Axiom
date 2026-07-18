"""Security & behaviour tests for OS Perception Taps (RFC-003 Phase 2).

These tests verify the zero-trust security guarantees:
- Password manager processes are silently blocked with zero data leakage.
- Scrubber correctly masks API keys, tokens, and PEM blocks.
- Taps respect their independent config guards (OFF by default).
- IntentEngine correctly classifies clipboard content.
"""

import pytest
from unittest.mock import patch, MagicMock

from axiom.config import AxiomConfig, set_config
from axiom.core.events import EventBus, Event
from axiom.perception.deny_list import DenyList
from axiom.perception.scrubber import PrivacyScrubber
from axiom.perception.window_tap import WindowFocusTap
from axiom.perception.clipboard_tap import ClipboardTap
from axiom.perception.intent_engine import IntentEngine


# ---------------------------------------------------------------------------
# DenyList security tests
# ---------------------------------------------------------------------------

class TestDenyList:

    @pytest.mark.parametrize("process_name", [
        "1password", "1Password", "1PASSWORD",
        "bitwarden", "Bitwarden",
        "gnome-keyring",
        "keepass", "KeePassXC",
        "lastpass",
        "dashlane",
        "kwallet",
    ])
    def test_blocks_credential_manager_processes(self, process_name):
        """Credential manager processes must always be blocked."""
        assert DenyList.is_process_blocked(process_name) is True

    @pytest.mark.parametrize("process_name", [
        "code", "python3", "bash", "firefox", "vim", "cursor", "zsh",
    ])
    def test_allows_safe_processes(self, process_name):
        """Common development processes must not be blocked."""
        assert DenyList.is_process_blocked(process_name) is False

    @pytest.mark.parametrize("title", [
        "1Password — Vault",
        "Bitwarden | Auto-fill",
        "Keychain Access",
        "Credential Manager",
        "My Bank — Account Summary",
        "PayPal: Send Money",
        "Coinbase Pro Trading",
        "Private Key Generator",
        "API Key Management Console",
    ])
    def test_blocks_sensitive_window_titles(self, title):
        """Sensitive window titles (banking, key managers) must be blocked."""
        assert DenyList.is_window_title_blocked(title) is True

    @pytest.mark.parametrize("title", [
        "Visual Studio Code",
        "Stack Overflow — Python questions",
        "GitHub — my-repo",
        "Slack",
        "Google Docs",
        "AXIOM Terminal",
    ])
    def test_allows_safe_window_titles(self, title):
        """Normal application titles must not be blocked."""
        assert DenyList.is_window_title_blocked(title) is False

    def test_unified_is_blocked_blocks_on_process(self):
        assert DenyList.is_blocked(process_name="1password", window_title="") is True

    def test_unified_is_blocked_blocks_on_title(self):
        assert DenyList.is_blocked(process_name="code", window_title="Bitwarden Vault") is True

    def test_unified_is_blocked_passes_clean_context(self):
        assert DenyList.is_blocked(process_name="code", window_title="GitHub") is False


# ---------------------------------------------------------------------------
# PrivacyScrubber.scrub_text tests
# ---------------------------------------------------------------------------

class TestPrivacyScrubberText:

    def test_scrubs_openai_api_key(self):
        text = "My key is sk-abcdef1234567890ABCDEFGHIJK"
        result = PrivacyScrubber.scrub_text(text)
        assert "sk-abcdef" not in result
        assert "[REDACTED:openai_key]" in result

    def test_scrubs_aws_access_key(self):
        text = "AWS key: AKIAIOSFODNN7EXAMPLE"
        result = PrivacyScrubber.scrub_text(text)
        assert "AKIAIOSFODNN7EXAMPLE" not in result
        assert "[REDACTED:aws_access_key]" in result

    def test_scrubs_bearer_token(self):
        text = "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
        result = PrivacyScrubber.scrub_text(text)
        assert "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9" not in result
        assert "Bearer [REDACTED]" in result

    def test_scrubs_password_in_config(self):
        text = "password=supersecret123"
        result = PrivacyScrubber.scrub_text(text)
        assert "supersecret123" not in result
        assert "[REDACTED]" in result

    def test_scrubs_pem_private_key(self):
        text = "-----BEGIN RSA PRIVATE KEY-----\nMIIEowIBAAK...\n-----END RSA PRIVATE KEY-----"
        result = PrivacyScrubber.scrub_text(text)
        assert "MIIEowIBAAK" not in result
        assert "[REDACTED:private_key]" in result

    def test_safe_text_passes_through_unchanged(self):
        text = "Hello, world! This is a normal message."
        result = PrivacyScrubber.scrub_text(text)
        assert result == text

    def test_scrubs_api_key_assignment(self):
        text = "api_key=my_very_secret_key_value"
        result = PrivacyScrubber.scrub_text(text)
        assert "my_very_secret_key_value" not in result


# ---------------------------------------------------------------------------
# WindowFocusTap config guard tests
# ---------------------------------------------------------------------------

class TestWindowFocusTap:

    def test_tap_does_not_start_when_disabled(self):
        """Tap must not spawn any thread when config guard is OFF."""
        set_config(AxiomConfig(monitor_window_focus=False))
        bus = EventBus()
        tap = WindowFocusTap(bus)
        started = tap.start()
        assert started is False
        assert tap._thread is None

    def test_tap_starts_when_enabled(self):
        """Tap must start its polling thread when the config guard is ON."""
        set_config(AxiomConfig(monitor_window_focus=True))
        bus = EventBus()
        tap = WindowFocusTap(bus)
        # Patch get_active_window to avoid real system calls
        with patch("axiom.perception.window_tap.get_active_window", return_value=("Test", "code")):
            started = tap.start()
            assert started is True
            assert tap._thread is not None
            assert tap._thread.is_alive()
            tap.stop()

    def test_tap_drops_password_manager_events(self):
        """Events from password manager windows must never reach the EventBus."""
        set_config(AxiomConfig(monitor_window_focus=True))
        received = []
        bus = EventBus()
        bus.subscribe("perception.window.focus", lambda e: received.append(e))

        tap = WindowFocusTap(bus)
        # Simulate a sample call with a blocked process
        with patch("axiom.perception.window_tap.get_active_window", return_value=("1Password Vault", "1password")):
            tap._sample()

        assert len(received) == 0, "No events must be emitted for blocked sources"

    def test_tap_emits_event_for_safe_window(self):
        """Events from safe applications must reach the EventBus."""
        set_config(AxiomConfig(monitor_window_focus=True))
        received = []
        bus = EventBus()
        bus.subscribe("perception.window.focus", lambda e: received.append(e))

        tap = WindowFocusTap(bus)
        with patch("axiom.perception.window_tap.get_active_window", return_value=("GitHub", "firefox")):
            tap._sample()

        assert len(received) == 1
        assert received[0].data["process_name"] == "firefox"


# ---------------------------------------------------------------------------
# ClipboardTap config guard and security tests
# ---------------------------------------------------------------------------

class TestClipboardTap:

    def test_tap_does_not_start_when_disabled(self):
        """Clipboard tap must not spawn a thread when config guard is OFF."""
        set_config(AxiomConfig(monitor_clipboard=False))
        bus = EventBus()
        tap = ClipboardTap(bus)
        started = tap.start()
        assert started is False

    def test_tap_drops_events_from_password_manager_window(self):
        """Clipboard must be completely ignored when a password manager is active."""
        set_config(AxiomConfig(monitor_clipboard=True))
        received = []
        bus = EventBus()
        bus.subscribe("perception.clipboard.change", lambda e: received.append(e))

        tap = ClipboardTap(bus)
        with patch("axiom.perception.window_tap.get_active_window", return_value=("Bitwarden", "bitwarden")):
            with patch("axiom.perception.clipboard_tap._read_clipboard", return_value="mysupersecretpassword"):
                tap._sample()

        assert len(received) == 0, "Clipboard events from password managers must be dropped"

    def test_tap_scrubs_secrets_before_emission(self):
        """API keys in clipboard text must be redacted before reaching EventBus."""
        set_config(AxiomConfig(monitor_clipboard=True))
        received = []
        bus = EventBus()
        bus.subscribe("perception.clipboard.change", lambda e: received.append(e))

        tap = ClipboardTap(bus)
        raw_secret = "My API key: sk-abcdefghijklmnopqrstuvwxyz123456"
        with patch("axiom.perception.window_tap.get_active_window", return_value=("Terminal", "bash")):
            with patch("axiom.perception.clipboard_tap._read_clipboard", return_value=raw_secret):
                tap._sample()

        assert len(received) == 1
        emitted_text = received[0].data["text"]
        assert "sk-abcdefghijklmnopqrstuvwxyz123456" not in emitted_text
        assert "[REDACTED:openai_key]" in emitted_text

    def test_tap_deduplicates_identical_clipboard_content(self):
        """Identical clipboard content must not emit duplicate events."""
        set_config(AxiomConfig(monitor_clipboard=True))
        received = []
        bus = EventBus()
        bus.subscribe("perception.clipboard.change", lambda e: received.append(e))

        tap = ClipboardTap(bus)
        same_text = "Hello world"
        with patch("axiom.perception.window_tap.get_active_window", return_value=("Terminal", "bash")):
            with patch("axiom.perception.clipboard_tap._read_clipboard", return_value=same_text):
                tap._sample()
                tap._sample()  # same content
                tap._sample()  # same content again

        assert len(received) == 1


# ---------------------------------------------------------------------------
# IntentEngine clipboard rule tests
# ---------------------------------------------------------------------------

class TestIntentEngineClipboard:

    def test_detects_python_traceback(self):
        bus = EventBus()
        engine = IntentEngine(bus)
        text = "Traceback (most recent call last):\n  File 'app.py', line 10\nValueError: bad input"
        action = engine.evaluate_clipboard(text)
        assert action is not None
        assert action["task"] == "analyze_traceback"

    def test_detects_bash_error(self):
        bus = EventBus()
        engine = IntentEngine(bus)
        text = "bash: git: command not found"
        action = engine.evaluate_clipboard(text)
        assert action is not None
        assert action["task"] == "explain_shell_error"

    def test_detects_stackoverflow_url(self):
        bus = EventBus()
        engine = IntentEngine(bus)
        text = "https://stackoverflow.com/questions/12345/how-to-fix-python"
        action = engine.evaluate_clipboard(text)
        assert action is not None
        assert action["task"] == "prefetch_so_context"

    def test_detects_sql_query(self):
        bus = EventBus()
        engine = IntentEngine(bus)
        text = "SELECT * FROM users WHERE id = 1;"
        action = engine.evaluate_clipboard(text)
        assert action is not None
        assert action["task"] == "explain_sql"

    def test_returns_none_for_generic_text(self):
        bus = EventBus()
        engine = IntentEngine(bus)
        action = engine.evaluate_clipboard("Hello, this is just a normal note.")
        assert action is None

    def test_window_context_terminal(self):
        bus = EventBus()
        engine = IntentEngine(bus)
        action = engine.evaluate_context("WindowFocusTap", "Terminal", "bash")
        assert action is not None
        assert action["task"] == "context_terminal"

    def test_window_context_editor(self):
        bus = EventBus()
        engine = IntentEngine(bus)
        action = engine.evaluate_context("WindowFocusTap", "VS Code", "code")
        assert action is not None
        assert action["task"] == "context_editor"
