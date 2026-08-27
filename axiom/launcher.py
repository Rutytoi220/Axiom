import os
import sys
import time
import socket
import subprocess
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("axiom.launcher")

def is_daemon_running(port: int = 9410) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex(('127.0.0.1', port)) == 0

def main():
    if len(sys.argv) > 1:
        from axiom.cli.main import main as cli_main
        cli_main()
        return

    os.environ["QT_QPA_PLATFORM"] = os.environ.get("QT_QPA_PLATFORM", "xcb")
    
    daemon_process = None
    if not is_daemon_running():
        logger.info("Daemon not running. Spawning background daemon...")
        
        env = os.environ.copy()
        daemon_process = subprocess.Popen([sys.executable, "-m", "axiom.server.daemon"], env=env)
        
        # Poll up to 5 seconds
        start_time = time.time()
        daemon_started = False
        while time.time() - start_time < 5.0:
            if is_daemon_running():
                daemon_started = True
                break
            time.sleep(0.5)
            
        if daemon_started:
            logger.info("Daemon successfully spawned and listening on port 9410.")
        else:
            logger.warning("Daemon did not respond on port 9410 within 5 seconds. GUI will continue without it.")
    else:
        logger.info("Found existing daemon running on port 9410.")
        
    logger.info("Launching PySide6 App...")
    try:
        from axiom.gui.app import main as gui_main
        gui_main()
    finally:
        # Cleanup spawned daemon on GUI exit
        if daemon_process is not None:
            logger.info("GUI exited. Terminating spawned daemon...")
            daemon_process.terminate()
            try:
                daemon_process.wait(timeout=3.0)
            except subprocess.TimeoutExpired:
                daemon_process.kill()
            logger.info("Spawned daemon terminated.")

if __name__ == "__main__":
    main()
