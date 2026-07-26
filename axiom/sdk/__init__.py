"""AXIOM SDK - Official Python Client Library.

Provides asynchronous and synchronous clients, as well as strict
Pydantic v2 data models for interacting with the AXIOM JSON-RPC daemon.
"""

from axiom.sdk.client import AxiomClient, SyncAxiomClient  # pragma: no cover
from axiom.sdk.models import (  # pragma: no cover
    JsonRpcRequest,
    JsonRpcResponse,
    JsonRpcError,
    PromptRequest,
    TelemetryPayload,
    SwarmProposal,
    SwarmVote,
)

__all__ = [  # pragma: no cover
    "AxiomClient",
    "SyncAxiomClient",
    "JsonRpcRequest",
    "JsonRpcResponse",
    "JsonRpcError",
    "PromptRequest",
    "TelemetryPayload",
    "SwarmProposal",
    "SwarmVote",
]
