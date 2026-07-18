import os
import json
import time
from pathlib import Path
from axiom.core.recorder import FlightRecorder
from axiom.core.events import EventBus, Event

def test_flight_recorder_scrub_secrets(tmp_path):
    bus = EventBus()
    recorder = FlightRecorder(bus, trace_dir=str(tmp_path))
    
    # Test scrubbing
    payload = {
        "api_key": "sk-12345678901234567890abcd",
        "auth": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9",
        "url": "https://user:password123@api.example.com",
        "path": str(Path.home() / "secret.txt"),
        "nested": {
            "key": "sk-09876543210987654321dcba"
        }
    }
    scrubbed = recorder._scrub_secrets(payload)
    
    assert scrubbed["api_key"] == "sk-***"
    assert scrubbed["auth"] == "Bearer ***"
    assert "password123" not in scrubbed["url"]
    assert "***" in scrubbed["url"]
    assert scrubbed["nested"]["key"] == "sk-***"
    if str(Path.home()) != "/":
        assert str(Path.home()) not in scrubbed["path"]
        assert "~" in scrubbed["path"]

def test_flight_recorder_write_and_rotate(tmp_path):
    bus = EventBus()
    recorder = FlightRecorder(bus, trace_dir=str(tmp_path))
    
    recorder.start()
    
    # Emit an event
    bus.publish_sync("test.event", {"hello": "world"})
    
    # Wait for background thread
    time.sleep(0.1)
    recorder.stop()
    
    trace_file = tmp_path / "flight_recorder.jsonl"
    assert trace_file.exists()
    
    content = trace_file.read_text()
    assert "test.event" in content
    assert "world" in content

    # Test manual rotation mechanics (forcing the limit)
    import axiom.core.recorder
    axiom.core.recorder.MAX_BYTES = 50  # Super small limit
    
    recorder = FlightRecorder(bus, trace_dir=str(tmp_path))
    recorder.start()
    for _ in range(5):
        bus.publish_sync("spam.event", {"data": "lots of data to force rotation quickly!"})
        time.sleep(0.01)
    
    time.sleep(0.1)
    recorder.stop()
    
    # Check that backups were created
    assert (tmp_path / "flight_recorder.jsonl.1").exists()
    
    # Restore original size
    axiom.core.recorder.MAX_BYTES = 5 * 1024 * 1024
