"""Tests for AXIOM v2.5 OS Sandbox Plugin.

Verifies backend detection, command classification, sandbox argument
construction, and mode-based routing — all with mocked subprocess calls
so no real Docker or bubblewrap is required.
"""

import os
import pytest
from unittest.mock import patch, MagicMock

from axiom.plugins.sandbox_plugin import (
    SandboxBackend,
    SandboxMode,
    SandboxRuntime,
    _extract_base_command,
)


# ---------------------------------------------------------------------------
# Backend Detection
# ---------------------------------------------------------------------------

class TestBackendDetection:
    """Verify that SandboxRuntime detects the correct isolation backend."""

    @patch("axiom.plugins.sandbox_plugin.shutil.which")
    def test_backend_detection_docker(self, mock_which):
        """Docker is preferred when available."""
        mock_which.side_effect = lambda cmd: "/usr/bin/docker" if cmd == "docker" else None
        runtime = SandboxRuntime()
        assert runtime.backend == SandboxBackend.DOCKER

    @patch("axiom.plugins.sandbox_plugin.shutil.which")
    def test_backend_detection_bwrap(self, mock_which):
        """Bubblewrap is used when Docker is absent."""
        def which_side_effect(cmd):
            if cmd == "docker":
                return None
            if cmd == "bwrap":
                return "/usr/bin/bwrap"
            return None
        mock_which.side_effect = which_side_effect
        runtime = SandboxRuntime()
        assert runtime.backend == SandboxBackend.BWRAP

    @patch("axiom.plugins.sandbox_plugin.shutil.which")
    def test_backend_detection_none(self, mock_which):
        """Falls back to NONE when neither Docker nor bwrap exists."""
        mock_which.return_value = None
        runtime = SandboxRuntime()
        assert runtime.backend == SandboxBackend.NONE


# ---------------------------------------------------------------------------
# Command Classification
# ---------------------------------------------------------------------------

class TestCommandClassification:
    """Verify the read-only vs state-changing command classifier."""

    @pytest.mark.parametrize("command", [
        "ls -la",
        "cat /etc/hostname",
        "ps aux",
        "uname -a",
        "whoami",
        "echo hello",
        "grep -r foo /tmp",
        "head -n 10 file.txt",
        "df -h",
        "free -m",
        "date",
        "pwd",
        "id",
        "env",
    ])
    def test_readonly_classification(self, command):
        """Read-only commands are correctly identified."""
        assert SandboxRuntime.is_readonly_command(command) is True

    @pytest.mark.parametrize("command", [
        "pip install requests",
        "chmod +x script.sh",
        "./script.sh",
        "git apply patch.diff",
        "rm -rf /tmp/test",
        "npm test",
        "python3 setup.py install",
        "apt-get install vim",
        "make build",
        "gcc -o test test.c",
        "mv foo.txt bar.txt",
        "cp -r src/ dst/",
        "touch newfile.txt",
        "mkdir -p /tmp/test",
    ])
    def test_dangerous_classification(self, command):
        """State-changing commands are correctly identified as NOT read-only."""
        assert SandboxRuntime.is_readonly_command(command) is False

    def test_extract_base_command_skips_sudo(self):
        """sudo prefix is stripped when extracting the base command."""
        assert _extract_base_command("sudo ls -la") == "ls"

    def test_extract_base_command_skips_env_vars(self):
        """Environment variable assignments are skipped."""
        assert _extract_base_command("FOO=bar BAZ=1 cat file.txt") == "cat"


# ---------------------------------------------------------------------------
# Docker Execution Arguments
# ---------------------------------------------------------------------------

class TestDockerExecution:
    """Verify Docker sandbox constructs correct arguments."""

    @patch("axiom.plugins.sandbox_plugin.shutil.which")
    @patch("axiom.plugins.sandbox_plugin.subprocess.run")
    def test_docker_execution_args(self, mock_run, mock_which):
        """Docker mode passes --rm, --memory, --network=none, and bind mounts."""
        mock_which.side_effect = lambda cmd: "/usr/bin/docker" if cmd == "docker" else None
        mock_run.return_value = MagicMock(
            stdout="test output", stderr="", returncode=0
        )
        runtime = SandboxRuntime()
        result = runtime.execute_in_sandbox("npm test", cwd="/workspace", timeout=30)

        mock_run.assert_called_once()
        call_args = mock_run.call_args[0][0]  # The list of args

        assert call_args[0] == "docker"
        assert "--rm" in call_args
        assert "--memory=512m" in call_args
        assert "--network=none" in call_args
        assert "-v" in call_args
        assert "/workspace:/workspace" in call_args
        assert "bash" in call_args
        assert "npm test" in call_args

        assert result["stdout"] == "test output"
        assert result["exit_code"] == 0
        assert result["sandboxed"] is True
        assert result["sandbox_backend"] == "docker"


# ---------------------------------------------------------------------------
# Bubblewrap Execution Arguments
# ---------------------------------------------------------------------------

class TestBwrapExecution:
    """Verify bubblewrap sandbox constructs correct arguments."""

    @patch("axiom.plugins.sandbox_plugin.shutil.which")
    @patch("axiom.plugins.sandbox_plugin.subprocess.run")
    def test_bwrap_execution_args(self, mock_run, mock_which):
        """Bwrap mode passes --ro-bind, --unshare-all, --die-with-parent."""
        def which_side_effect(cmd):
            if cmd == "docker":
                return None
            if cmd == "bwrap":
                return "/usr/bin/bwrap"
            return None
        mock_which.side_effect = which_side_effect
        mock_run.return_value = MagicMock(
            stdout="bwrap output", stderr="", returncode=0
        )
        runtime = SandboxRuntime()
        result = runtime.execute_in_sandbox("git status", cwd="/project", timeout=15)

        mock_run.assert_called_once()
        call_args = mock_run.call_args[0][0]

        assert call_args[0] == "bwrap"
        assert "--ro-bind" in call_args
        assert "--unshare-all" in call_args
        assert "--die-with-parent" in call_args
        assert "/project" in call_args
        assert "git status" in call_args

        assert result["stdout"] == "bwrap output"
        assert result["exit_code"] == 0
        assert result["sandboxed"] is True
        assert result["sandbox_backend"] == "bwrap"


# ---------------------------------------------------------------------------
# Mode-Based Routing
# ---------------------------------------------------------------------------

class TestModeRouting:
    """Verify sandbox mode controls which commands get sandboxed."""

    @patch("axiom.plugins.sandbox_plugin.shutil.which")
    def test_auto_mode_passthrough_readonly(self, mock_which):
        """In AUTO mode, read-only commands are NOT sandboxed."""
        mock_which.side_effect = lambda cmd: "/usr/bin/docker" if cmd == "docker" else None
        runtime = SandboxRuntime(mode=SandboxMode.AUTO)
        assert runtime.should_sandbox("ls -la") is False
        assert runtime.should_sandbox("cat /etc/hostname") is False
        assert runtime.should_sandbox("ps aux") is False

    @patch("axiom.plugins.sandbox_plugin.shutil.which")
    def test_auto_mode_sandboxes_dangerous(self, mock_which):
        """In AUTO mode, state-changing commands ARE sandboxed."""
        mock_which.side_effect = lambda cmd: "/usr/bin/docker" if cmd == "docker" else None
        runtime = SandboxRuntime(mode=SandboxMode.AUTO)
        assert runtime.should_sandbox("pip install requests") is True
        assert runtime.should_sandbox("chmod +x script.sh") is True
        assert runtime.should_sandbox("./run.sh") is True
        assert runtime.should_sandbox("rm -rf /tmp/test") is True

    @patch("axiom.plugins.sandbox_plugin.shutil.which")
    def test_strict_mode_sandboxes_all(self, mock_which):
        """In STRICT mode, even read-only commands are sandboxed."""
        mock_which.side_effect = lambda cmd: "/usr/bin/docker" if cmd == "docker" else None
        runtime = SandboxRuntime(mode=SandboxMode.STRICT)
        assert runtime.should_sandbox("ls -la") is True
        assert runtime.should_sandbox("whoami") is True
        assert runtime.should_sandbox("pip install foo") is True

    @patch("axiom.plugins.sandbox_plugin.shutil.which")
    def test_off_mode_bypasses_all(self, mock_which):
        """In OFF mode, nothing is sandboxed."""
        mock_which.side_effect = lambda cmd: "/usr/bin/docker" if cmd == "docker" else None
        runtime = SandboxRuntime(mode=SandboxMode.OFF)
        assert runtime.should_sandbox("rm -rf /") is False
        assert runtime.should_sandbox("pip install malware") is False
        assert runtime.should_sandbox("ls") is False


# ---------------------------------------------------------------------------
# Status Reporting
# ---------------------------------------------------------------------------

class TestStatusReporting:
    """Verify get_status() returns correct metadata."""

    @patch("axiom.plugins.sandbox_plugin.shutil.which")
    def test_status_docker(self, mock_which):
        mock_which.side_effect = lambda cmd: "/usr/bin/docker" if cmd == "docker" else None
        runtime = SandboxRuntime()
        status = runtime.get_status()
        assert status["backend"] == "DOCKER"
        assert status["mode"] == "auto"
        assert status["available"] is True
        assert status["docker_image"] == "python:3.12-slim"

    @patch("axiom.plugins.sandbox_plugin.shutil.which")
    def test_status_none(self, mock_which):
        mock_which.return_value = None
        runtime = SandboxRuntime()
        status = runtime.get_status()
        assert status["backend"] == "NONE"
        assert status["available"] is False
        assert status["docker_image"] == "N/A"


# ---------------------------------------------------------------------------
# EventBus Telemetry
# ---------------------------------------------------------------------------

class TestEventBusTelemetry:
    """Verify sandbox emits telemetry events when bus is connected."""

    @patch("axiom.plugins.sandbox_plugin.shutil.which")
    @patch("axiom.plugins.sandbox_plugin.subprocess.run")
    def test_events_emitted_on_execution(self, mock_run, mock_which):
        """EventBus receives sandbox.exec and sandbox.exec.complete events."""
        mock_which.side_effect = lambda cmd: "/usr/bin/docker" if cmd == "docker" else None
        mock_run.return_value = MagicMock(stdout="ok", stderr="", returncode=0)

        mock_bus = MagicMock()
        runtime = SandboxRuntime(event_bus=mock_bus)
        runtime.execute_in_sandbox("npm test", cwd="/workspace")

        # Two events: running + completed
        assert mock_bus.publish.call_count == 2
        events = [call[0][0] for call in mock_bus.publish.call_args_list]
        assert events[0].event_type == "sandbox.exec"
        assert events[0].data["status"] == "running"
        assert events[1].event_type == "sandbox.exec.complete"
        assert events[1].data["status"] == "completed"
