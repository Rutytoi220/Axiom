import re
from typing import List, Dict, Any

class ToolPruner:
    """Dynamically clusters and prunes tool schemas to optimize LLM context usage."""

    CLUSTER_MAPPINGS = {
        "filesystem": {
            "keywords": ["file", "document", "read", "write", "text", "search"],
            "tools": ["read_document_content", "file_read", "file_write", "file_search"]
        },
        "system_os": {
            "keywords": ["run", "command", "os", "app", "launch", "system"],
            "tools": ["execute_command", "system_info", "launch_app"]
        },
        "perception": {
            "keywords": ["screen", "see", "view", "controller", "game"],
            "tools": ["capture_screenshot", "nxbt_controller"]
        }
    }

    @staticmethod
    def prune_schemas(user_prompt: str, raw_schemas: List[Dict[str, Any]], intent: str) -> List[Dict[str, Any]]:
        """Filters schemas based on the intent and semantic clustering of the user prompt."""
        if intent == "chat":
            return []

        prompt_lower = user_prompt.lower()
        active_tools = set()
        matched_cluster = False

        for cluster, config in ToolPruner.CLUSTER_MAPPINGS.items():
            pattern = re.compile(r'\b(' + '|'.join(config["keywords"]) + r')\b')
            if pattern.search(prompt_lower):
                matched_cluster = True
                active_tools.update(config["tools"])

        if not matched_cluster:
            # Fallback: if no specific cluster matches, we return all schemas to be safe.
            return raw_schemas

        # Prune the raw schemas to only include those in the active_tools set
        pruned_schemas = [schema for schema in raw_schemas if schema.get("name") in active_tools]
        
        # If pruning somehow removed everything but we had a non-chat intent, fallback to raw_schemas
        if not pruned_schemas:
            return raw_schemas

        return pruned_schemas
