"""Automation Plugin - Task automation and scheduling."""

import json
import uuid
import threading
from pathlib import Path
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
    
    def __init__(self, engine=None):
        super().__init__(
            plugin_id="automation",
            name="Automation Plugin",
            version="1.0.0"
        )
        self.tasks: Dict[str, AutomationTask] = {}
        self._running = False
        self.engine = engine
        self.is_recording = False
        self.current_macro_steps = []
        self.macros_dir = Path.home() / ".axiom" / "macros"
        self.macros_dir.mkdir(parents=True, exist_ok=True)
    
    def initialize(self, config: Optional[Dict] = None) -> bool:
        """Initialize automation plugin."""
        try:
            self.config = config or {}
            if self.engine and hasattr(self.engine, "event_bus"):
                self.engine.event_bus.subscribe("tool.executed", self._on_tool_executed)
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

    def execute_action(self, grid_coord: str, action: str, data: str = None) -> bool:
        """Translate Set-of-Mark grid coordinates (e.g. A1, D4) to screen coordinates and act."""
        try:
            import pyautogui
        except ImportError:
            # Fallback for headless test environments
            logger.info(f"[Mock Action] {action} at {grid_coord} with data {data}")
            return True

        # Resolve grid coordinates to screen pixels (Assuming 4x4 Grid)
        # Columns: A, B, C, D (1-4). Rows: 1, 2, 3, 4
        col_char = grid_coord[0].upper()
        row_char = grid_coord[1]
        
        col_idx = ord(col_char) - ord('A')
        row_idx = int(row_char) - 1
        
        screen_w, screen_h = pyautogui.size()
        cell_w = screen_w / 4
        cell_h = screen_h / 4
        
        x = int(col_idx * cell_w + cell_w / 2)
        y = int(row_idx * cell_h + cell_h / 2)
        
        logger.info(f"Visual Action: {action} on {grid_coord} mapped to ({x}, {y})")
        
        if action == "click":
            pyautogui.click(x, y)
        elif action == "double_click":
            pyautogui.doubleClick(x, y)
        elif action == "type" and data:
            pyautogui.click(x, y)
            pyautogui.typewrite(data)
            
        return True

    # --- Macro Recording and Execution ---

    def _on_tool_executed(self, event):
        if not self.is_recording:
            return
        payload = getattr(event, "payload", getattr(event, "data", {}))
        if isinstance(payload, dict):
            tool_name = payload.get("tool_name")
            arguments = payload.get("arguments", {})
            if tool_name:
                self.current_macro_steps.append({"tool": tool_name, "arguments": arguments})

    def start_recording(self) -> bool:
        self.is_recording = True
        self.current_macro_steps = []
        logger.info("Macro recording started.")
        return True

    def stop_recording(self, macro_name: str) -> Optional[str]:
        self.is_recording = False
        if not self.current_macro_steps:
            logger.warning("Stopped recording but no steps were captured.")
            return None
        
        macro_id = str(uuid.uuid4())
        macro_data = {
            "id": macro_id,
            "name": macro_name,
            "created_at": datetime.now().isoformat(),
            "steps": self.current_macro_steps
        }
        file_path = self.macros_dir / f"{macro_id}.json"
        file_path.write_text(json.dumps(macro_data, indent=2))
        self.current_macro_steps = []
        logger.info(f"Macro '{macro_name}' saved with {len(macro_data['steps'])} steps.")
        return macro_id

    def list_macros(self) -> List[Dict[str, Any]]:
        macros = []
        for file_path in self.macros_dir.glob("*.json"):
            try:
                data = json.loads(file_path.read_text())
                macros.append(data)
            except Exception:
                pass
        return macros
        
    def delete_macro(self, macro_id: str) -> bool:
        file_path = self.macros_dir / f"{macro_id}.json"
        if file_path.exists():
            file_path.unlink()
            return True
        return False

    def execute_macro(self, macro_id: str) -> bool:
        file_path = self.macros_dir / f"{macro_id}.json"
        if not file_path.exists():
            logger.error(f"Macro {macro_id} not found.")
            return False
            
        try:
            macro_data = json.loads(file_path.read_text())
        except Exception as e:
            logger.error(f"Failed to read macro {macro_id}: {e}")
            return False
            
        if not self.engine or not hasattr(self.engine, "registry"):
            logger.error("Engine or registry not available to execute macro.")
            return False
            
        steps = macro_data.get("steps", [])
        total_steps = len(steps)
        
        def _run():
            from axiom.core.events import Event
            for i, step in enumerate(steps, 1):
                tool_name = step.get("tool")
                arguments = step.get("arguments", {})
                
                if hasattr(self.engine, "event_bus"):
                    self.engine.event_bus.publish(Event(
                        event_type="macro.step",
                        source="AutomationPlugin",
                        data={
                            "macro_id": macro_id,
                            "step": i,
                            "total": total_steps,
                            "action": f"{tool_name}({arguments})"
                        }
                    ))
                
                try:
                    self.engine.registry.execute(tool_name, **arguments)
                except Exception as e:
                    logger.error(f"Macro step {i} failed: {e}")
                    break
                    
            if hasattr(self.engine, "event_bus"):
                self.engine.event_bus.publish(Event(
                    event_type="macro.completed",
                    source="AutomationPlugin",
                    data={"macro_id": macro_id}
                ))

        thread = threading.Thread(target=_run, daemon=True)
        thread.start()
        return True
