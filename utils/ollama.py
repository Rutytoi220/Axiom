"""Helpers to detect, start, and optionally install Ollama locally.

Provides:
- is_server_up(url)
- which_ollama()
- start_ollama(ollama_path=None)
- attempt_auto_install(confirm=False)

The module avoids automatic installs unless the user explicitly requests
`attempt_auto_install(confirm=True)` via the CLI `:ollama install confirm`.
"""

import os
import socket
import shutil
import subprocess
import tempfile
import time
from urllib.parse import urlparse
from typing import Tuple

from .config import get_config
from .logger import get_logger

logger = get_logger(__name__)


def _get_base_url(provided_url: str = None) -> str:
    cfg = get_config() or {}
    url = provided_url or cfg.get('ollama', {}).get('url', 'http://127.0.0.1:11434')
    return url


def _parse_host_port(url: str) -> Tuple[str, int]:
    p = urlparse(url)
    host = p.hostname or '127.0.0.1'
    port = p.port or (11434 if p.scheme in ('http', 'https') else 11434)
    return host, int(port)


def is_server_up(url: str = None, timeout: float = 1.0) -> bool:
    url = _get_base_url(url)
    host, port = _parse_host_port(url)
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except Exception:
        return False


def which_ollama() -> str | None:
    return shutil.which('ollama')


def start_ollama(ollama_path: str = None, wait: float = 3.0) -> Tuple[bool, str]:
    """Attempt to start the Ollama daemon using the provided binary path or
    the one found on PATH. Returns (ok, message).
    """
    path = ollama_path or which_ollama()
    if not path:
        return False, 'ollama binary not found on PATH.'
    logfile = os.path.join(tempfile.gettempdir(), 'ollama_autostart.log')
    cmd = [path, 'serve']
    try:
        f = open(logfile, 'a')
        proc = subprocess.Popen(cmd, stdout=f, stderr=f, start_new_session=True)
        logger.info('Started ollama serve pid=%s logfile=%s', proc.pid, logfile)
    except Exception as e:
        logger.exception('Failed to start ollama')
        return False, f'Failed to start ollama: {e}'
    # wait a bit and check
    time.sleep(wait)
    if is_server_up():
        return True, f'Ollama server started (pid={proc.pid}), logfile: {logfile}'
    else:
        return False, f'Attempted to start ollama (pid={proc.pid}), but server not responding yet. See {logfile}'


def attempt_auto_install(confirm: bool = False) -> Tuple[bool, str]:
    """If confirm is False, returns instructions. If True, attempts a basic
    automated install by downloading the official installer and running it.

    NOTE: this performs network operations and runs a remote script. It
    requires user consent and may require elevated privileges.
    """
    if not confirm:
        return False, (
            "Ollama not found. To install manually, follow instructions at https://ollama.com/docs/install\n"
            "To attempt an automated install from this CLI, run: :ollama install confirm"
        )

    curl = shutil.which('curl')
    wget = shutil.which('wget')
    if not curl and not wget:
        return False, 'Neither curl nor wget is available to download installer.'

    script_url = 'https://ollama.com/install.sh'
    tmp_script = os.path.join(tempfile.gettempdir(), 'ollama_install.sh')
    try:
        if curl:
            subprocess.run([curl, '-fsSL', script_url, '-o', tmp_script], check=True)
        else:
            subprocess.run([wget, '-qO', tmp_script, script_url], check=True)
        os.chmod(tmp_script, 0o700)
        # run installer
        subprocess.run(['sh', tmp_script], check=True)
    except subprocess.CalledProcessError as e:
        logger.exception('Automated install failed')
        return False, f'Automated install failed: {e}'
    except Exception as e:
        logger.exception('Automated install error')
        return False, f'Automated install error: {e}'

    # verify
    if which_ollama():
        return True, 'Ollama installed successfully (binary on PATH).'
    return False, 'Installer ran but ollama binary not found on PATH.'
