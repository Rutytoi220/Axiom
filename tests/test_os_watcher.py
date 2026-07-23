import pytest
import time
from unittest.mock import patch, MagicMock

from axiom.perception.watcher import OSWatcher
from axiom.core.events import EventBus

class TestOSWatcher:

    @pytest.fixture
    def mock_config(self):
        with patch('axiom.perception.watcher.get_config') as mock_get_config:
            mock_conf = MagicMock()
            mock_conf.proactive_kernel = True
            mock_get_config.return_value = mock_conf
            yield mock_get_config

    @pytest.fixture
    def mock_psutil(self):
        with patch('axiom.perception.watcher.psutil') as m_psutil:
            
            # Setup default normal memory
            m_mem = MagicMock()
            m_mem.percent = 50.0
            m_mem.available = 8 * (1024**3)
            m_mem.total = 16 * (1024**3)
            m_psutil.virtual_memory.return_value = m_mem
            
            # Setup default normal disk
            m_disk = MagicMock()
            m_disk.free = 100 * (1024**3)
            m_psutil.disk_usage.return_value = m_disk
            
            # Setup default normal cpu
            m_psutil.cpu_percent.return_value = 10.0
            
            yield m_psutil

    def test_os_watcher_starts_and_stops(self, mock_config, mock_psutil):
        event_bus = EventBus()
        watcher = OSWatcher(event_bus)
        
        assert watcher.start() is True
        assert watcher._running is True
        
        watcher.stop()
        assert watcher._running is False

    @patch('axiom.perception.watcher.time.time')
    def test_memory_anomaly_triggers_alert(self, mock_time, mock_config, mock_psutil):
        event_bus = MagicMock()
        watcher = OSWatcher(event_bus)
        
        # Simulate memory spike (88% used)
        m_mem = MagicMock()
        m_mem.percent = 88.0
        m_mem.available = 2 * (1024**3)
        m_mem.total = 16 * (1024**3)
        mock_psutil.virtual_memory.return_value = m_mem
        
        # Fix time
        mock_time.return_value = 1000.0
        
        # Force a single monitor loop manually to avoid threading complexity in tests
        watcher._running = True
        
        # Since _monitor_loop sleeps and loops indefinitely, we'll patch time.sleep to raise an exception to break the loop,
        # or we can just extract the logic. Let's patch sleep to raise KeyboardInterrupt.
        with patch('axiom.perception.watcher.time.sleep', side_effect=[None, KeyboardInterrupt]):
            try:
                watcher._monitor_loop()
            except KeyboardInterrupt:
                pass
                
        # Assert publish was called with system.anomaly
        assert event_bus.publish.called
        event = event_bus.publish.call_args[0][0]
        assert event.event_type == "system.anomaly"
        assert event.data["type"] == "high_memory"
        assert "RAM at 88.0%" in event.data["details"]
        
        # Test cooldown logic: advance time by 10 seconds (less than 300s cooldown)
        event_bus.publish.reset_mock()
        mock_time.return_value = 1010.0
        
        with patch('axiom.perception.watcher.time.sleep', side_effect=[None, KeyboardInterrupt]):
            try:
                watcher._monitor_loop()
            except KeyboardInterrupt:
                pass
                
        # Should NOT trigger again due to cooldown
        assert not event_bus.publish.called
        
        # Test cooldown expiration: advance time past 300s
        mock_time.return_value = 1400.0
        with patch('axiom.perception.watcher.time.sleep', side_effect=[None, KeyboardInterrupt]):
            try:
                watcher._monitor_loop()
            except KeyboardInterrupt:
                pass
        
        assert event_bus.publish.called
        
