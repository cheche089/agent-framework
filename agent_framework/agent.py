from __future__ import annotations
import asyncio
import logging
from typing import Any, Callable, Dict, List, Optional

from .config import AgentConfig
from .core.interfaces import (
    BaseTool, ContextManager, MemoryStore, PlannerEngine,
    Sandbox, SkillManager, ToolRegistry, WorkflowEngine,
)
from .core.types import (
    ExecutionContext, Message, MessageRole, Plan, PlanStep,
    StepStatus, ToolResult, WorkflowNode,
)

logger = logging.getLogger(__name__)


class Agent:
    """Agent 主类，协调工具、规划、记忆、上下文、工作流、技能、沙箱七大模块。"""

    def __init__(
        self,
        tool_registry: ToolRegistry,
        planner: PlannerEngine,
        memory: MemoryStore,
        context_mgr: ContextManager,
        workflow_engine: WorkflowEngine,
        skill_mgr: SkillManager,
        sandbox: Sandbox,
        config: Optional[AgentConfig] = None,
    ):
        self.tools = tool_registry
        self.planner = planner
        self.memory = memory
        self.context = context_mgr
        self.workflow = workflow_engine
        self.skills = skill_mgr
        self.sandbox = sandbox
        self.config = config or AgentConfig.default()
        self._on_tool_start: Optional[Callable] = None
        self._on_step_complete: Optional[Callable] = None
        self._on_error: Optional[Callable] = None

    def on_tool_start(self, handler: Callable) -> None:
        self._on_tool_start = handler

    def on_step_complete(self, handler: Callable) -> None:
        self._on_step_complete = handler

    def on_error(self, handler: Callable) -> None:
        self._on_error = handler

    async def run(self, task: str) -> str:
        """执行一个任务：规划 -> 逐步骤执行 -> 返回最终结果。"""
        ctx = ExecutionContext(config=self.config)
        plan = await self.planner.plan(task, self.tools.list_specs(), ctx)

        for step in plan.steps:
            step.status = StepStatus.IN_PROGRESS
            try:
                result = await self._execute_step(step, ctx)
                step.status = StepStatus.COMPLETED if result.success else StepStatus.FAILED
                step.result = result.output or result.error

                if self._on_step_complete:
                    await self._on_step_complete(step)

                if not result.success:
                    plan = await self.planner.replan(plan, result.error or "", self.tools.list_specs(), ctx)
            except Exception as e:
                step.status = StepStatus.FAILED
                step.result = str(e)
                if self._on_error:
                    await self._on_error(e)
                plan = await self.planner.replan(plan, str(e), self.tools.list_specs(), ctx)

        return self._format_summary(plan)

    async def run_with_workflow(self, workflow: WorkflowNode, task: str) -> Dict[str, Any]:
        ctx = ExecutionContext(config=self.config)
        ctx.metadata["task"] = task
        return await self.workflow.execute(workflow, ctx)

    async def _execute_step(self, step: PlanStep, ctx: ExecutionContext) -> ToolResult:
        """执行单个规划步骤。"""
        parts = step.action.split("(", 1)
        tool_name = parts[0].strip()
        kwargs: Dict[str, Any] = {}
        if len(parts) > 1:
            arg_str = parts[1].rstrip(")")
            for pair in arg_str.split(","):
                if "=" in pair:
                    k, v = pair.split("=", 1)
                    kwargs[k.strip()] = v.strip().strip("'\"")

        if self._on_tool_start:
            await self._on_tool_start(tool_name, kwargs)

        return await self.tools.execute(tool_name, ctx, **kwargs)

    def _format_summary(self, plan: Plan) -> str:
        total = len(plan.steps)
        completed = sum(1 for s in plan.steps if s.status == StepStatus.COMPLETED)
        failed = sum(1 for s in plan.steps if s.status == StepStatus.FAILED)
        lines = [f"目标: {plan.goal}", f"完成: {completed}/{total} 步骤"]
        if failed:
            lines.append(f"失败: {failed} 步骤")
        for s in plan.steps:
            status = chr(10003) if s.status == StepStatus.COMPLETED else chr(10007) if s.status == StepStatus.FAILED else chr(183)
            lines.append(f"  {status} {s.id}: {s.action}")
            if s.result:
                lines.append(f"     -> {s.result[:80]}")
        return "\n".join(lines)

