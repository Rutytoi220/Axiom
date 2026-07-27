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
        """Filters schemas based on the intent."""
        if intent == "chat":
            return []
            
        # Return all schemas directly, shifting full reasoning burden to the LLM
        return raw_schemas
