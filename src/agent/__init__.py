"""The agent "brain": the OBSERVE -> ... -> NEXT loop, typed tools, and
structured + failure memory (constraint-cage.md Part 7).

This package depends only on the structural Protocols in
``src.agent.interfaces`` -- never on a concrete LLM backend or transport --
so it is fully importable and unit-testable with zero model weights and no
VM running. Concrete implementations (the llama-server HTTP client, the
SSH/vsock action channel) live in ``src.orchestrator``.
"""

from src.agent.loop import AgentLoop, LoopConfig
from src.agent.memory import StructuredMemory
from src.agent.models import (
    AgentState,
    AgentStepOutput,
    EpisodeOutcome,
    EpisodeResult,
    Evaluation,
    Fact,
    FailureRecord,
    Goal,
    StepRecord,
    ToolCall,
    ToolResult,
)
from src.agent.tools import ToolRegistry

__all__ = [
    "AgentLoop",
    "LoopConfig",
    "StructuredMemory",
    "AgentState",
    "AgentStepOutput",
    "EpisodeOutcome",
    "EpisodeResult",
    "Evaluation",
    "Fact",
    "FailureRecord",
    "Goal",
    "StepRecord",
    "ToolCall",
    "ToolResult",
    "ToolRegistry",
]
