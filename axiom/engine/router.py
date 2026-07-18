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
        
        # Configure the routing matrix (model names to map to tiers)
        # Default config; can be updated based on user hardware profiling in the future.
        self.model_tiers = {
            "tier1": "phi3:mini",        # Sub-3B parameter, very fast
            "tier2": "llama3:8b",        # 7-8B parameter, standard
            "tier3": "mixtral:8x7b"      # >30B parameter, complex
        }

    def _classify_task(self, messages: List[Dict[str, Any]], tool_schemas: Optional[List[Dict[str, Any]]] = None) -> str:
        """Classify the prompt complexity into a Tier."""
        if not messages:
            return "tier1"
            
        # Combine all user/system message contents for heuristic checking
        full_text = "\n".join([m.get("content", "") for m in messages if isinstance(m.get("content"), str)]).lower()
        
        # 1. Tier 3 Heuristics: Large context, complex keywords, architecture
        tier3_keywords = ["architecture", "refactor", "design pattern", "framework", "complex"]
        if len(full_text) > 4000 or any(kw in full_text for kw in tier3_keywords):
            return "tier3"
            
        # 2. Tier 1 Heuristics: Very short prompt, no tools, formatting tasks
        if len(messages) <= 2 and len(full_text) < 200 and not tool_schemas:
            return "tier1"
            
        # 3. Tier 2: Default for most standard agentic loops
        return "tier2"

    def _route_request(self, messages: List[Dict[str, Any]], tool_schemas: Optional[List[Dict[str, Any]]] = None) -> str:
        """Determine which model to use, considering telemetry downgrades."""
        target_tier = self._classify_task(messages, tool_schemas)
        
        if target_tier == "tier3":
            # Check for OOM conditions before scheduling a Tier 3 task
            if self.telemetry and self.telemetry.latest_state.get("warning"):
                ram_avail = self.telemetry.latest_state.get("ram_available_percent", 0)
                
                config = get_config()
                if getattr(config, "allow_cloud_fallback", False) and self.cloud_adapter.is_configured:
                    print("\n[!] Local VRAM exhausted (<15%). Bursting Tier 3 task to Cloud Fallback...\n")
                    logger.warning(f"Local VRAM exhausted ({ram_avail:.1f}%). Bursting to Cloud Fallback.")
                    return "cloud"
                else:
                    logger.warning(
                        f"Emergency Downgrade: Tier 3 task requested, but RAM is critically low ({ram_avail:.1f}%). "
                        "Downgrading to Tier 2 to prevent OOM crash."
                    )
                    target_tier = "tier2"
                
        return self.model_tiers.get(target_tier, getattr(getattr(self.llm_client, "config", None), "model", "default"))

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
