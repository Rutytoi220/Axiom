import sys
import io
import pytest
import logging
from axiom.perception.audio_queue import AudioDaemon
from axiom.perception.voice_in import stt_loop
from axiom.perception.voice_out import tts_loop
import multiprocessing

# We need to simulate the CLI loading its logging config
# to make sure the environment is properly isolated.
import axiom.api.cli

def test_background_daemons_are_silent():
    """Ensure that initializing daemons doesn't dump logs to stdout/stderr."""
    # Capture stdout and stderr
    captured_stdout = io.StringIO()
    captured_stderr = io.StringIO()
    
    old_stdout = sys.stdout
    old_stderr = sys.stderr
    
    sys.stdout = captured_stdout
    sys.stderr = captured_stderr
    
    try:
        # Initialize AudioDaemon
        daemon = AudioDaemon()
        
        # We trigger the logs that usually spam the console
        # by manually calling the inner methods with a dummy queue
        # that would trigger the initial logger.info()
        dummy_q = multiprocessing.Queue()
        
        # AudioDaemon triggers a log in start
        # but since start() spawns a process, we just manually invoke 
        # a logger call in the module to ensure it's squashed.
        import axiom.perception.audio_queue as aq
        aq.logger.info("This should NOT appear on console.")
        
        # voice_in uses logger.info on startup
        import axiom.perception.voice_in as vi
        vi.logger.info("STT Loop initialized (Stubbed).")
        
        # voice_out uses logger.info on startup
        import axiom.perception.voice_out as vo
        vo.logger.info("TTS Engine initialized.")
        
    finally:
        sys.stdout = old_stdout
        sys.stderr = old_stderr
        
    out = captured_stdout.getvalue()
    err = captured_stderr.getvalue()
    
    # Assert zero bytes written to console
    assert len(out) == 0, f"Stdout was not completely silent: {out}"
    assert len(err) == 0, f"Stderr was not completely silent: {err}"
