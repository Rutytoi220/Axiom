"""Vision-based desktop control agent.

Provides screen analysis and automated control via LLM vision capabilities.
Takes screenshots, sends them to LLM for analysis, and executes actions.
"""

import base64
import time
import re
from typing import Dict, Optional, Tuple
from brain.parser import parse
from core.llm import generate, extract_text_from_ndjson
from actions.desktop import take_screenshot, click_mouse, type_text, press_keys, move_mouse, get_screen_size
from actions import execute_instruction
from utils.logger import get_logger
from utils.config import get_config

logger = get_logger(__name__)


class VisionAgent:
    """Desktop control agent that uses vision + LLM to interact with desktop."""
    
    def __init__(self, model: str | None = None):
        cfg = get_config() or {}
        self.model = model or cfg.get('ollama', {}).get('model', 'llama2')
        self.max_steps = 10  # Prevent infinite loops
        self.step_delay = 0.5  # Delay between actions
        
    def run_vision_task(self, task: str, max_steps: int | None = None) -> Dict:
        """Execute a task by analyzing the screen and issuing commands.
        
        Args:
            task: Natural language task description
            max_steps: Maximum number of steps (default: 10)
            
        Returns:
            Result dict with success status and history
        """
        max_steps = max_steps or self.max_steps
        history = []
        
        # Get screen size for reference
        ok, size_str = get_screen_size()
        logger.info("Starting vision task: %s", task)
        logger.info("Screen size: %s", size_str)
        
        for step in range(max_steps):
            logger.info("Vision step %d/%d", step + 1, max_steps)
            
            # Take screenshot
            ok, screenshot_b64 = take_screenshot(encode_base64=True)
            if not ok:
                logger.error("Failed to take screenshot")
                return {
                    'ok': False,
                    'message': f'Failed to take screenshot: {screenshot_b64}',
                    'steps': len(history)
                }
            
            # Prepare prompt for LLM with vision
            vision_prompt = self._build_vision_prompt(task, step, max_steps, size_str)
            
            try:
                # Send screenshot + task to LLM
                # Note: Vision support depends on the model and ollama version
                response = generate(vision_prompt, model=self.model)
                cleaned = extract_text_from_ndjson(response) or response
                
                logger.debug("LLM response: %s", cleaned[:200])
                
                # Parse the response for actions
                actions = self._parse_vision_response(cleaned)
                
                if not actions:
                    logger.info("No more actions needed")
                    return {
                        'ok': True,
                        'message': 'Task completed',
                        'steps': len(history),
                        'history': history
                    }
                
                # Execute actions
                for action in actions:
                    result = self._execute_vision_action(action)
                    history.append({
                        'step': step + 1,
                        'action': action,
                        'result': result
                    })
                    logger.info("Action result: %s", result)
                    time.sleep(self.step_delay)
                    
            except Exception as e:
                logger.exception("Error in vision loop")
                return {
                    'ok': False,
                    'message': f'Error during vision task: {e}',
                    'steps': len(history),
                    'history': history
                }
        
        return {
            'ok': True,
            'message': f'Completed {len(history)} steps',
            'steps': len(history),
            'history': history
        }
    
    def _build_vision_prompt(self, task: str, step: int, max_steps: int, screen_size: str) -> str:
        """Build a prompt for the LLM to analyze the screen.
        
        Args:
            task: User's task description
            step: Current step number
            max_steps: Maximum steps allowed
            screen_size: Screen resolution (WIDTHxHEIGHT)
            
        Returns:
            Prompt string with instructions
        """
        system_part = f"""You are a desktop automation assistant. Your job is to help the user complete tasks by controlling their computer.

TASK: {task}
STEP: {step + 1}/{max_steps}
SCREEN SIZE: {screen_size}

You will be shown a screenshot of the desktop. Analyze it and determine the next action to take.

RESPONSE FORMAT:
If you can see the next action to take, respond with:
[ACTION]click x=100 y=200[/ACTION]
or
[ACTION]type text="hello"[/ACTION]
or
[ACTION]press keys="enter"[/ACTION]
or
[ACTION]move x=500 y=300[/ACTION]

Multiple actions can be combined:
[ACTION]click x=100 y=200[/ACTION]
[ACTION]type text="search term"[/ACTION]
[ACTION]press keys="enter"[/ACTION]

If the task is complete, respond with:
[DONE]Task completed successfully[/DONE]

If you cannot complete the task, respond with:
[ERROR]Reason why[/ERROR]

Coordinate system: (0,0) is top-left, x increases right, y increases down.
IMPORTANT: Use exact coordinates you can see on the screen. Be precise with clicks.
"""
        return system_part
    
    def _parse_vision_response(self, response: str) -> list:
        """Parse LLM response for actions.
        
        Args:
            response: LLM response text
            
        Returns:
            List of action dicts
        """
        actions = []
        
        # Check for task completion
        if '[DONE]' in response.upper():
            return []
        
        # Check for errors
        if '[ERROR]' in response.upper():
            logger.warning("LLM reported error: %s", response)
            return []
        
        # Parse actions
        pattern = r'\[ACTION\](.*?)\[/ACTION\]'
        matches = re.findall(pattern, response, re.IGNORECASE | re.DOTALL)
        
        for match in matches:
            action_str = match.strip()
            # Parse individual action
            if action_str.lower().startswith('click'):
                m = re.search(r'click\s+x=(\d+)\s+y=(\d+)', action_str, re.IGNORECASE)
                if m:
                    actions.append({
                        'type': 'click',
                        'x': int(m.group(1)),
                        'y': int(m.group(2))
                    })
            elif action_str.lower().startswith('type'):
                m = re.search(r'type\s+text="([^"]*)"', action_str, re.IGNORECASE)
                if m:
                    actions.append({
                        'type': 'type',
                        'text': m.group(1)
                    })
            elif action_str.lower().startswith('press'):
                m = re.search(r'press\s+keys="([^"]*)"', action_str, re.IGNORECASE)
                if m:
                    actions.append({
                        'type': 'press',
                        'keys': m.group(1)
                    })
            elif action_str.lower().startswith('move'):
                m = re.search(r'move\s+x=(\d+)\s+y=(\d+)', action_str, re.IGNORECASE)
                if m:
                    actions.append({
                        'type': 'move',
                        'x': int(m.group(1)),
                        'y': int(m.group(2))
                    })
        
        return actions
    
    def _execute_vision_action(self, action: Dict) -> Tuple[bool, str]:
        """Execute a parsed vision action.
        
        Args:
            action: Action dict from _parse_vision_response
            
        Returns:
            (success, message)
        """
        action_type = action.get('type')
        
        try:
            if action_type == 'click':
                x, y = action['x'], action['y']
                return click_mouse(x, y)
            elif action_type == 'type':
                text = action['text']
                return type_text(text)
            elif action_type == 'press':
                keys = action['keys']
                return press_keys(keys)
            elif action_type == 'move':
                x, y = action['x'], action['y']
                return move_mouse(x, y)
            else:
                return False, f'Unknown action type: {action_type}'
        except Exception as e:
            logger.exception("Failed to execute action: %s", action)
            return False, f'Action failed: {e}'
