"""Automation Plugin - Task automation and scheduling."""

from typing import Dict, Optional, Any, List, Callable
from dataclasses import dataclass
from datetime import datetime
import logging

from axiom.plugins.base_plugin import BasePlugin

logger = logging.getLogger(__name__)


@dataclass
class AutomationTask:
    """Automation task definition."""
    task_id: str
    name: str
    trigger: str  # "time", "event", "condition"
    action: Callable
    enabled: bool = True
    created_at: datetime = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()


class AutomationPlugin(BasePlugin):
    """Plugin for task automation and scheduling."""
    
    def __init__(self):
        super().__init__(
            plugin_id="automation",
            name="Automation Plugin",
            version="1.0.0"
        )
        self.tasks: Dict[str, AutomationTask] = {}
        self._running = False
    
    def initialize(self, config: Optional[Dict] = None) -> bool:
        """Initialize automation plugin."""
        try:
            self.config = config or {}
            logger.info("Automation Plugin initialized")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize automation: {e}")
            return False
    
    def shutdown(self) -> bool:
        """Shutdown automation plugin."""
        try:
            self._running = False
            self.tasks.clear()
            logger.info("Automation Plugin shutdown")
            return True
        except Exception as e:
            logger.error(f"Error shutting down automation: {e}")
            return False
    
    def register_task(self, task: AutomationTask) -> bool:
        """Register an automation task."""
        try:
            self.tasks[task.task_id] = task
            logger.info(f"Task registered: {task.task_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to register task: {e}")
            return False
    
    def unregister_task(self, task_id: str) -> bool:
        """Unregister an automation task."""
        try:
            if task_id in self.tasks:
                del self.tasks[task_id]
                logger.info(f"Task unregistered: {task_id}")
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to unregister task: {e}")
            return False
    
    def enable_task(self, task_id: str) -> bool:
        """Enable an automation task."""
        if task_id in self.tasks:
            self.tasks[task_id].enabled = True
            logger.info(f"Task enabled: {task_id}")
            return True
        return False
    
    def disable_task(self, task_id: str) -> bool:
        """Disable an automation task."""
        if task_id in self.tasks:
            self.tasks[task_id].enabled = False
            logger.info(f"Task disabled: {task_id}")
            return True
        return False
    
    def execute_task(self, task_id: str) -> bool:
        """Execute an automation task."""
        if task_id not in self.tasks:
            return False
        
        task = self.tasks[task_id]
        if not task.enabled:
            return False
        
        try:
            task.action()
            logger.info(f"Task executed: {task_id}")
            return True
        except Exception as e:
            logger.error(f"Error executing task {task_id}: {e}")
            return False
    
    def list_tasks(self) -> List[Dict[str, Any]]:
        """List all automation tasks."""
        return [
            {
                "task_id": task.task_id,
                "name": task.name,
                "trigger": task.trigger,
                "enabled": task.enabled,
                "created_at": task.created_at.isoformat()
            }
            for task in self.tasks.values()
        ]
    
    def get_task_info(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get information about a specific task."""
        if task_id not in self.tasks:
            return None
        
        task = self.tasks[task_id]
        return {
            "task_id": task.task_id,
            "name": task.name,
            "trigger": task.trigger,
            "enabled": task.enabled,
            "created_at": task.created_at.isoformat()
        }
