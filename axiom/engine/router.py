"""Dynamic Inference Router for AXIOM v2.

Routes incoming prompts to the most efficient Ollama model based on task
complexity (Tier 1 vs Tier 2 vs Tier 3). Intercepts routing if telemetry
indicates a low-memory (OOM) situation and forces a graceful downgrade.
"""

import logging
from typing import Dict, Any, List, Optional
import time

from axiom.llm.ollama_client import OllamaClient, OllamaConfig
from axiom.engine.telemetry import HardwareTelemetryDaemon
from axiom.engine.cloud_adapter import CloudAdapter
from axiom.config import get_config

logger = logging.getLogger(__name__)

class InferenceRouter:
    """Smart wrapper around OllamaClient that dynamically routes prompts."""

    def __init__(self, llm_client: OllamaClient, telemetry_daemon: Optional[HardwareTelemetryDaemon] = None):
        self.llm_client = llm_client
        self.telemetry = telemetry_daemon
        self.cloud_adapter = CloudAdapter()
        
        # Configure the routing matrix (model names to map to intents)
        self.model_tiers = {
            "chat": "llama3.1:latest",          # Promoted to 8B class for multi-turn stability
            "orchestration": "llama3.1:latest", # General Orchestration/Assistive Context
            "code": "qwen3-coder:latest"        # Code Generation/Refactoring
        }
        self._current_active_model = None

    def _classify_task(self, messages: List[Dict[str, Any]], tool_schemas: Optional[List[Dict[str, Any]]] = None) -> str:
        """Classify the prompt complexity into a Task Intent."""
        if not messages:
            return "chat"
        # Isolate user text for accurate heuristic checking without system prompt pollution
        user_messages = [m.get("content", "") for m in messages if isinstance(m.get("content"), str) and m.get("role") == "user"]
        user_text = "\n".join(user_messages).lower()
        
        # Fallback to full text if no user messages exist
        if not user_text:
            user_text = "\n".join([m.get("content", "") for m in messages if isinstance(m.get("content"), str)]).lower()
        
        import re
        
        # 1. Code Heuristics: Only trigger on explicit keywords in user prompt
        code_pattern = r'\b(python|javascript|refactor|debug|compile|class|import|traceback|pytest|git)\b|\.py\b'
        if re.search(code_pattern, user_text):
            return "code"
            
        # 2. Check for File Paths, Extensions, explicit Tool Verbs, or Contextual Pronouns
        # These MUST override the short-prompt chat fallback.
        path_ext_pattern = r'(/home/|~/|\./|\.pdf\b|\.txt\b|\.docx\b|\.csv\b|\.json\b|\.sh\b|\.md\b)'
        tool_verb_pattern = r'\b(read|open|delete|write|launch|echo|screen|status|file|run|search|test|fix|show|close)\b'
        contextual_pronoun_pattern = r'\b(the file|that document|it|the pdf)\b'
        
        has_path_or_verb = bool(
            re.search(path_ext_pattern, user_text) or 
            re.search(tool_verb_pattern, user_text) or
            re.search(contextual_pronoun_pattern, user_text)
        )
            
        # 3. Chat Heuristics: Very short prompt (<15 words) and NO explicit tool keywords or paths
        word_count = len(user_text.split())
        if word_count < 15 and not has_path_or_verb:
            return "chat"
            
        # 4. Orchestration: Default fallback for general queries
        return "orchestration"

    def _route_request(self, messages: List[Dict[str, Any]], tool_schemas: Optional[List[Dict[str, Any]]] = None) -> str:
        """Determine which model to use, considering telemetry downgrades."""
        target_intent = self._classify_task(messages, tool_schemas)
        
        if target_intent == "code":
            # Check for OOM conditions before scheduling a Code task
            if self.telemetry and self.telemetry.latest_state.get("warning"):
                ram_avail = self.telemetry.latest_state.get("ram_available_percent", 0)
                
                config = get_config()
                if getattr(config, "allow_cloud_fallback", False) and self.cloud_adapter.is_configured:
                    print("\n[!] Local VRAM exhausted (<15%). Bursting Code task to Cloud Fallback...\n")
                    logger.warning(f"Local VRAM exhausted ({ram_avail:.1f}%). Bursting to Cloud Fallback.")
                    return "cloud"
                else:
                    logger.warning(
                        f"Emergency Downgrade: Code task requested, but RAM is critically low ({ram_avail:.1f}%). "
                        "Downgrading to Orchestration to prevent OOM crash."
                    )
                    target_intent = "orchestration"
                
                
        target_model_name = self.model_tiers.get(target_intent)
        
        # Verify the target model is actually installed
        capabilities = getattr(self.llm_client, "capabilities", {})
        installed_models = capabilities.get("models", [])
        
        # If installed_models is populated but our target isn't there, fall back to the main config model
        if installed_models and target_model_name not in installed_models and f"{target_model_name}:latest" not in installed_models:
            return getattr(getattr(self.llm_client, "config", None), "model", "default")
            
        selected_model = target_model_name or getattr(getattr(self.llm_client, "config", None), "model", "default")
        
        # Log mid-flight model swapping if it changes
        if self._current_active_model and self._current_active_model != selected_model:
            logger.info(f"Mid-Flight Context Router Swapping Model: {self._current_active_model} -> {selected_model} (Intent: {target_intent})")
        elif not self._current_active_model:
            logger.info(f"Context Router initializing with Model: {selected_model} (Intent: {target_intent})")
            
        self._current_active_model = selected_model
        return selected_model

    def chat(self, messages: List[Dict[str, Any]], **kwargs) -> str:
        """Route and execute a standard chat completion."""
        target_model = self._route_request(messages)
        
        if target_model == "cloud":
            return self.cloud_adapter.chat(messages, **kwargs)
            
        has_config = hasattr(self.llm_client, "config") and hasattr(self.llm_client.config, "model")
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
        
        if target_model == "cloud":
            return self.cloud_adapter.chat_with_tools(messages, tool_schemas, **kwargs)
            
        has_config = hasattr(self.llm_client, "config") and hasattr(self.llm_client.config, "model")
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
