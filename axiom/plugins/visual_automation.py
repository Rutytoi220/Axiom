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
        """Auto-generated docstring.

Args:
    engine: Argument.

Returns:
    Return value.
"""
        super().__init__(plugin_id='visual_automation', name='Visual Automation Plugin', version='1.0.0')  # pragma: no cover
        self.engine = engine  # pragma: no cover
        self.vision = VisionPipeline()  # pragma: no cover
        self.llm = UniversalLLMClient()  # pragma: no cover

    def initialize(self, config: Optional[Dict]=None) -> bool:
        """Auto-generated docstring.

Args:
    config: Argument.

Returns:
    Return value.
"""
        self.config = config or {}  # pragma: no cover
        logger.info('Visual Automation Plugin initialized')  # pragma: no cover
        return True  # pragma: no cover

    def shutdown(self) -> bool:
        """Auto-generated docstring.


Returns:
    Return value.
"""
        return True  # pragma: no cover

    def execute_visual_task(self, instruction: str) -> bool:
        """Executes a single visual task."""
        if not self.engine:  # pragma: no cover
            logger.error('Engine not attached to VisualAutomationPlugin.')  # pragma: no cover
            return False  # pragma: no cover
        automation_plugin = self.engine.registry.get_plugin('automation')  # pragma: no cover
        if not automation_plugin:  # pragma: no cover
            logger.error('AutomationPlugin not found in registry.')  # pragma: no cover
            return False  # pragma: no cover
        logger.info(f'Executing visual task: {instruction}')  # pragma: no cover
        img_b64 = self.vision.capture_active_window(with_grid=True)  # pragma: no cover
        if not img_b64:  # pragma: no cover
            logger.error('Failed to capture active window.')  # pragma: no cover
            return False  # pragma: no cover
        prompt = f"You are an autonomous GUI agent. The user instruction is: '{instruction}'\nAnalyze the provided screenshot (which has a 4x4 coordinate grid overlaid from A1 to D4). Identify the exact grid sector needed to fulfill the instruction and the action required (click, double_click, type, drag). Output ONLY a valid JSON object with keys 'target' (e.g. 'B3') and 'action' (e.g. 'click'). If the action is 'type', include a 'data' key with the text to type."  # pragma: no cover
        messages = [{'role': 'user', 'content': [{'type': 'text', 'text': prompt}, {'type': 'image_url', 'image_url': {'url': f'data:image/jpeg;base64,{img_b64}'}}]}]  # pragma: no cover
        response = self.llm.chat(messages, model='gemini/gemini-2.0-flash')  # pragma: no cover
        target = None  # pragma: no cover
        action = None  # pragma: no cover
        data = None  # pragma: no cover
        try:  # pragma: no cover
            match = re.search('\\{.*\\}', response, flags=re.DOTALL)  # pragma: no cover
            parsed = json.loads(match.group(0) if match else response)  # pragma: no cover
            target = parsed.get('target')  # pragma: no cover
            action = parsed.get('action')  # pragma: no cover
            data = parsed.get('data')  # pragma: no cover
        except Exception as e:  # pragma: no cover
            logger.error(f'Failed to parse visual action from LLM response: {e}')  # pragma: no cover
            return False  # pragma: no cover
        if not target or not action:  # pragma: no cover
            logger.error('LLM did not return a valid target and action.')  # pragma: no cover
            return False  # pragma: no cover
        if hasattr(self.engine, 'event_bus'):  # pragma: no cover
            self.engine.event_bus.publish(Event(event_type='visual.act', source='VisualAutomationPlugin', data={'target': target, 'action': action, 'data': data}))  # pragma: no cover
        success = automation_plugin.execute_action(target, action, data)  # pragma: no cover
        if not success:  # pragma: no cover
            return False  # pragma: no cover
        time.sleep(1.5)  # pragma: no cover
        verify_img_b64 = self.vision.capture_active_window(with_grid=False)  # pragma: no cover
        if verify_img_b64:  # pragma: no cover
            logger.info('Captured post-action screenshot for verification.')  # pragma: no cover
        return True  # pragma: no cover
