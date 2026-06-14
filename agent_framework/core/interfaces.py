from __future__ import annotations
import abc
from typing import Any, Dict, List, Optional, Tuple
from .types import (
    ExecutionContext, MemoryItem, Plan, PlanStep,
    SandboxResult, SkillSpec, ToolResult, ToolSpec, WorkflowNode,
    SandboxMode,
)


class BaseTool(abc.ABC):
    """工具基类。子类需设置 name/description/parameters 并实现 execute。"""
    name: str = ""
    description: str = ""
    parameters: Dict[str, Any] = {}

    @abc.abstractmethod
    async def execute(self, ctx: ExecutionContext, **kwargs: Any) -> ToolResult:
        ...

    def to_spec(self) -> ToolSpec:
        return ToolSpec(name=self.name, description=self.description, parameters=self.parameters)


class ToolRegistry(abc.ABC):
    @abc.abstractmethod
    def register(self, tool: BaseTool) -> None: ...
    @abc.abstractmethod
    def unregister(self, name: str) -> None: ...
    @abc.abstractmethod
    def get(self, name: str) -> Optional[BaseTool]: ...
    @abc.abstractmethod
    def list_specs(self) -> List[ToolSpec]: ...
    @abc.abstractmethod
    async def execute(self, name: str, ctx: ExecutionContext, **kwargs: Any) -> ToolResult: ...


class PlanningStrategy(abc.ABC):
    @abc.abstractmethod
    async def decompose(self, goal: str, tools: List[ToolSpec], context: ExecutionContext) -> List[PlanStep]: ...


class PlannerEngine(abc.ABC):
    @abc.abstractmethod
    async def plan(self, goal: str, tools: List[ToolSpec], context: ExecutionContext) -> Plan: ...
    @abc.abstractmethod
    async def replan(self, plan: Plan, feedback: str, tools: List[ToolSpec], context: ExecutionContext) -> Plan: ...


class MemoryBackend(abc.ABC):
    @abc.abstractmethod
    async def store(self, item: MemoryItem) -> None: ...
    @abc.abstractmethod
    async def retrieve(self, query: str, limit: int = 10, filters: Optional[Dict[str, Any]] = None) -> List[MemoryItem]: ...
    @abc.abstractmethod
    async def forget(self, key: str) -> bool: ...
    @abc.abstractmethod
    async def clear(self) -> None: ...


class MemoryStore(abc.ABC):
    @abc.abstractmethod
    async def remember(self, key: str, value: Any, metadata: Optional[Dict[str, Any]] = None) -> None: ...
    @abc.abstractmethod
    async def recall(self, query: str, limit: int = 10) -> List[MemoryItem]: ...
    @abc.abstractmethod
    async def forget(self, key: str) -> bool: ...
    @abc.abstractmethod
    async def summarize(self) -> str: ...


class TokenCounter(abc.ABC):
    @abc.abstractmethod
    def count(self, text: str) -> int: ...


class ContextManager(abc.ABC):
    @abc.abstractmethod
    async def add_message(self, message: "Message") -> None: ...
    @abc.abstractmethod
    async def build_prompt(self) -> List["Message"]: ...
    @abc.abstractmethod
    async def compress(self) -> None: ...
    @abc.abstractmethod
    def token_count(self) -> int: ...


class WorkflowEngine(abc.ABC):
    @abc.abstractmethod
    async def execute(self, workflow: WorkflowNode, context: ExecutionContext) -> Dict[str, Any]: ...
    @abc.abstractmethod
    async def step(self, node: WorkflowNode, context: ExecutionContext) -> Any: ...


class SkillLoader(abc.ABC):
    @abc.abstractmethod
    async def load(self, source: str) -> SkillSpec: ...


class SkillManager(abc.ABC):
    @abc.abstractmethod
    async def load_skill(self, source: str) -> SkillSpec: ...
    @abc.abstractmethod
    async def execute_skill(self, name: str, params: Dict[str, Any], context: ExecutionContext) -> str: ...
    @abc.abstractmethod
    def list_skills(self) -> List[SkillSpec]: ...
    @abc.abstractmethod
    async def unload_skill(self, name: str) -> bool: ...


class PolicyRule(abc.ABC):
    @abc.abstractmethod
    async def check(self, action: str, target: str, context: ExecutionContext) -> Tuple[bool, str]: ...


class Sandbox(abc.ABC):
    @abc.abstractmethod
    async def execute_command(self, command: str, timeout: int = 30) -> SandboxResult: ...
    @abc.abstractmethod
    async def read_file(self, path: str) -> str: ...
    @abc.abstractmethod
    async def write_file(self, path: str, content: str) -> None: ...
    @abc.abstractmethod
    async def set_mode(self, mode: SandboxMode) -> None: ...


# ==============================================
# Agent Loop 接口 (v2.0)
# ==============================================

class LoopEngine(abc.ABC):
    @abc.abstractmethod
    async def think(self, step_id: str, goal: str, context: ExecutionContext, tools: list['ToolSpec']) -> 'AgentThought': ...
    @abc.abstractmethod
    async def decide_action(self, thought: 'AgentThought', context: ExecutionContext, tools: list['ToolSpec']) -> 'AgentAction': ...
    @abc.abstractmethod
    async def observe(self, action: 'AgentAction', result: 'ToolResult', context: ExecutionContext) -> 'AgentObservation': ...
    @abc.abstractmethod
    async def evaluate_step(self, loop_step: 'AgentLoopStep', context: ExecutionContext) -> 'LoopDecision': ...
    @abc.abstractmethod
    async def should_replan(self, state: 'LoopState', context: ExecutionContext) -> bool: ...
    @abc.abstractmethod
    async def format_final_answer(self, state: 'LoopState', context: ExecutionContext) -> str: ...


class HarnessEngine(abc.ABC):
    @abc.abstractmethod
    async def pre_tool_check(self, action: 'AgentAction', context: ExecutionContext) -> tuple[bool, str]: ...
    @abc.abstractmethod
    async def post_tool_check(self, action: 'AgentAction', result: 'ToolResult', context: ExecutionContext) -> tuple[bool, str]: ...
    @abc.abstractmethod
    async def log_feedback(self, step: 'AgentLoopStep', context: ExecutionContext) -> None: ...
    @abc.abstractmethod
    async def human_intervention_needed(self, reason: str, context: ExecutionContext) -> None: ...
    @abc.abstractmethod
    def get_metrics(self) -> dict: ...


class ProgressFormatter(abc.ABC):
    @abc.abstractmethod
    def format_progress(self, state: 'LoopState') -> str: ...
    @abc.abstractmethod
    def format_step_start(self, step: 'StepProgress') -> str: ...
    @abc.abstractmethod
    def format_step_complete(self, step: 'StepProgress') -> str: ...
