"""Pytest configuration and debug instrumentation."""

import importlib.util
import json
import time

_DEBUG_LOG = "/run/media/rutytoi/fast af/ChienGPT/.cursor/debug-e94045.log"


def _agent_log(location: str, message: str, data: dict, hypothesis_id: str) -> None:
    # #region agent log
    try:
        with open(_DEBUG_LOG, "a", encoding="utf-8") as f:
            f.write(
                json.dumps(
                    {
                        "sessionId": "e94045",
                        "hypothesisId": hypothesis_id,
                        "location": location,
                        "message": message,
                        "data": data,
                        "timestamp": int(time.time() * 1000),
                    }
                )
                + "\n"
            )
    except Exception:
        pass
    # #endregion


def pytest_configure(config):
    """Log whether pytest-asyncio is available (hypothesis A)."""
    has_asyncio_plugin = importlib.util.find_spec("pytest_asyncio") is not None
    _agent_log(
        "tests/conftest.py:pytest_configure",
        "pytest_asyncio_availability",
        {"pytest_asyncio_installed": has_asyncio_plugin},
        "A",
    )
