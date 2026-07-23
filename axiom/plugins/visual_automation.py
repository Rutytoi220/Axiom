import time
import logging
import json
import re
from typing import Optional, Dict, Any
from axiom.plugins.base_plugin import BasePlugin
from axiom.perception.vision_pipeline import VisionPipeline
from axiom.llm.universal_client import UniversalLLMClient
from axiom.core.events import Event

logger = logging.getLogger(__name__)

class VisualAutomationPlugin(BasePlugin):
    """High-level visual controller bridging VisionPipeline and AutomationPlugin."""

    def __init__(self, engine=None):
        super().__init__(
            plugin_id="visual_automation",
            name="Visual Automation Plugin",
            version="1.0.0"
        )
        self.engine = engine
        self.vision = VisionPipeline()
        self.llm = UniversalLLMClient()

    def initialize(self, config: Optional[Dict] = None) -> bool:
        self.config = config or {}
        logger.info("Visual Automation Plugin initialized")
        return True

    def shutdown(self) -> bool:
        return True

    def execute_visual_task(self, instruction: str) -> bool:
        """Executes a single visual task."""
        if not self.engine:
            logger.error("Engine not attached to VisualAutomationPlugin.")
            return False

        automation_plugin = self.engine.registry.get_plugin("automation")
        if not automation_plugin:
            logger.error("AutomationPlugin not found in registry.")
            return False

        logger.info(f"Executing visual task: {instruction}")

        # Step 1: Capture
        img_b64 = self.vision.capture_active_window(with_grid=True)
        if not img_b64:
            logger.error("Failed to capture active window.")
            return False

        # Step 2: Locate
        prompt = (
            "You are an autonomous GUI agent. "
            f"The user instruction is: '{instruction}'\n"
            "Analyze the provided screenshot (which has a 4x4 coordinate grid overlaid from A1 to D4). "
            "Identify the exact grid sector needed to fulfill the instruction and the action required (click, double_click, type, drag). "
            "Output ONLY a valid JSON object with keys 'target' (e.g. 'B3') and 'action' (e.g. 'click'). "
            "If the action is 'type', include a 'data' key with the text to type."
        )

        messages = [
            {"role": "user", "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}}
            ]}
        ]

        response = self.llm.chat(messages, model="gemini/gemini-2.0-flash")
        
        target = None
        action = None
        data = None
        
        try:
            match = re.search(r"\{.*\}", response, flags=re.DOTALL)
            parsed = json.loads(match.group(0) if match else response)
            target = parsed.get("target")
            action = parsed.get("action")
            data = parsed.get("data")
        except Exception as e:
            logger.error(f"Failed to parse visual action from LLM response: {e}")
            return False

        if not target or not action:
            logger.error("LLM did not return a valid target and action.")
            return False

        # Event Bus Broadcast
        if hasattr(self.engine, "event_bus"):
            self.engine.event_bus.publish(Event(
                event_type="visual.act",
                source="VisualAutomationPlugin",
                data={"target": target, "action": action, "data": data}
            ))

        # Step 3: Act
        success = automation_plugin.execute_action(target, action, data)
        if not success:
            return False

        # Step 4: Verify
        time.sleep(1.5)
        verify_img_b64 = self.vision.capture_active_window(with_grid=False)
        if verify_img_b64:
            logger.info("Captured post-action screenshot for verification.")
            
        return True
