"""Research state — everything the orchestrator tracks per session."""

from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, Field

from kresearch.models.mind_map import MindMap
from kresearch.models.task_graph import TaskGraph


class ActionLog(BaseModel):
    """Record of a single tool invocation."""

    tool: str
    args: dict = Field(default_factory=dict)
    result_summary: str = ""
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class TokenUsage(BaseModel):
    """Cumulative token usage across the session."""

    input_tokens: int = 0
    output_tokens: int = 0

    def add(self, inp: int, out: int) -> None:
        self.input_tokens += inp
        self.output_tokens += out


class ResearchState(BaseModel):
    """Full mutable state for one research session."""

    query: str
    mind_map: MindMap
    task_graph: TaskGraph = Field(default_factory=TaskGraph)
    iteration: int = 0
    max_iterations: int = 20
    actions_log: list[ActionLog] = Field(default_factory=list)
    token_usage: TokenUsage = Field(default_factory=TokenUsage)
    subagent_results: list[str] = Field(default_factory=list)
    draft_requested: bool = False

    @classmethod
    def create(cls, query: str, max_iterations: int = 20) -> ResearchState:
        return cls(
            query=query,
            mind_map=MindMap.create(query),
            max_iterations=max_iterations,
        )

    def increment_iteration(self) -> int:
        self.iteration += 1
        return self.iteration

    def log_action(
        self, tool: str, args: dict, result_summary: str = ""
    ) -> None:
        self.actions_log.append(
            ActionLog(tool=tool, args=args, result_summary=result_summary)
        )

    def is_over_budget(self) -> bool:
        if self.max_iterations == 0:
            return False
        return self.iteration >= self.max_iterations
