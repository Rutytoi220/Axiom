import time
import logging
from multiprocessing import Queue

logger = logging.getLogger(__name__)

def stt_loop(stt_queue: Queue):
    """Voice Activity Detection and STT loop running in background thread."""
    # Stubbed implementation - in a real scenario this would load Whisper,
    # capture PyAudio streams, run VAD, and push transcriptions.
    logger.info("STT Loop initialized (Stubbed). Listening for voice activity...")
    
    while True:
        try:
            # Simulating wait for voice detection
            time.sleep(1.0)
            
            # In production:
            # audio_data = vad.listen()
            # text = whisper.transcribe(audio_data)
            # if text:
            #     stt_queue.put(text)
                
        except Exception as e:
            logger.error(f"STT Loop error: {e}")
            time.sleep(1.0)
