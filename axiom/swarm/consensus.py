"""Multi-Agent Consensus Engine for high-risk operations."""

import json
import logging
import asyncio
from typing import List, Dict, Any

from axiom.swarm.blackboard import Blackboard, Proposal, Critique
from axiom.llm.ollama_client import OllamaClient, OllamaConfig

logger = logging.getLogger(__name__)

class ConsensusEngine:
    """Coordinates a debate among local LLMs to approve or reject high-risk tool execution."""
    
    def __init__(self, event_bus):
        self.bus = event_bus
        self.blackboard = Blackboard()
        
        # Instantiate clients for specific roles
        self.proposer_llm = OllamaClient(OllamaConfig(model="qwen3-coder:latest"))
        self.critic_llm = OllamaClient(OllamaConfig(model="llama3.1:latest"))

    async def run_debate(self, task: str, context: str, pending_tools: List[Dict[str, Any]]) -> bool:
        """Run the debate protocol. Returns True if consensus reached, False otherwise."""
        
        # Publish start event
        if self.bus and hasattr(self.bus, "publish_sync"):
            self.bus.publish_sync("swarm.debate.started", {
                "task": task,
                "tool_count": len(pending_tools)
            })
            
        # Clear previous state
        await self.blackboard.clear()
        
        max_revisions = 1
        current_revision = 0
        consensus_reached = False
        
        # The tool payload to review
        tools_json = json.dumps(pending_tools, indent=2, default=str)
        
        # Base Proposal Phase
        proposal = await self._generate_proposal(task, context, tools_json)
        await self.blackboard.post_proposal(proposal)
        
        if self.bus and hasattr(self.bus, "publish_sync"):
            self.bus.publish_sync("swarm.proposal.submitted", {
                "author": proposal.author,
                "proposal_id": proposal.id
            })

        while current_revision <= max_revisions and not consensus_reached:
            # Critique Phase
            critique = await self._generate_critique(task, proposal, tools_json)
            await self.blackboard.post_critique(critique)
            
            if critique.consensus_reached:
                consensus_reached = True
                break
                
            current_revision += 1
            if current_revision <= max_revisions:
                # Synthesis / Revision Phase
                proposal = await self._generate_revision(task, proposal, critique, tools_json)
                await self.blackboard.post_proposal(proposal)
                if self.bus and hasattr(self.bus, "publish_sync"):
                    self.bus.publish_sync("swarm.proposal.submitted", {
                        "author": proposal.author,
                        "proposal_id": proposal.id,
                        "revision": current_revision
                    })

        # Final outcome
        if self.bus and hasattr(self.bus, "publish_sync"):
            self.bus.publish_sync("swarm.consensus.reached" if consensus_reached else "swarm.consensus.failed", {
                "consensus": consensus_reached,
                "revisions": current_revision
            })
            
        return consensus_reached

    async def _generate_proposal(self, task: str, context: str, tools_json: str) -> Proposal:
        """Ask the Proposer model to explain and justify the tool calls."""
        prompt = (
            f"Task: {task}\n"
            f"Context: {context}\n"
            f"Proposed Tool Calls:\n{tools_json}\n\n"
            "As the Proposer, write a clear Implementation Plan that explains what these tools will do "
            "and why they are safe and correct. Be concise."
        )
        response = self.proposer_llm.chat([{"role": "user", "content": prompt}])
        return Proposal(
            author="qwen3-coder:latest",
            content=response,
            tool_calls=json.loads(tools_json)
        )
        
    async def _generate_critique(self, task: str, proposal: Proposal, tools_json: str) -> Critique:
        """Ask the Critic model to scrutinize the proposal and tools."""
        prompt = (
            f"Task: {task}\n"
            f"Implementation Plan: {proposal.content}\n"
            f"Tool Calls:\n{tools_json}\n\n"
            "As the Critic, review this plan for edge cases, bugs, or security flaws. "
            "If it is completely safe and correct, output exactly 'CONSENSUS_REACHED'. "
            "Otherwise, list the issues."
        )
        response = self.critic_llm.chat([{"role": "user", "content": prompt}])
        
        is_consensus = "CONSENSUS_REACHED" in response.upper()
        flags = []
        if not is_consensus:
            flags.append("Critic raised concerns.")
            
        return Critique(
            target_proposal_id=proposal.id,
            author="llama3.1:latest",
            content=response,
            flags=flags,
            consensus_reached=is_consensus
        )
        
    async def _generate_revision(self, task: str, old_proposal: Proposal, critique: Critique, tools_json: str) -> Proposal:
        """Ask the Proposer to revise based on critique."""
        prompt = (
            f"Task: {task}\n"
            f"Previous Plan: {old_proposal.content}\n"
            f"Critic's Feedback: {critique.content}\n"
            f"Tool Calls:\n{tools_json}\n\n"
            "As the Proposer, revise your Implementation Plan to address the Critic's feedback."
        )
        response = self.proposer_llm.chat([{"role": "user", "content": prompt}])
        return Proposal(
            author="qwen3-coder:latest",
            content=response,
            tool_calls=json.loads(tools_json)
        )
