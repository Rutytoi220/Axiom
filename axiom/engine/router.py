"""Dynamic Inference Router for AXIOM v2.

Routes incoming prompts to the most efficient Ollama model based on task
complexity using an LLM-driven micro-model classification.
"""
import logging
from typing import Dict, Any, List, Optional
import time
from enum import Enum
from pydantic import BaseModel
import litellm
from axiom.llm.universal_client import UniversalLLMClient
from axiom.engine.telemetry import HardwareTelemetryDaemon
from axiom.engine.cloud_adapter import CloudAdapter
from axiom.config import get_config
logger = logging.getLogger(__name__)

class IntentCategory(str, Enum):
    """Auto-generated docstring.

"""
    CODE = 'CODE'
    CHAT = 'CHAT'
    VISION = 'VISION'
    SYSTEM = 'SYSTEM'
    REASONING = 'REASONING'

class RouterDecision(BaseModel):
    """Auto-generated docstring.

"""
    category: IntentCategory

class SmartRouter:
    """Smart wrapper around UniversalLLMClient that dynamically routes prompts."""

    def __init__(self, llm_client: UniversalLLMClient, telemetry_daemon: Optional[HardwareTelemetryDaemon]=None, event_bus=None):
        """Auto-generated docstring.

Args:
    llm_client: Argument.
    telemetry_daemon: Argument.
    event_bus: Argument.

Returns:
    Return value.
"""
        self.llm_client = llm_client
        self.telemetry = telemetry_daemon
        self.event_bus = event_bus
        self.cloud_adapter = CloudAdapter()
        self.model_tiers = {IntentCategory.CHAT: 'ollama/llama3.1:latest', IntentCategory.SYSTEM: 'ollama/qwen3:8b', IntentCategory.CODE: 'ollama/qwen3-coder:latest', IntentCategory.VISION: 'ollama/qwen3-vl:2b', IntentCategory.REASONING: 'ollama/laguna-xs-2.1:q4_K_M'}
        self._current_active_model: Optional[str] = None

    def _has_image(self, messages: List[Dict[str, Any]]) -> bool:
        """Check if any message contains an image payload."""
        for msg in messages:
            content = msg.get('content', '')
            if isinstance(content, list):
                for part in content:
                    if isinstance(part, dict) and part.get('type') == 'image_url':
                        return True
        return False

    def _classify_task(self, messages: List[Dict[str, Any]], tool_schemas: Optional[List[Dict[str, Any]]]=None) -> IntentCategory:
        """Classify the prompt complexity into a Task Intent using a micro-model."""
        if not messages:
            return IntentCategory.CHAT
        user_messages = [m.get('content', '') for m in messages if m.get('role') == 'user']
        user_texts = []
        for content in user_messages:
            if isinstance(content, str):
                user_texts.append(content)
            elif isinstance(content, list):
                user_texts.extend([p.get('text', '') for p in content if p.get('type') == 'text'])
        user_text = '\n'.join(user_texts)
        if not user_text:
            return IntentCategory.SYSTEM
            
        if self._has_image(messages):
            return IntentCategory.VISION
            
        system_prompt = "You are a semantic intent router. Classify the user's request into one of the following categories:\nCODE: For programming, refactoring, debugging, or execution.\nCHAT: For general conversation, greetings, or short chat.\nSYSTEM: For orchestrating tools, reading files, or complex multi-step OS tasks.\nREASONING: For deep logical puzzles, math, or complex analysis requiring advanced chain-of-thought.\nOutput strictly valid JSON conforming to the requested schema."
        try:
            response = litellm.completion(model='ollama/qwen3:0.6b', api_base='http://localhost:11434', messages=[{'role': 'system', 'content': system_prompt}, {'role': 'user', 'content': f'User Request: {user_text}'}], temperature=0.0, max_tokens=60, response_format=RouterDecision)
            content = response.choices[0].message.content
            import json
            decision = RouterDecision.model_validate_json(content)
            if decision.category == IntentCategory.VISION:
                return IntentCategory.SYSTEM
            return decision.category
        except Exception as e:
            logger.warning(f'SmartRouter classification failed: {e}. Falling back to SYSTEM intent.')
            return IntentCategory.SYSTEM

    def _route_request(self, messages: List[Dict[str, Any]], tool_schemas: Optional[List[Dict[str, Any]]]=None) -> str:
        """Determine which model to use."""
        config = get_config()
        if getattr(config, 'model_selection_mode', 'auto') == 'manual':
            selected_model = getattr(config, 'ollama_model', 'ollama/qwen3:8b')
            if self._current_active_model and self._current_active_model != selected_model:
                logger.info(f'SmartRouter (Manual Override) Swapping Model: {self._current_active_model} -> {selected_model}')
            elif not self._current_active_model:
                logger.info(f'SmartRouter (Manual Override) initializing with Model: {selected_model}')
            self._current_active_model = selected_model
            if self.event_bus:
                from axiom.core.events import Event
                self.event_bus.publish(Event('model.routed', 'SmartRouter', data={'target': selected_model, 'intent': 'MANUAL'}))
            return selected_model

        target_intent = self._classify_task(messages, tool_schemas)
        if target_intent == IntentCategory.CODE:
            if self.telemetry and self.telemetry.latest_state.get('warning'):
                ram_avail = self.telemetry.latest_state.get('ram_available_percent', 0)
                config = get_config()
                if getattr(config, 'allow_cloud_fallback', False) and self.cloud_adapter.is_configured:
                    logger.warning(f'Local VRAM exhausted ({ram_avail:.1f}%). Bursting to Cloud Fallback.')
                    return 'cloud'
                else:
                    logger.warning(f'Emergency Downgrade: Code task requested, but RAM is critically low ({ram_avail:.1f}%). Downgrading to Orchestration to prevent OOM crash.')
                    target_intent = IntentCategory.SYSTEM
        target_model_name = self.model_tiers.get(target_intent)
        selected_model: str = str(target_model_name or getattr(getattr(self.llm_client, 'config', None), 'model', 'ollama/qwen3:8b'))
        if self._current_active_model and self._current_active_model != selected_model:
            logger.info(f'SmartRouter Swapping Model: {self._current_active_model} -> {selected_model} (Intent: {target_intent.value})')
        elif not self._current_active_model:
            logger.info(f'SmartRouter initializing with Model: {selected_model} (Intent: {target_intent.value})')
        self._current_active_model = selected_model
        if self.event_bus:
            from axiom.core.events import Event
            self.event_bus.publish(Event('model.routed', 'SmartRouter', data={'target': selected_model, 'intent': target_intent.value}))
        return selected_model

    def chat(self, messages: List[Dict[str, Any]], **kwargs) -> str:
        """Route and execute a standard chat completion."""
        target_model = self._route_request(messages)
        if target_model == 'cloud':
            return self.cloud_adapter.chat(messages, **kwargs)
        has_config = hasattr(self.llm_client, 'config') and hasattr(self.llm_client.config, 'model')
        original_model = self.llm_client.config.model if has_config else None
        try:
            if has_config:
                self.llm_client.config.model = target_model
            return self.llm_client.chat(messages, **kwargs)
        finally:
            if has_config and original_model is not None:
                self.llm_client.config.model = original_model

    def chat_with_tools(self, messages: List[Dict[str, Any]], tool_schemas: List[Dict[str, Any]], **kwargs) -> Any:
        """Route and execute a tool-enabled chat completion."""
        target_model = self._route_request(messages, tool_schemas)
        if target_model == 'cloud':
            return self.cloud_adapter.chat_with_tools(messages, tool_schemas, **kwargs)
        has_config = hasattr(self.llm_client, 'config') and hasattr(self.llm_client.config, 'model')
        original_model = self.llm_client.config.model if has_config else None
        try:
            if has_config:
                self.llm_client.config.model = target_model
            return self.llm_client.chat_with_tools(messages, tool_schemas, **kwargs)
        finally:
            if has_config and original_model is not None:
                self.llm_client.config.model = original_model

    def is_available(self) -> bool:
        """Check availability."""
        return self.llm_client.is_available()
