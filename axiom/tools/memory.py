"""AXIOM Memory Tools — Autonomous Fact Retention."""

from typing import Any, Dict
from axiom.tools.core import BaseTool, ToolResult
from axiom.memory.semantic import add_memory


class RememberFactTool(BaseTool):
    """Tool allowing the model to autonomously store important user preferences,
    system configurations, and persistent project details into semantic memory.
    """

    def __init__(self):
        super().__init__()
        self._name = "remember_fact"
        self._description = (
            "Store an important fact, user preference, system configuration, or persistent project detail "
            "into long-term semantic memory."
        )

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return self._description

    @property
    def schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "fact": {
                    "type": "string",
                    "description": "The concise, permanent fact, user preference, or project rule to store."
                }
            },
            "required": ["fact"]
        }

    async def execute(self, params: Dict[str, Any]) -> ToolResult:
        fact = params.get("fact", "").strip()
        if not fact:
            return ToolResult(success=False, error="Parameter 'fact' cannot be empty.")

        try:
            mem_id = add_memory(fact)
            return ToolResult(
                success=True,
                output={
                    "message": f"Successfully stored memory #{mem_id}: {fact}",
                    "memory_id": mem_id,
                    "fact": fact,
                }
            )
        except Exception as e:
            return ToolResult(success=False, error=f"Failed to store memory: {e}")
