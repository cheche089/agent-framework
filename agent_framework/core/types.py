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
