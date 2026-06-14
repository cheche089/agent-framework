from __future__ import annotations
import dataclasses
import enum
from typing import Any, Dict, List, Optional


class MessageRole(str, enum.Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


@dataclasses.dataclass
class Message:
    role: MessageRole
    content: str
    metadata: Dict[str, Any] = dataclasses.field(default_factory=dict)
    name: Optional[str] = None


@dataclasses.dataclass
class ToolSpec:
    name: str
    description: str
    parameters: Dict[str, Any]


@dataclasses.dataclass
class ToolResult:
    success: bool
    output: str = ""
    error: Optional[str] = None
    metadata: Dict[str, Any] = dataclasses.field(default_factory=dict)

    @classmethod
    def ok(cls, output: str = "", **metadata) -> "ToolResult":
        return cls(success=True, output=output, metadata=metadata)

    @classmethod
    def fail(cls, error: str, **metadata) -> "ToolResult":
        return cls(success=False, error=error, metadata=metadata)


class StepStatus(str, enum.Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclasses.dataclass
class PlanStep:
    id: str
    action: str
    expected_outcome: str
    depends_on: List[str] = dataclasses.field(default_factory=list)
    status: StepStatus = StepStatus.PENDING
    result: Optional[str] = None
    metadata: Dict[str, Any] = dataclasses.field(default_factory=dict)


@dataclasses.dataclass
class Plan:
    goal: str
    steps: List[PlanStep]
    status: StepStatus = StepStatus.PENDING
    metadata: Dict[str, Any] = dataclasses.field(default_factory=dict)

    @property
    def completed(self) -> bool:
        return all(s.status == StepStatus.COMPLETED for s in self.steps)


@dataclasses.dataclass
class MemoryItem:
    key: str
    value: Any
    metadata: Dict[str, Any] = dataclasses.field(default_factory=dict)
    timestamp: Optional[float] = None


@dataclasses.dataclass
class ContextLimit:
    max_tokens: int = 128000
    strategy: str = "sliding_window"
    reserved_tokens: int = 4000


class NodeType(str, enum.Enum):
    ACTION = "action"
    CONDITION = "condition"
    LOOP = "loop"
    PARALLEL = "parallel"
    SEQUENCE = "sequence"


@dataclasses.dataclass
class WorkflowNode:
    id: str
    type: NodeType
    config: Dict[str, Any] = dataclasses.field(default_factory=dict)
    children: List["WorkflowNode"] = dataclasses.field(default_factory=list)
    next_on_success: Optional[str] = None
    next_on_failure: Optional[str] = None


@dataclasses.dataclass
class SkillSpec:
    name: str
    description: str
    instructions: str
    required_tools: List[str] = dataclasses.field(default_factory=list)
    metadata: Dict[str, Any] = dataclasses.field(default_factory=dict)


class SandboxMode(str, enum.Enum):
    RESTRICTED = "restricted"
    ISOLATED = "isolated"
    PERMISSIVE = "permissive"


@dataclasses.dataclass
class SandboxResult:
    success: bool
    stdout: str = ""
    stderr: str = ""
    exit_code: int = 0
    error: Optional[str] = None
    duration_ms: float = 0.0


@dataclasses.dataclass
class ExecutionContext:
    messages: List[Message] = dataclasses.field(default_factory=list)
    metadata: Dict[str, Any] = dataclasses.field(default_factory=dict)
    config: Optional["AgentConfig"] = None


# ==============================================
# Agent Loop 增强类型 (v2.0)
# ==============================================

class TaskStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    NEEDS_HUMAN = "needs_human"

class LoopDecision(str, enum.Enum):
    CONTINUE = "continue"
    REPLAN = "replan"
    NEEDS_HUMAN = "needs_human"
    ABORT = "abort"
    COMPLETE = "complete"

@dataclasses.dataclass
class AgentThought:
    step_id: str
    thought: str
    timestamp: float = 0.0

@dataclasses.dataclass
class AgentAction:
    tool_name: str
    params: dict = dataclasses.field(default_factory=dict)
    description: str = ""
    timestamp: float = 0.0

@dataclasses.dataclass
class AgentObservation:
    step_id: str
    result: 'ToolResult'
    timestamp: float = 0.0

    @property
    def summary(self) -> str:
        return self.result.output[:200] if self.result.success else (self.result.error or "unknown error")

@dataclasses.dataclass
class AgentLoopStep:
    step_id: str
    thought: 'AgentThought | None' = None
    action: 'AgentAction | None' = None
    observation: 'AgentObservation | None' = None
    plan_step: 'PlanStep | None' = None
    decision: LoopDecision = LoopDecision.CONTINUE
    retry_count: int = 0
    max_retries: int = 3
    duration_ms: float = 0.0

@dataclasses.dataclass
class LoopState:
    task_id: str
    goal: str
    steps: list['AgentLoopStep']
    current_index: int = 0
    plan: 'Plan | None' = None
    status: TaskStatus = TaskStatus.PENDING
    replan_count: int = 0
    max_replans: int = 5
    final_answer: str | None = None
    metadata: dict = dataclasses.field(default_factory=dict)

    def current_step(self) -> 'AgentLoopStep | None':
        if 0 <= self.current_index < len(self.steps):
            return self.steps[self.current_index]
        return None

    def completed(self) -> bool:
        return self.status in (TaskStatus.COMPLETED, TaskStatus.FAILED)

@dataclasses.dataclass
class StepProgress:
    step_id: str
    description: str
    status: StepStatus
    thought: str | None = None
    action: str | None = None
    observation: str | None = None
    duration_ms: float = 0.0

    def icon(self) -> str:
        mapping = {
            StepStatus.PENDING: "...",
            StepStatus.IN_PROGRESS: "->",
            StepStatus.COMPLETED: "OK",
            StepStatus.FAILED: "XX",
            StepStatus.SKIPPED: "--",
        }
        return mapping.get(self.status, "??")

    def to_display_line(self) -> str:
        icon = self.icon()
        parts = [f"  {icon} {self.step_id}: {self.description}"]
        if self.thought:
            parts.append(f"      Thought: {self.thought[:120]}")
        if self.action:
            parts.append(f"      Action: {self.action[:120]}")
        if self.observation:
            parts.append(f"      Observation: {self.observation[:120]}")
        return chr(10).join(parts)

@dataclasses.dataclass
class TaskProgress:
    task_id: str
    goal: str
    steps: list['StepProgress']
    current_step_index: int = 0
    status: TaskStatus = TaskStatus.PENDING
    metadata: dict = dataclasses.field(default_factory=dict)

    def to_display(self) -> str:
        status_icon = {
            TaskStatus.PENDING: "[...]",
            TaskStatus.RUNNING: "[->]",
            TaskStatus.COMPLETED: "[OK]",
            TaskStatus.FAILED: "[XX]",
            TaskStatus.NEEDS_HUMAN: "[??]",
        }.get(self.status, "[??]")

        completed = sum(1 for s in self.steps if s.status == StepStatus.COMPLETED)
        total = len(self.steps)

        lines = [
            f"Task: {self.goal}  {status_icon}",
            f"  Progress: {completed}/{total} steps completed",
        ]
        for i, step in enumerate(self.steps):
            prefix = chr(9500) if i < total - 1 else chr(9492)
            lines.append(f"{prefix}{chr(9472)} {step.icon()} {step.step_id}: {step.description}")
        return chr(10).join(lines)
