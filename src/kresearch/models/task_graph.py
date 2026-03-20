"""Task graph for tracking research sub-tasks."""

from __future__ import annotations

import uuid
from enum import Enum

from pydantic import BaseModel, Field


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class TaskNode(BaseModel):
    """A single research sub-task with a query, status, and results."""

    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:8])
    query: str
    status: TaskStatus = TaskStatus.PENDING
    results: str = ""


class TaskGraph(BaseModel):
    """Tracks sub-tasks spawned during a research session.

    Used by the orchestrator to manage parallel sub-agent work.
    Tasks progress through: PENDING -> RUNNING -> COMPLETED/FAILED.
    """

    tasks: list[TaskNode] = Field(default_factory=list)

    def add_task(self, query: str) -> TaskNode:
        """Create a new pending task and return it."""
        task = TaskNode(query=query)
        self.tasks.append(task)
        return task

    def complete_task(self, task_id: str, results: str) -> None:
        """Mark a task as completed with its results. No-op if ID not found."""
        for t in self.tasks:
            if t.id == task_id:
                t.status = TaskStatus.COMPLETED
                t.results = results
                return

    def fail_task(self, task_id: str, error: str) -> None:
        """Mark a task as failed with an error message. No-op if ID not found."""
        for t in self.tasks:
            if t.id == task_id:
                t.status = TaskStatus.FAILED
                t.results = error
                return

    def get_pending(self) -> list[TaskNode]:
        """Return all tasks that have not yet started."""
        return [t for t in self.tasks if t.status == TaskStatus.PENDING]

    def get_running(self) -> list[TaskNode]:
        """Return all tasks currently in progress."""
        return [t for t in self.tasks if t.status == TaskStatus.RUNNING]
