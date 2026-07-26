"""Agent / dispatcher that wires LLM -> parser -> actions -> feedback."""

from brain.parser import parse
from brain.intent_parser import parse_intent
from core.llm import generate, extract_text_from_ndjson
import re
import time
from utils.logger import get_logger
from utils.config import get_config
from utils.system import get_default_browser
from actions import execute_instruction
from actions.executor import execute_action_sequence, execute_and_record
from brain.context_memory import get_context_memory
from security.validator import find_allowed_app

logger = get_logger(__name__)


class Agent:
    def __init__(self, model: str | None = None, system_prompt: str | None = None):
        cfg = get_config() or {}
        self.model = model or cfg.get('ollama', {}).get('model', 'llama2')
        # system_prompt may be provided programmatically or read from config
        self.base_system_prompt = (
            system_prompt if system_prompt is not None else cfg.get('system_prompt', '')
        )
        self.available_apps = self._detect_available_apps()
    
    def _detect_available_apps(self) -> list:
        """Detect which apps are actually available on the system."""
        cfg = get_config() or {}
        allowed_apps = cfg.get('allowed_apps', {})
        available = []
        
        # Detect system default browser and prioritize it
        default_browser = self._get_default_browser()
        
        for app_name in sorted(allowed_apps.keys()):
            if find_allowed_app(app_name):
                available.append(app_name)
        
        # If we have a default browser, move it to the front
        if default_browser and default_browser in available:
            available.remove(default_browser)
            available.insert(0, default_browser)
        
        return available
    
    def _get_default_browser(self) -> str:
        """Get the system default browser (delegates to shared util)."""
        return get_default_browser()
    
    def _get_system_prompt(self) -> str:
        """Get the system prompt with dynamically injected default browser."""
        prompt = self.base_system_prompt
        
        # Get the default browser and replace DEFAULT_BROWSER placeholder
        default_browser = self._get_default_browser()
        if default_browser:
            # Replace all occurrences of DEFAULT_BROWSER with actual browser name
            prompt = prompt.replace("DEFAULT_BROWSER", default_browser)
            # Prepend a prominent message about the default browser
            browser_info = f"=== SYSTEM INFO ===\nDEFAULT BROWSER: {default_browser}\nWhen user doesn't specify a browser, ALWAYS use: {default_browser}\n\n"
            prompt = browser_info + prompt
        
        # Add available apps list
        if self.available_apps:
            available_str = ", ".join(self.available_apps)
            prompt += f"\nAVAILABLE APPS: {available_str}\n"
        
        return prompt

    def _check_suggestions(self, result: dict) -> dict:
        """Run the observer and attach any new suggestions to *result*.

        Suggestions are added as a 'suggestions' key and appended to
        the human-readable message so existing UI code displays them
        without modification.
        """
        cfg = get_config() or {}
        if not cfg.get('observer', {}).get('enabled', True):
            return result
        try:
            from brain.observer import get_observer
            suggestions = get_observer().check()
            if suggestions:
                result['suggestions'] = [
                    {'pattern_id': s.pattern_id, 'message': s.message,
                     'confidence': s.confidence}
                    for s in suggestions
                ]
                text = '\n'.join(f"\U0001f4a1 {s.message}" for s in suggestions)
                msg = result.get('result', {}).get('message', '')
                result['result']['message'] = f"{msg}\n\n{text}" if msg else text
        except Exception as e:
            logger.debug("Observer check skipped: %s", e)
        return result

    def _build_feedback_prompt(self, original_prompt: str, action: str,
                               params: str, error_msg: str) -> str:
        """Build a prompt that includes failure context for the LLM.

        Tells the LLM what was tried, why it failed, and asks it to
        produce a corrected instruction.
        """
        ctx = get_context_memory()
        recent = ctx.get_action_history(3)
        history_lines = []
        for entry in recent:
            status = 'OK' if entry['ok'] else 'FAILED'
            history_lines.append(
                f"  - {entry['action']} {entry['params']} -> {status}: {entry['message']}"
            )
        history_block = '\n'.join(history_lines) if history_lines else '  (none)'

        return (
            f"The user asked: {original_prompt}\n\n"
            f"You previously responded with action: {action} {params}\n"
            f"But it FAILED with error: {error_msg}\n\n"
            f"Recent action history:\n{history_block}\n\n"
            f"Please try a DIFFERENT approach to accomplish the user's request.\n"
            f"Use a different action or different parameters.\n"
            f"Respond using the same instruction format."
        )

    def handle_prompt(self, prompt: str, _depth: int = 0) -> dict:
        """Process a user prompt through the event pipeline.

        Returns a dict with keys: 'raw', 'parsed', 'result'.
        
        Args:
            prompt: The user prompt to process
            _depth: Internal recursion depth tracker (max 2 levels)
        """
        # Limit recursion to prevent infinite loops
        if _depth > 2:
            return {'raw': '', 'parsed': {'type': 'message', 'message': ''}, 
                    'result': {'ok': False, 'message': 'Task too complex - recursion limit reached'}}
        try:
            # STEP 1: Try intent parser first (for smart action sequencing)
            action_plan = parse_intent(prompt)
            if action_plan:
                logger.info("Intent parsed: %s actions detected", len(action_plan.actions))
                instructions = action_plan.to_instructions()
                
                # Convert to instructions dict format for execution
                if instructions['type'] == 'instruction':
                    # Single action
                    ok, msg = execute_instruction(instructions['action'], instructions['params'])
                    return self._check_suggestions(
                        {'raw': '', 'parsed': instructions, 'result': {'ok': ok, 'message': msg}})
                else:
                    # Multiple actions
                    ok, msg = execute_action_sequence(instructions['instructions'])
                    return self._check_suggestions(
                        {'raw': '', 'parsed': instructions, 'result': {'ok': ok, 'message': msg}})
            
            # STEP 2: Quick local intent handling for simple app launching
            # if the user explicitly asked to open/start/launch app(s)
            m0 = re.match(r"^(open|launch|start|ouvre|lance|démarre|lancez|ouvert)\s+(?:the\s+|l[ea]\s+|l['']|un\s+|une\s+)?(?:app\s+)?(?P<apps>.+)$", prompt.strip(), re.IGNORECASE)
            if m0:
                apps_str = m0.group('apps').strip()
                words = apps_str.split()
                if len(words) <= 2:
                    # Simple case: try to launch as apps
                    app_list = re.split(r'\s+(?:et|and)\s+|,\s*', apps_str, flags=re.IGNORECASE)
                    app_list = [a.strip().strip('"\'') for a in app_list if a.strip()]
                    
                    if app_list:
                        results = []
                        for appname in app_list:
                            ok, msg = execute_instruction('open_app', f'name="{appname}"')
                            results.append({'app': appname, 'ok': ok, 'msg': msg})
                        
                        # Return success if at least one app launched
                        any_ok = any(r['ok'] for r in results)
                        if any_ok:
                            msg_parts = [f"Launched: {r['app']}" for r in results if r['ok']]
                            full_msg = ', '.join(msg_parts)
                            return self._check_suggestions(
                                {'raw': '', 'parsed': {'type': 'instruction', 'action': 'open_app', 'params': apps_str},
                                 'result': {'ok': True, 'message': full_msg}})
                else:
                    # Complex multi-step task: let the LLM handle it
                    logger.info("Complex task detected, delegating to LLM: %s", prompt)
            
            # STEP 3: Send to LLM for processing
            logger.info("Sending prompt to LLM")
            system_prompt = self._get_system_prompt()
            if system_prompt:
                full_prompt = f"{system_prompt.strip()}\n\n{prompt}"
            else:
                full_prompt = prompt

            raw = generate(full_prompt, model=self.model)
            logger.debug("LLM raw response (first 200 chars): %s", raw[:200])
            
            # Clean up NDJSON if present
            cleaned = extract_text_from_ndjson(raw) or raw
            
            # STEP 4: Parse the LLM response
            parsed = parse(cleaned)
            logger.debug("Parsed type: %s", parsed.get('type'))
            
            # STEP 5: Execute based on parsed type
            if parsed['type'] == 'instruction':
                # Single instruction (backward compatible)
                action = parsed.get('action')
                params = parsed.get('params', '')
                ok, msg = execute_and_record(action, params)
                if not ok and _depth < 2:
                    logger.info("Action failed, retrying with feedback (depth=%d)", _depth)
                    feedback = self._build_feedback_prompt(prompt, action, params, msg)
                    return self.handle_prompt(feedback, _depth=_depth + 1)
                return self._check_suggestions(
                    {'raw': raw, 'parsed': parsed, 'result': {'ok': ok, 'message': msg}})
            
            elif parsed['type'] == 'instructions':
                # Multiple instructions (new format from parser)
                instructions = parsed.get('instructions', [])
                ok, msg = execute_action_sequence(instructions)
                if not ok and _depth < 2:
                    logger.info("Action sequence failed, retrying with feedback (depth=%d)", _depth)
                    failed_summary = msg
                    feedback = self._build_feedback_prompt(
                        prompt, 'action_sequence',
                        str([i.get('action') for i in instructions]), failed_summary
                    )
                    return self.handle_prompt(feedback, _depth=_depth + 1)
                return self._check_suggestions(
                    {'raw': raw, 'parsed': parsed, 'result': {'ok': ok, 'message': msg}})
            
            elif parsed['type'] == 'message':
                # Plain message response
                text = parsed.get('message', '') or ''
                
                # Check for backticked commands
                m = re.search(r"`([^`]+)`", text)
                if m:
                    candidate = m.group(1).strip()
                    cmd = candidate.split()[0]
                    
                    # Try to launch as app
                    ok, msg = execute_instruction('open_app', f'name="{cmd}"')
                    if ok:
                        return {'raw': raw, 'parsed': parsed, 'result': {'ok': True, 'message': f'Launched app: {cmd}'}}
                    
                    # Try as command
                    ok2, msg2 = execute_instruction('run_command', f'cmd="{candidate}"')
                    if ok2:
                        return {'raw': raw, 'parsed': parsed, 'result': {'ok': True, 'message': msg2}}
                
                # Return plain message
                return {'raw': raw, 'parsed': parsed, 'result': {'ok': True, 'message': text}}
            
            elif parsed['type'] == 'no_action':
                return {'raw': raw, 'parsed': parsed, 'result': {'ok': True, 'message': 'No action needed'}}
            
            else:
                return {'raw': raw, 'parsed': parsed, 'result': {'ok': False, 'message': 'Unknown response type'}}
        
        except Exception as e:
            logger.exception('Agent pipeline error')
            return {'raw': '', 'parsed': {'type': 'message', 'message': ''}, 
                    'result': {'ok': False, 'message': f'Error: {str(e)}'}}
    
    def handle_vision_task(self, task: str, max_steps: int = 10) -> dict:
        """Process a desktop control task using vision + LLM.
        
        Takes screenshots, analyzes them, and controls the desktop.
        
        Returns:
            Result dict with success status and action history.
        """
        from brain.vision import VisionAgent
        try:
            vision_agent = VisionAgent(model=self.model)
            result = vision_agent.run_vision_task(task, max_steps=max_steps)
            return result
        except Exception as e:
            logger.exception('Vision task error')
            return {'ok': False, 'message': f'Vision task failed: {e}'}
