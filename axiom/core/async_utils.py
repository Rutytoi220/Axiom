import asyncio
import logging
from typing import Any, Coroutine

logger = logging.getLogger(__name__)

def _handle_task_result(task: asyncio.Task[Any]) -> None:
    try:
        task.result()
    except asyncio.CancelledError:
        pass
    except Exception as e:
        logger.error(f"Background task failed: {e}", exc_info=True)

def safe_create_task(coro: Coroutine[Any, Any, Any]) -> asyncio.Task[Any]:
    task = asyncio.create_task(coro)
    task.add_done_callback(_handle_task_result)
    return task
