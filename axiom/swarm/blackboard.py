"""Swarm Blackboard Memory for multi-agent coordination."""

import uuid
import time
import asyncio
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any

@dataclass
class Proposal:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    author: str = ""
    content: str = ""
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)
    status: str = "PENDING"
    timestamp: float = field(default_factory=time.time)

@dataclass
class Critique:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    target_proposal_id: str = ""
    author: str = ""
    content: str = ""
    flags: List[str] = field(default_factory=list)
    consensus_reached: bool = False
    timestamp: float = field(default_factory=time.time)

@dataclass
class Vote:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    target_proposal_id: str = ""
    author: str = ""
    decision: bool = False
    timestamp: float = field(default_factory=time.time)

class Blackboard:
    """Async shared state structure for swarm subagents."""
    
    def __init__(self):
        self.proposals: Dict[str, Proposal] = {}
        self.critiques: Dict[str, List[Critique]] = {}
        self.votes: Dict[str, List[Vote]] = {}
        self._lock = asyncio.Lock()

    async def post_proposal(self, proposal: Proposal) -> None:
        async with self._lock:
            self.proposals[proposal.id] = proposal
            self.critiques[proposal.id] = []
            self.votes[proposal.id] = []

    async def post_critique(self, critique: Critique) -> None:
        async with self._lock:
            if critique.target_proposal_id in self.critiques:
                self.critiques[critique.target_proposal_id].append(critique)

    async def post_vote(self, vote: Vote) -> None:
        async with self._lock:
            if vote.target_proposal_id in self.votes:
                self.votes[vote.target_proposal_id].append(vote)

    async def get_proposal(self, proposal_id: str) -> Optional[Proposal]:
        async with self._lock:
            return self.proposals.get(proposal_id)

    async def get_critiques(self, proposal_id: str) -> List[Critique]:
        async with self._lock:
            return self.critiques.get(proposal_id, [])

    async def get_votes(self, proposal_id: str) -> List[Vote]:
        async with self._lock:
            return self.votes.get(proposal_id, [])

    async def clear(self) -> None:
        async with self._lock:
            self.proposals.clear()
            self.critiques.clear()
            self.votes.clear()
