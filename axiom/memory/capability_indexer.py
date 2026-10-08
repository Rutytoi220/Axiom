"""AXIOM Tool Capability Indexer.

Auto-indexes all registered tools into persistent MemoryStore under category 'capability',
keyed by 'tool.<tool_name>'. Automatically supersedes older entries when tool schemas
or descriptions change.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from axiom.db.memory import MemoryStore, get_db_path

logger = logging.getLogger(__name__)


def index_tool_capabilities(
    store: Optional[MemoryStore] = None,
    schemas: Optional[List[Dict[str, Any]]] = None,
) -> int:
    """Index registered tool capabilities into long-term MemoryStore.

    Each tool is indexed with:
      category = 'capability'
      key = 'tool.<name>'
      content = '<name>: <description>'

    If an active entry already exists with the same content, it is skipped.
    If the description or content has changed, storing with the key supersedes the old entry.

    Returns the number of indexed or updated tools.
    """
    mem_store = store or MemoryStore()

    if schemas is None:
        try:
            from axiom.core.plugins import get_tool_schemas
            schemas = get_tool_schemas()
        except Exception as e:
            logger.warning("Could not load tool schemas for capability indexing: %s", e)
            schemas = []

    indexed_count = 0
    for s in schemas:
        try:
            fn = s.get("function", {})
            name = fn.get("name")
            if not name:
                continue
            desc = fn.get("description", "").strip()
            key = f"tool.{name}"
            content = f"{name}: {desc}" if desc else f"{name}"

            # Check if active capability already exists with identical content
            active_record = mem_store.get_by_key(key)
            if active_record and active_record.get("content") == content:
                continue

            # Store new capability (superseding previous active entry if any)
            mem_store.store(
                content=content,
                category="capability",
                key=key,
                confidence=1.0,
            )
            indexed_count += 1
        except Exception as err:
            logger.warning("Failed to index capability for schema %s: %s", s, err)

    return indexed_count
