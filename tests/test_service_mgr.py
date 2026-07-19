"""Tests for Systemd User Service Generator."""

import pytest
import os
import sys
from unittest.mock import patch, MagicMock
from pathlib import Path

from axiom.core.service_mgr import SystemdServiceManager

@pytest.fixture
def service_mgr():
    return SystemdServiceManager()

def test_generate_service_file(service_mgr):
    with patch.object(service_mgr, "_get_axiom_executable", return_value="/usr/local/bin/axiom"):
        content = service_mgr.generate_service_file()
        
        assert "[Unit]" in content
        assert "Description=AXIOM Local AI Orchestrator Daemon" in content
        assert "ExecStart=/usr/local/bin/axiom daemon start" in content
        assert "Restart=on-failure" in content
        assert "RestartSec=5s" in content
        assert "WantedBy=default.target" in content

@patch("sys.platform", "win32")
def test_is_supported_on_windows(service_mgr):
    """Should return False if not Linux."""
    assert not service_mgr.is_supported()

@patch("sys.platform", "linux")
@patch("shutil.which", return_value=None)
def test_is_supported_without_systemctl(mock_which, service_mgr):
    """Should return False if systemctl is not found on linux."""
    assert not service_mgr.is_supported()

@patch("sys.platform", "linux")
@patch("shutil.which", return_value="/usr/bin/systemctl")
def test_is_supported_with_systemctl(mock_which, service_mgr):
    """Should return True on linux with systemctl."""
    assert service_mgr.is_supported()

@patch.object(SystemdServiceManager, "is_supported", return_value=True)
@patch("subprocess.run")
def test_install_success(mock_run, mock_support, service_mgr, tmp_path):
    # Override directories to use tmp_path
    service_mgr.config_dir = tmp_path / "systemd" / "user"
    service_mgr.service_path = service_mgr.config_dir / "axiom.service"
    service_mgr.axiom_dir = tmp_path / ".axiom"
    
    with patch.object(service_mgr, "_get_axiom_executable", return_value="/bin/axiom"):
        assert service_mgr.install() is True
        
    assert service_mgr.service_path.exists()
    assert "ExecStart=/bin/axiom" in service_mgr.service_path.read_text()
    
    # systemctl commands should be called
    assert mock_run.call_count == 2
    mock_run.assert_any_call(["systemctl", "--user", "daemon-reload"], check=True)
    mock_run.assert_any_call(["systemctl", "--user", "enable", "axiom.service"], check=True)

@patch.object(SystemdServiceManager, "is_supported", return_value=True)
@patch("subprocess.run")
def test_service_commands(mock_run, mock_support, service_mgr):
    assert service_mgr.start() is True
    mock_run.assert_called_with(["systemctl", "--user", "start", "axiom.service"], check=True)
    
    assert service_mgr.stop() is True
    mock_run.assert_called_with(["systemctl", "--user", "stop", "axiom.service"], check=True)
    
    assert service_mgr.restart() is True
    mock_run.assert_called_with(["systemctl", "--user", "restart", "axiom.service"], check=True)

@patch.object(SystemdServiceManager, "is_supported", return_value=True)
@patch("subprocess.run")
def test_service_status(mock_run, mock_support, service_mgr):
    mock_result = MagicMock()
    mock_result.stdout = "Active: active (running)"
    mock_result.stderr = ""
    mock_run.return_value = mock_result
    
    status = service_mgr.status()
    assert "Active: active (running)" in status
    mock_run.assert_called_with(["systemctl", "--user", "status", "axiom.service"], capture_output=True, text=True)

@patch.object(SystemdServiceManager, "is_supported", return_value=False)
def test_commands_fail_if_unsupported(mock_support, service_mgr):
    with pytest.raises(RuntimeError):
        service_mgr.install()
        
    with pytest.raises(RuntimeError):
        service_mgr.start()
        
    assert "Systemd not supported" in service_mgr.status()
