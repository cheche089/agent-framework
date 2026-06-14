from __future__ import annotations
import asyncio
import logging
from typing import Any, Callable, Dict, List, Optional

from .config import AgentConfig
from .core.interfaces import (
    BaseTool, ContextManager, HarnessEngine, LoopEngine, MemoryStore,
    PlannerEngine, ProgressFormatter, Sandbox, SkillManager, ToolRegistry,
    WorkflowEngine,
)
from .core.types import (
    AgentLoopStep, ExecutionContext, LoopDecision, LoopState,
    Message, MessageRole, Plan, PlanStep, StepProgress,
    StepStatus, TaskProgress, TaskStatus, ToolResult, WorkflowNode,
)
from .harness import DefaultHarnessEngine
from .loop_engine import DefaultLoopEngine, DefaultProgressFormatter

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
        loop_engine: Optional[LoopEngine] = None,
        harness: Optional[HarnessEngine] = None,
        progress_formatter: Optional[ProgressFormatter] = None,
    ):
        self.tools = tool_registry
        self.planner = planner
        self.memory = memory
        self.context = context_mgr
        self.workflow = workflow_engine
        self.skills = skill_mgr
        self.sandbox = sandbox
        self.config = config or AgentConfig.default()

        # v2.0: Agent Loop 引擎
        self._loop_engine = loop_engine
        # v2.0: Harness 引擎
        self._harness = harness
        # v2.0: 进度格式器
        self._formatter = progress_formatter or DefaultProgressFormatter()

        # 兼容原回调接口
        self._on_tool_start: Optional[Callable] = None
        self._on_step_complete: Optional[Callable] = None
        self._on_error: Optional[Callable] = None

        # v2.0 新增回调
        self._on_thought: Optional[Callable] = None
        self._on_action: Optional[Callable] = None
        self._on_observation: Optional[Callable] = None
        self._on_progress_update: Optional[Callable] = None
        self._on_human_needed: Optional[Callable] = None

        # Long-running task 持久化路径
        self._checkpoint_dir: Optional[str] = None

    def on_tool_start(self, handler: Callable) -> None:
        self._on_tool_start = handler

    def on_step_complete(self, handler: Callable) -> None:
        self._on_step_complete = handler

    def on_error(self, handler: Callable) -> None:
        self._on_error = handler

    # v2.0 callback registration methods
    def on_thought(self, handler: Callable) -> None:
        self._on_thought = handler

    def on_action(self, handler: Callable) -> None:
        self._on_action = handler

    def on_observation(self, handler: Callable) -> None:
        self._on_observation = handler

    def on_progress_update(self, handler: Callable) -> None:
        self._on_progress_update = handler

    def on_human_needed(self, handler: Callable) -> None:
        self._on_human_needed = handler

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

    async def run_with_loop(self, task: str) -> LoopState:
        ctx = ExecutionContext(config=self.config)
        loop_engine = self._get_loop_engine()
        plan = await self.planner.plan(task, self.tools.list_specs(), ctx)
        ctx.metadata["plan"] = plan
        state = await loop_engine.execute_loop(plan, ctx, self.tools)
        replan_attempts = 0
        while state.status == TaskStatus.RUNNING and not state.completed():
            if await loop_engine.should_replan(state, ctx):
                replan_attempts += 1
                state.replan_count = replan_attempts
                feedback = self._build_feedback(state)
                plan = await self.planner.replan(plan, feedback, self.tools.list_specs(), ctx)
                state = await loop_engine.execute_loop(plan, ctx, self.tools)
        state.final_answer = await loop_engine.format_final_answer(state, ctx)
        state.status = TaskStatus.COMPLETED if plan.completed else TaskStatus.FAILED
        return state

    async def run_long_running(self, task: str, checkpoint_dir=None) -> LoopState:
        import os, glob, json
        if checkpoint_dir:
            self._checkpoint_dir = checkpoint_dir
        state = await self._load_checkpoint()
        if state:
            return await self._resume_task(state)
        ctx = ExecutionContext(config=self.config)
        loop_engine = self._get_loop_engine()
        plan = await self.planner.plan(task, self.tools.list_specs(), ctx)
        state = await loop_engine.execute_loop(plan, ctx, self.tools)
        await self._save_checkpoint(state)
        replan_attempts = 0
        while state.status == TaskStatus.RUNNING and replan_attempts < (self.config.max_iterations // 10):
            if await loop_engine.should_replan(state, ctx):
                replan_attempts += 1
                state.replan_count = replan_attempts
                plan = await self.planner.replan(plan, self._build_feedback(state), self.tools.list_specs(), ctx)
                state = await loop_engine.execute_loop(plan, ctx, self.tools)
                await self._save_checkpoint(state)
        state.final_answer = await loop_engine.format_final_answer(state, ctx)
        state.status = TaskStatus.COMPLETED if plan.completed else TaskStatus.FAILED
        return state

    async def _save_checkpoint(self, state: LoopState) -> None:
        import os, json
        if not self._checkpoint_dir:
            return
        os.makedirs(self._checkpoint_dir, exist_ok=True)
        ckp = os.path.join(self._checkpoint_dir, f"checkpoint_{state.task_id}.json")
        try:
            data = {"task_id": state.task_id, "goal": state.goal, "status": state.status.value, "current_index": state.current_index, "timestamp": __import__('time').time()}
            with open(ckp, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)
        except Exception:
            pass

    async def _load_checkpoint(self):
        import os, glob, json
        if not self._checkpoint_dir:
            return None
        files = glob.glob(os.path.join(self._checkpoint_dir, "checkpoint_*.json"))
        if not files:
            return None
        try:
            with open(max(files, key=os.path.getmtime), "r", encoding="utf-8") as f:
                data = json.load(f)
            return LoopState(task_id=data["task_id"], goal=data["goal"], steps=[], status=TaskStatus(data["status"]), current_index=data["current_index"])
        except Exception:
            return None

    async def _resume_task(self, state: LoopState) -> LoopState:
        ctx = ExecutionContext(config=self.config)
        loop_engine = self._get_loop_engine()
        plan = await self.planner.plan(state.goal, self.tools.list_specs(), ctx)
        remaining = Plan(goal=plan.goal, steps=plan.steps[state.current_index:])
        new_state = await loop_engine.execute_loop(remaining, ctx, self.tools)
        new_state.final_answer = await loop_engine.format_final_answer(new_state, ctx)
        return new_state

    def _build_feedback(self, state: LoopState) -> str:
        parts = []
        for s in state.steps:
            if s.plan_step and s.plan_step.status == StepStatus.FAILED:
                obs = s.observation.summary if s.observation else "unknown error"
                parts.append(f"[{s.step_id}] {obs}")
        return "; ".join(parts) or "needs revision"

    def _get_loop_engine(self) -> LoopEngine:
        if self._loop_engine is None:
            from .loop_engine import DefaultLoopEngine
            self._loop_engine = DefaultLoopEngine(harness=self._harness, tool_registry=self.tools, progress_formatter=self._formatter)
            if self._on_thought:
                self._loop_engine.on_think(self._on_thought)
            if self._on_action:
                self._loop_engine.on_act(self._on_action)
            if self._on_observation:
                self._loop_engine.on_observe(self._on_observation)
            if self._on_progress_update:
                self._loop_engine.on_progress(lambda s: __import__('asyncio').ensure_future(self._on_progress_update(s)))
        return self._loop_engine

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

    def display_progress(self, state: LoopState) -> str:
        return self._formatter.format_progress(state)

    @property
    def loop_engine(self) -> Optional[LoopEngine]:
        return self._loop_engine

    @property
    def harness(self) -> Optional[HarnessEngine]:
        return self._harness

    @property
    def checkpoint_dir(self) -> Optional[str]:
        return self._checkpoint_dir

    @checkpoint_dir.setter
    def checkpoint_dir(self, path: str) -> None:
        self._checkpoint_dir = path

    def get_metrics(self) -> Dict[str, Any]:
        if self._harness:
            return self._harness.get_metrics()
        return {}

