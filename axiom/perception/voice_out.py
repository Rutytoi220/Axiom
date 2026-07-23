import time
import queue
import logging
import re
from multiprocessing import Queue

logger = logging.getLogger(__name__)

def clean_markdown_for_speech(text: str) -> str:
    """Strips Markdown syntax to make text TTS-friendly."""
    # Remove code blocks
    text = re.sub(r'```.*?```', ' [Code block omitted] ', text, flags=re.DOTALL)
    # Remove inline code
    text = re.sub(r'`[^`]*`', '', text)
    # Remove bold/italic
    text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)
    text = re.sub(r'\*(.*?)\*', r'\1', text)
    text = re.sub(r'__(.*?)__', r'\1', text)
    text = re.sub(r'_(.*?)_', r'\1', text)
    # Remove JSON wrappers or specific tags if any
    text = re.sub(r'\{.*?\}', '', text, flags=re.DOTALL)
    return text.strip()

def tts_loop(tts_queue: Queue):
    """Text-to-Speech loop running in background thread."""
    try:
        import pyttsx3
        engine = pyttsx3.init()
        engine.setProperty('rate', 170)
        has_tts = True
        logger.info("TTS Engine initialized (pyttsx3).")
    except ImportError:
        logger.warning("pyttsx3 not installed. TTS will just consume the queue silently.")
        has_tts = False

    while True:
        try:
            # Block until there is text to speak
            text = tts_queue.get()
            
            clean_text = clean_markdown_for_speech(text)
            if not clean_text:
                continue
                
            if has_tts:
                engine.say(clean_text)
                engine.runAndWait()
            else:
                logger.info(f"[TTS Stub Speak]: {clean_text}")
                
        except Exception as e:
            logger.error(f"TTS Loop error: {e}")
            time.sleep(1.0)
