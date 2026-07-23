import multiprocessing
import queue
import logging

logger = logging.getLogger(__name__)

class AudioDaemon:
    """Isolated background daemon for non-blocking STT and TTS audio pipelines."""
    
    def __init__(self):
        self.tts_queue = multiprocessing.Queue()
        self.stt_queue = multiprocessing.Queue()
        self.process = None

    def start(self):
        if self.process is not None and self.process.is_alive():
            return
            
        logger.info("Starting isolated AudioDaemon process for JARVIS pipeline.")
        self.process = multiprocessing.Process(target=self._run_loops, daemon=True)
        self.process.start()

    def _run_loops(self):
        """Runs inside the child process to prevent GIL locking."""
        from axiom.perception.voice_out import tts_loop
        from axiom.perception.voice_in import stt_loop
        import threading
        
        # Start TTS and STT in threads inside the isolated process
        t1 = threading.Thread(target=tts_loop, args=(self.tts_queue,), daemon=True)
        t2 = threading.Thread(target=stt_loop, args=(self.stt_queue,), daemon=True)
        t1.start()
        t2.start()
        
        t1.join()
        t2.join()

    def send_tts(self, text: str):
        self.tts_queue.put(text)
        
    def poll_stt(self):
        try:
            return self.stt_queue.get_nowait()
        except queue.Empty:
            return None
