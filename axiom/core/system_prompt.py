"""AXIOM Core — System Prompt Templates.

Centralises every system-prompt template so the orchestrator (and any future
agents) can import a single function rather than embedding raw strings inline.

Exported helpers
----------------
SOM_REACT_SYSTEM_PROMPT
    The verbatim ReAct XML state-machine prompt for vision + SoM tasks.
    Formatted with few-shot examples and an explicit "NEVER GUESS" rule so
    that even a 1.5B model follows a rigid THOUGHT → ACTION rail.

build_som_override(tool_names)
    Returns the SoM override string with the tool list injected dynamically
    from the live registry — keeps the prompt accurate even if tool IDs change.

extract_xml_tool_call(text)
    Regex extractor for <tool_call>…</tool_call> blobs emitted by models
    running under the ReAct prompt.  Returns a parsed dict or None.
    Used by the orchestrator's fallback parsing chain.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ── Verbatim ReAct prompt ─────────────────────────────────────────────────────
# The exact wording is intentional:
#   • ALL CAPS directives ("YOU MUST NEVER GUESS") work better with small models
#     than polite hedges.
#   • Few-shot examples are the single most effective technique for getting 2B
#     models to follow a format — they never deviate from a shown pattern.
#   • One tool per response prevents parallel hallucinations where the model
#     invents the result of tool A before seeing it.
#   • <thought> forces scratchpad tokens before the JSON, dramatically reducing
#     premature / incomplete JSON emission on small models.

SOM_REACT_SYSTEM_PROMPT: str = """\
You are AXIOM, a local-first, sovereign AI desktop assistant.
You have access to tools that allow you to see and physically control the user's computer.

### YOUR CAPABILITIES:
1. You cannot see the screen by default. You MUST use the `capture_som_screen` tool to take a picture.
2. The screen capture returns an annotated image with 2-letter tags (AA, AB, AC …) drawn directly on every clickable UI element.
3. You can click any tagged element using the `click_tag` tool.
4. YOU MUST NEVER GUESS A TAG. If you have not captured the screen yet, or if the tag you want is not visible in the image, you MUST call `capture_som_screen` first.

### THE RULES OF EXECUTION:
- You must follow a strict THOUGHT → ACTION loop.
- You may execute ONLY ONE tool per response.
- You MUST wrap your internal reasoning inside <thought> tags before every action.
- You MUST wrap your tool call inside <tool_call> tags as raw JSON with keys "name" and "arguments".
- Do NOT output any text after the closing </tool_call> tag.
- Do NOT emit a <tool_call> without a preceding <thought>.

### AVAILABLE TOOLS:
- {"name": "capture_som_screen", "arguments": {}}
- {"name": "click_tag", "arguments": {"tag": "<2-letter tag>", "button": "left|right", "clicks": 1}}

### STRICT EXAMPLES (reproduce this exact format — no deviations):

─── Example 1: First interaction ───────────────────────────────────────────────
User: Open the Settings application.

<thought>
The user wants to open Settings. I have not captured the screen yet, so I do not know which tag corresponds to the Settings button. I must call capture_som_screen first.
</thought>
<tool_call>
{"name": "capture_som_screen", "arguments": {}}
</tool_call>

─── Example 2: Acting on a captured screen ──────────────────────────────────────
[System Observation]: Screen captured. 14 elements tagged. Tags visible: AA, AB, AC, AD, AE, AF, AG, AH, AI, AJ, AK, AL, AM, AN.
[Image]: <annotated screenshot — Settings icon has tag "AF">

<thought>
I can see the screen. The Settings icon has the tag "AF". I will click it now.
</thought>
<tool_call>
{"name": "click_tag", "arguments": {"tag": "AF"}}
</tool_call>

─── Example 3: Tag not visible ───────────────────────────────────────────────────
[System Observation]: Clicked "AF". New screen loaded.

<thought>
The screen has changed after clicking. The previous tags are now stale. I need to capture the screen again to find the new tags for the next step.
</thought>
<tool_call>
{"name": "capture_som_screen", "arguments": {}}
</tool_call>

### BEGIN:
"""  # noqa: E501


def build_som_override(available_tool_names: Optional[List[str]] = None) -> str:
    """Return the SoM ReAct override prompt, optionally listing live tool names.

    This is injected as an ``override_prompt`` system message in
    ``_build_messages`` when a vision/desktop intent is detected.  It sits
    *on top of* the existing base prompt so the persona and file-path rules
    remain intact.

    Parameters
    ----------
    available_tool_names:
        If provided, tool names are validated against the live registry and an
        extra line is appended listing only the tools actually available.
    """
    prompt = SOM_REACT_SYSTEM_PROMPT
    if available_tool_names:
        som_tools = [
            t for t in available_tool_names
            if t in ("capture_som_screen", "click_tag")
        ]
        if som_tools:
            prompt += (
                f"\n[Active SoM Tools in Registry]: {', '.join(som_tools)}\n"
            )
        else:
            prompt += (
                "\n[Warning]: capture_som_screen / click_tag are not currently "
                "registered. Ensure axiom/tools/som_tools.py is loaded.\n"
            )
    return prompt


# ── XML tool-call extractor ───────────────────────────────────────────────────

# Compiled once at import time — called on every THINK iteration.
_XML_TOOL_CALL_RE = re.compile(
    r"<tool_call>\s*(.*?)\s*</tool_call>",
    re.DOTALL | re.IGNORECASE,
)

# Models sometimes emit a closing tag variant without the slash.
_XML_TOOL_CALL_OPEN_RE = re.compile(
    r"<tool_call>\s*(.*?)(?:</tool_call>|<tool_call>|$)",
    re.DOTALL | re.IGNORECASE,
)


def extract_xml_tool_call(text: str) -> Optional[Dict[str, Any]]:
    """Extract and parse a <tool_call>…</tool_call> block from model output.

    This is the primary extraction path for models running under
    SOM_REACT_SYSTEM_PROMPT.  It is called *before* the legacy regex chain
    in the orchestrator's fallback parser so that well-formed XML blocks are
    handled with zero ambiguity.

    Returns
    -------
    dict | None
        A dict in the orchestrator's internal tool-call format::

            {"function": {"name": "<tool>", "arguments": {…}}}

        or None if no valid <tool_call> block is found.

    Design notes
    ------------
    - Extracts the raw JSON between the XML tags.
    - Strips markdown fences (```json … ```) that models sometimes wrap around
      the JSON even when instructed not to.
    - Falls back to searching for any ``{…}`` blob inside the tag if strict
      JSON parsing fails — catches models that emit trailing comments.
    - Logs every parse failure at DEBUG level so we can tune prompts.
    """
    if not text or "<tool_call>" not in text.lower():
        return None

    # ── 1. Extract content between tags ──────────────────────────────────────
    match = _XML_TOOL_CALL_RE.search(text)
    if not match:
        # Try the open-ended pattern (model forgot closing tag).
        match = _XML_TOOL_CALL_OPEN_RE.search(text)
    if not match:
        logger.debug("extract_xml_tool_call: <tool_call> present but no parseable content.")
        return None

    raw = match.group(1).strip()

    # ── 2. Strip optional markdown fence ─────────────────────────────────────
    fence_match = re.search(r"```(?:json)?\s*(.*?)```", raw, re.DOTALL | re.IGNORECASE)
    if fence_match:
        raw = fence_match.group(1).strip()

    # ── 3. Parse JSON ─────────────────────────────────────────────────────────
    parsed: Optional[Dict[str, Any]] = None
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        # Small models sometimes emit trailing prose after the JSON object.
        # Find the outermost complete { … } and try again.
        blob_match = re.search(r"\{.*\}", raw, re.DOTALL)
        if blob_match:
            try:
                parsed = json.loads(blob_match.group(0))
            except json.JSONDecodeError as exc:
                logger.debug("extract_xml_tool_call: JSON parse failed: %s | raw=%r", exc, raw[:200])
                return None
        else:
            logger.debug("extract_xml_tool_call: no JSON object found in <tool_call> block.")
            return None

    if not isinstance(parsed, dict):
        logger.debug("extract_xml_tool_call: parsed value is not a dict: %r", parsed)
        return None

    # ── 4. Normalise to orchestrator internal format ──────────────────────────
    # The prompt instructs: {"name": "tool_name", "arguments": {…}}
    # The orchestrator's _normalize_tool_call() expects:
    #   {"function": {"name": "…", "arguments": {…}}}
    tool_name = parsed.get("name") or parsed.get("tool") or parsed.get("function")
    arguments = parsed.get("arguments") or parsed.get("args") or parsed.get("params") or {}

    if not tool_name:
        logger.debug("extract_xml_tool_call: parsed dict has no 'name' key: %r", parsed)
        return None

    if not isinstance(arguments, dict):
        # Model emitted arguments as a string — wrap it.
        arguments = {"input": arguments}

    logger.info(
        "extract_xml_tool_call: extracted tool='%s' args=%s", tool_name, arguments
    )
    return {"function": {"name": str(tool_name), "arguments": arguments}}
