import pytest
import sys
from unittest.mock import MagicMock, patch
from axiom.core.service_mgr import SystemdServiceManager

@pytest.fixture
def manager():
    return SystemdServiceManager()

def test_is_supported_false(manager):
    with patch("sys.platform", "win32"):
        assert manager.is_supported() == False
        
    with patch("sys.platform", "linux"):
        with patch("shutil.which", return_value=None):
            assert manager.is_supported() == False

def test_is_supported_true(manager):
    with patch("sys.platform", "linux"):
        with patch("shutil.which", return_value="systemctl"):
            assert manager.is_supported() == True

def test_get_axiom_executable(manager):
    with patch("shutil.which", return_value="/bin/axiom"):
        assert manager._get_axiom_executable() == "/bin/axiom"
        
    with patch("shutil.which", return_value=None):
        with patch("os.path.abspath", return_value="/abs/path"):
            assert manager._get_axiom_executable() == "/abs/path"

def test_generate_service_file(manager):
    with patch.object(manager, "_get_axiom_executable", return_value="/bin/axiom"):
        content = manager.generate_service_file()
        assert "ExecStart=/bin/axiom daemon start" in content

def test_install(manager):
    with patch.object(manager, "is_supported", return_value=False):
        with pytest.raises(RuntimeError):
            manager.install()
            
    with patch.object(manager, "is_supported", return_value=True):
        with patch("subprocess.run") as mock_run:
            with patch("pathlib.Path.write_text") as mock_write:
                assert manager.install() == True
                assert mock_run.call_count == 2
                mock_write.assert_called_once()
                
    with patch.object(manager, "is_supported", return_value=True):
        with patch("subprocess.run", side_effect=Exception("error")):
            assert manager.install() == False

def test_start_stop_restart(manager):
    with patch.object(manager, "_run_systemctl", return_value=True) as mock_run:
        assert manager.start() == True
        mock_run.assert_called_with("start")
        
        assert manager.stop() == True
        mock_run.assert_called_with("stop")
        
        assert manager.restart() == True
        mock_run.assert_called_with("restart")

def test_status(manager):
    with patch.object(manager, "is_supported", return_value=False):
        assert manager.status() == "Systemd not supported."
        
    with patch.object(manager, "is_supported", return_value=True):
        result = MagicMock()
        result.stdout = "running"
        with patch("subprocess.run", return_value=result):
            assert manager.status() == "running"
            
        with patch("subprocess.run", side_effect=Exception("error")):
            assert "Error fetching status" in manager.status()

from subprocess import CalledProcessError
def test_run_systemctl(manager):
    with patch.object(manager, "is_supported", return_value=False):
        with pytest.raises(RuntimeError):
            manager._run_systemctl("start")
            
    with patch.object(manager, "is_supported", return_value=True):
        with patch("subprocess.run"):
            assert manager._run_systemctl("start") == True
            
        with patch("subprocess.run", side_effect=CalledProcessError(1, "cmd")):
            assert manager._run_systemctl("start") == False
            
        with patch("subprocess.run", side_effect=Exception("error")):
            assert manager._run_systemctl("start") == False
