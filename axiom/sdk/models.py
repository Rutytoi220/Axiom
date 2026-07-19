"""Typed Data Models for the AXIOM SDK.

Provides strict Pydantic v2 schemas for JSON-RPC payloads and core
AXIOM domain entities (prompts, telemetry, swarm events).
"""

from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field


class JsonRpcRequest(BaseModel):
    """A standard JSON-RPC 2.0 Request."""
    jsonrpc: str = "2.0"
    method: str
    params: Optional[Dict[str, Any]] = None
    id: Optional[Union[str, int]] = None


class JsonRpcError(BaseModel):
    """A JSON-RPC 2.0 Error object."""
    code: int
    message: str
    data: Optional[Any] = None


class JsonRpcResponse(BaseModel):
    """A standard JSON-RPC 2.0 Response."""
    jsonrpc: str = "2.0"
    result: Optional[Any] = None
    error: Optional[JsonRpcError] = None
    id: Optional[Union[str, int]] = None


class PromptRequest(BaseModel):
    """Payload for submitting a prompt to AXIOM."""
    text: str
    session_id: Optional[str] = None


class TelemetryPayload(BaseModel):
    """Telemetry payload emitted by AXIOM daemon."""
    ram_percent: float
    vram_percent: float
    tier: str


class SwarmProposal(BaseModel):
    """A proposal emitted by a sub-agent within the swarm."""
    proposal_id: str
    tool: str
    agent: str
    status: str = "PROPOSED"


class SwarmVote(BaseModel):
    """A vote cast by a sub-agent regarding a proposal."""
    proposal_id: str
    vote: str
    voter: str
