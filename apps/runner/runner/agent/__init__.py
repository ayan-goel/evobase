"""LLM agent layer for autonomous codebase optimization.

Public API:
    run_agent_cycle() — full discovery + patch + validation cycle
    AgentCycleResult, AgentOpportunity, AgentPatch, AgentRun
"""

from runner.agent.orchestrator import AgentCycleResult, run_agent_cycle
from runner.agent.types import AgentOpportunity, AgentPatch, AgentRun

__all__ = [
    "run_agent_cycle",
    "AgentCycleResult",
    "AgentOpportunity",
    "AgentPatch",
    "AgentRun",
]
