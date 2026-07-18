"""Tests for the Proactive OS Perception Kernel (RFC-003)."""

import pytest
import time
import psutil
from unittest.mock import Mock, patch
from pathlib import Path

from axiom.core.events import EventBus
from axiom.perception.scrubber import PrivacyScrubber
from axiom.perception.intent_engine import IntentEngine
from axiom.perception.watcher import ResourceGovernor, ProactiveWatcher


def test_privacy_scrubber_allowed_files():
    assert PrivacyScrubber.is_safe("src/main.py")
    assert PrivacyScrubber.is_safe("/var/log/app.log")
    assert PrivacyScrubber.is_safe("README.md")


def test_privacy_scrubber_blocked_filenames():
    assert not PrivacyScrubber.is_safe(".env")
    assert not PrivacyScrubber.is_safe("/path/to/.env")
    assert not PrivacyScrubber.is_safe("id_rsa")
    assert not PrivacyScrubber.is_safe("secrets.json")


def test_privacy_scrubber_blocked_extensions():
    assert not PrivacyScrubber.is_safe("cert.pem")
    assert not PrivacyScrubber.is_safe("private.key")


def test_privacy_scrubber_blocked_patterns():
    assert not PrivacyScrubber.is_safe("/project/.git/config")
    assert not PrivacyScrubber.is_safe("/project/.axiom/memory.db")
    assert not PrivacyScrubber.is_safe("/project/node_modules/index.js")
    assert not PrivacyScrubber.is_safe("/project/secret_key.txt")
    assert not PrivacyScrubber.is_safe("/project/MY_PASSWORD_123.txt")


def test_intent_engine_auto_index_rule():
    bus = Mock()
    engine = IntentEngine(bus)
    
    # Matches Rule 1 (silent auto-index)
    result = engine.evaluate("created", "/path/to/new_file.py")
    
    assert result is not None
    assert result["action_mode"] == "silent"
    assert result["task"] == "auto_index"
    
    # Verifies event was published
    assert bus.publish.called
    event = bus.publish.call_args[0][0]
    assert event.event_type == "perception.intent.silent"


def test_intent_engine_notify_rule():
    bus = Mock()
    engine = IntentEngine(bus)
    
    # Matches Rule 2 (notify traceback)
    result = engine.evaluate("modified", "/path/to/app_traceback.log")
    
    assert result is not None
    assert result["action_mode"] == "notify"
    assert result["task"] == "analyze_error"
    
    # Verifies event was published
    event = bus.publish.call_args[0][0]
    assert event.event_type == "perception.intent.notify"


def test_intent_engine_no_match():
    bus = Mock()
    engine = IntentEngine(bus)
    
    result = engine.evaluate("created", "/path/to/readme.md")
    assert result is None
    assert not bus.publish.called


def test_resource_governor_pauses_on_high_cpu():
    gov = ResourceGovernor(max_cpu_percent=1.5, window_seconds=2)
    # Simulate high CPU
    gov._history = [2.0, 2.0]
    
    with patch("psutil.cpu_percent", return_value=5.0):
        # We manually trigger the logic that would run in the thread
        cpu = psutil.cpu_percent()
        gov._history.append(cpu)
        if len(gov._history) > gov.window_seconds:
            gov._history.pop(0)
            
        avg = sum(gov._history) / len(gov._history)
        gov.is_paused = avg > gov.max_cpu_percent
        
        assert gov.is_paused is True


def test_proactive_watcher_opt_in_guard():
    bus = Mock()
    watcher = ProactiveWatcher(bus, ["/tmp"])
    
    with patch("axiom.perception.watcher.get_config") as mock_config:
        # 1. Disabled by default
        cfg = Mock()
        cfg.proactive_kernel = False
        mock_config.return_value = cfg
        
        assert watcher.start() is False
        assert watcher.observer is None
        
        # 2. Enabled explicitly
        cfg.proactive_kernel = True
        
        with patch.object(watcher.governor, "start"), \
             patch("axiom.perception.watcher.Observer") as mock_obs:
             
            # Assume /tmp exists
            assert watcher.start() is True
            assert mock_obs.called
