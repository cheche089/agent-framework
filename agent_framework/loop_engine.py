
"""Agent Loop 执行引擎 — 实现 Thought → Action → Observation 循环。

该模块是 Agent Loop 的核心实现，严格遵循以下流程：
1. Think: 分析当前步骤需要什么信息
2. Act: 决定是否调用工具，或使用 LLM 推理
3. Observe: 获取工具/LLM 结果并更新状态
4. Evaluate: 判断当前步骤是否完成
5. Repeat / Replan / Complete

强制规则：
- 不允许一次性直接回答复杂任务
- 必须通过"计划 → 执行 → 反馈 → 修正"循环
- 每一步都必须基于上一步结果
- 工具优先于猜测
"""

from __future__ import annotations
import asyncio
import logging
import time
from typing import Any, Callable, Dict, List, Optional

from .core.interfaces import LoopEngine, ToolRegistry, HarnessEngine, ProgressFormatter
from .core.types import (
    AgentAction, AgentLoopStep, AgentObservation, AgentThought,
    ExecutionContext, LoopDecision, LoopState, Plan, PlanStep,
    StepProgress, StepStatus, TaskProgress, TaskStatus, ToolResult, ToolSpec,
)
from .llm import LLMClient, LLMConfig, LLMMessage

logger = logging.getLogger(__name__)


# ── System prompts for each phase of the loop ──────────────────────

THINK_SYSTEM_PROMPT = """你是一个任务执行 Agent，正在执行一个步骤。请分析当前步骤，思考需要什么信息。

你的输出应当包含：
1. 对当前步骤的理解分析
2. 需要哪些信息才能完成此步骤
3. 是否需要调用工具来获取信息
4. 如果不需要工具，直接给出推理结果

判断规则：
- 如果需要读取文件、执行命令、查询数据 → 需要工具
- 如果是推理、总结、分析已有信息 → 可以不用工具
- 当不确定时，优先选择使用工具"""

DECIDE_ACTION_PROMPT = """基于你的思考分析，决定下一步行动。

可用的工具：
{tools_desc}

请选择：
1. 如果需要调用工具，输出工具名称和参数
2. 如果不需要工具，标记为 no_tool 并直接给出推理结果"""

EVALUATE_PROMPT = """评估当前步骤的执行结果。

原始预期：{expected}
执行结果：{observation}

判断：
1. 步骤是否成功完成？
2. 输出是否符合预期？
3. 是否需要重试？
4. 是否需要更多信息？

可选决定：continue（继续下一步）/ replan（重新规划）/ needs_human（需要人类介入）/ abort（终止）/ complete（全部完成）"""


# ── Default Thought/Action/Observation Loop Engine ────────────────

class DefaultLoopEngine(LoopEngine):
    """默认的 Agent Loop 引擎，使用 LLM 驱动 Thought → Action → Observation 循环。

    特性：
    - 每一步都经过 Think → Act → Observe → Evaluate 四阶段
    - 支持自动重试 (最多 max_retries 次)
    - 支持动态重规划触发
    - 可注册回调钩子 (on_think, on_act, on_observe, on_evaluate)
    - 支持 Manus 风格的进度展示
    """

    def __init__(
        self,
        llm: Optional[LLMClient] = None,
        llm_config: Optional[LLMConfig] = None,
        harness: Optional[HarnessEngine] = None,
        tool_registry: Optional[ToolRegistry] = None,
        progress_formatter: Optional[ProgressFormatter] = None,
    ):
        self._llm = llm
        self._llm_config = llm_config or LLMConfig()
        self._harness = harness
        self._tool_registry = tool_registry
        self._formatter = progress_formatter or DefaultProgressFormatter()

        # callback hooks
        self._on_think: Optional[Callable] = None
        self._on_act: Optional[Callable] = None
        self._on_observe: Optional[Callable] = None
        self._on_evaluate: Optional[Callable] = None
        self._on_progress: Optional[Callable] = None

    # ── callback registration ──────────────────────────────────

    def on_think(self, handler: Callable) -> None:
        self._on_think = handler

    def on_act(self, handler: Callable) -> None:
        self._on_act = handler

    def on_observe(self, handler: Callable) -> None:
        self._on_observe = handler

    def on_evaluate(self, handler: Callable) -> None:
        self._on_evaluate = handler

    def on_progress(self, handler: Callable) -> None:
        self._on_progress = handler

    # ── core loop interface ─────────────────────────────────────

    async def think(self, step_id: str, goal: str, context: ExecutionContext,
                    tools: List[ToolSpec]) -> AgentThought:
        """Phase 1: 思考当前步骤需要什么信息。"""
        thought_text = await self._generate_thought(step_id, goal, context, tools)
        thought = AgentThought(step_id=step_id, thought=thought_text, timestamp=time.time())

        if self._on_think:
            await self._on_think(thought)

        return thought

    async def decide_action(self, thought: AgentThought, context: ExecutionContext,
                            tools: List[ToolSpec]) -> AgentAction:
        """Phase 2: 基于思考决定是否调用工具。"""
        action = await self._decide_action(thought, context, tools)

        # Harness 前置检查
        if self._harness:
            allowed, reason = await self._harness.pre_tool_check(action, context)
            if not allowed:
                logger.warning(f"Action blocked by harness: {reason}")
                return AgentAction(
                    tool_name="__blocked__",
                    params={"reason": reason, "original_tool": action.tool_name},
                    description=f"[BLOCKED] {reason}",
                )

        if self._on_act:
            await self._on_act(action)

        return action

    async def observe(self, action: AgentAction, result: ToolResult,
                      context: ExecutionContext) -> AgentObservation:
        """Phase 3: 获取工具执行结果并更新状态。"""
        observation = AgentObservation(
            step_id=action.tool_name,
            result=result,
            timestamp=time.time(),
        )

        # Harness 后置检查
        if self._harness:
            allowed, reason = await self._harness.post_tool_check(action, result, context)
            if not allowed:
                logger.warning(f"Observation blocked by harness: {reason}")

        if self._on_observe:
            await self._on_observe(observation)

        return observation

    async def evaluate_step(self, loop_step: AgentLoopStep,
                            context: ExecutionContext) -> LoopDecision:
        """Phase 4: 评估步骤执行结果，决定下一步操作。"""
        if loop_step.action and loop_step.action.tool_name == "__blocked__":
            return LoopDecision.NEEDS_HUMAN

        observation = loop_step.observation
        if observation is None:
            return LoopDecision.CONTINUE

        # 工具执行成功 → 继续
        if observation.result.success:
            return LoopDecision.CONTINUE

        # 工具执行失败
        loop_step.retry_count += 1
        if loop_step.retry_count < loop_step.max_retries:
            logger.info(f"Step {loop_step.step_id} failed, retry {loop_step.retry_count}/{loop_step.max_retries}")
            return LoopDecision.CONTINUE  # 重试

        logger.warning(f"Step {loop_step.step_id} exceeded max retries, requesting replan")
        return LoopDecision.REPLAN

        if self._on_evaluate:
            await self._on_evaluate(loop_step, decision)

        return decision

    async def should_replan(self, state: LoopState, context: ExecutionContext) -> bool:
        """判断是否需要重新规划。"""
        if state.replan_count >= state.max_replans:
            logger.warning(f"Replan limit reached ({state.max_replans})")
            return False

        # 检查是否有步骤需要重规划
        for step in state.steps:
            if step.decision == LoopDecision.REPLAN:
                return True

        return False

    async def format_final_answer(self, state: LoopState, context: ExecutionContext) -> str:
        """生成最终答案。"""
        return self._format_final_answer(state)

    # ── main execution loop ─────────────────────────────────────

    async def execute_loop(
        self,
        plan: Plan,
        context: ExecutionContext,
        tool_registry: Optional[ToolRegistry] = None,
    ) -> LoopState:
        """执行完整的 Agent Loop：对 plan 中的每个步骤执行 Thought → Action → Observation。

        返回 LoopState，包含所有步骤的 Thought/Action/Observation 记录。
        """
        if tool_registry:
            self._tool_registry = tool_registry

        state = LoopState(
            task_id=f"task_{int(time.time())}",
            goal=plan.goal,
            steps=[],
            plan=plan,
            status=TaskStatus.RUNNING,
        )

        tools = self._tool_registry.list_specs() if self._tool_registry else []

        # 对每个步骤执行 Thought → Action → Observation 循环
        for plan_step in plan.steps:
            if plan_step.status == StepStatus.SKIPPED:
                continue

            loop_step = AgentLoopStep(
                step_id=plan_step.id,
                plan_step=plan_step,
            )

            step_start = time.time()

            # --- Thought ---
            thought = await self.think(plan_step.id, plan.goal, context, tools)
            loop_step.thought = thought

            # --- Action ---
            action = await self.decide_action(thought, context, tools)
            loop_step.action = action

            # --- Execute tool ---
            if action.tool_name != "__blocked__" and action.tool_name != "no_tool":
                result = await self._execute_tool(action, context)
            elif action.tool_name == "no_tool":
                result = ToolResult.ok(action.description or "No tool needed")
            else:
                result = ToolResult.fail(f"Blocked: {action.params.get('reason', 'unknown')}")

            # --- Observe ---
            observation = await self.observe(action, result, context)
            loop_step.observation = observation

            # --- Evaluate ---
            decision = await self.evaluate_step(loop_step, context)
            loop_step.decision = decision
            loop_step.duration_ms = (time.time() - step_start) * 1000

            # 更新 PlanStep 状态
            plan_step.status = StepStatus.COMPLETED if result.success else StepStatus.FAILED
            plan_step.result = result.output if result.success else result.error

            state.steps.append(loop_step)

            # 进度回调
            if self._on_progress:
                await self._on_progress(state)

            # 检查是否需要重新规划
            if decision in (LoopDecision.REPLAN, LoopDecision.ABORT, LoopDecision.NEEDS_HUMAN):
                break

        # 判断最终状态
        all_completed = all(
            s.plan_step and s.plan_step.status == StepStatus.COMPLETED
            for s in state.steps
        )
        any_failed = any(
            s.decision in (LoopDecision.REPLAN, LoopDecision.ABORT)
            for s in state.steps
        )
        any_needs_human = any(
            s.decision == LoopDecision.NEEDS_HUMAN for s in state.steps
        )

        if any_needs_human:
            state.status = TaskStatus.NEEDS_HUMAN
        elif any_failed:
            state.status = TaskStatus.FAILED
        elif all_completed:
            state.status = TaskStatus.COMPLETED
        else:
            state.status = TaskStatus.RUNNING

        state.current_index = len(state.steps) - 1
        return state

    # ── internal methods ────────────────────────────────────────

    async def _generate_thought(self, step_id: str, goal: str,
                                context: ExecutionContext,
                                tools: List[ToolSpec]) -> str:
        """使用 LLM 生成思考内容。无 LLM 时回退到默认分析。"""
        if self._llm is None:
            return f"Execute step {step_id}: {goal}"

        tools_desc = self._format_tools(tools)
        messages = [
            LLMMessage(role="system", content=THINK_SYSTEM_PROMPT),
            LLMMessage(role="user", content=(
                f"Step ID: {step_id}\n"
                f"Task Goal: {goal}\n"
                f"Available tools:\\n{tools_desc}\\n\\n"
                f"Please provide your thinking for this step."
            )),
        ]
        try:
            return await self._llm.chat(messages, self._llm_config)
        except Exception as e:
            logger.warning(f"LLM think failed: {e}, using default")
            return f"Execute step {step_id}: analyze and use appropriate tools"

    async def _decide_action(self, thought: AgentThought,
                             context: ExecutionContext,
                             tools: List[ToolSpec]) -> AgentAction:
        """根据思考内容决定具体行动（工具调用或纯 LLM 推理）。"""
        if self._llm is None:
            # 无 LLM 时尝试从 thought 中解析工具调用
            return AgentAction(
                tool_name="no_tool",
                description=f"Execute: {thought.thought[:100]}",
            )

        # 使用 LLM 决定是否调用工具
        tools_desc = self._format_tools(tools)
        messages = [
            LLMMessage(role="system", content=DECIDE_ACTION_PROMPT.format(tools_desc=tools_desc)),
            LLMMessage(role="user", content=f"Thought: {thought.thought}\\n\\nBased on this thought, what action should I take?"),
        ]

        schema = {
            "name": "decide_action",
            "type": "object",
            "properties": {
                "tool_name": {
                    "type": "string",
                    "description": "Tool name to call, or 'no_tool' if no tool needed",
                },
                "params": {
                    "type": "object",
                    "description": "Parameters for the tool (empty if no_tool)",
                },
                "description": {
                    "type": "string",
                    "description": "Plain text description of the action",
                },
            },
            "required": ["tool_name", "description"],
        }

        try:
            result = await self._llm.chat_structured(messages, schema, self._llm_config)
            return AgentAction(
                tool_name=result.get("tool_name", "no_tool"),
                params=result.get("params", {}),
                description=result.get("description", ""),
                timestamp=time.time(),
            )
        except Exception as e:
            logger.warning(f"LLM decide_action failed: {e}, using fallback")
            return AgentAction(
                tool_name="no_tool",
                description=f"Fallback: {thought.thought[:80]}",
            )

    async def _execute_tool(self, action: AgentAction,
                            context: ExecutionContext) -> ToolResult:
        """执行工具调用。"""
        if self._tool_registry is None:
            return ToolResult.fail("No tool registry available")

        try:
            return await self._tool_registry.execute(
                action.tool_name, context, **action.params
            )
        except Exception as e:
            return ToolResult.fail(f"Tool execution error: {e}")

    def _format_tools(self, tools: List[ToolSpec]) -> str:
        if not tools:
            return "(no tools available)"
        lines = []
        for t in tools:
            lines.append(f"- {t.name}: {t.description}")
            if t.parameters.get("properties"):
                for pname, pinfo in t.parameters["properties"].items():
                    lines.append(f"    {pname}: {pinfo.get('description', '')}")
        return "\\n".join(lines)

    def _format_final_answer(self, state: LoopState) -> str:
        """生成格式化的最终答案。"""
        total = len(state.steps)
        completed = sum(1 for s in state.steps
                        if s.plan_step and s.plan_step.status == StepStatus.COMPLETED)
        failed = sum(1 for s in state.steps
                     if s.plan_step and s.plan_step.status == StepStatus.FAILED)

        lines = [
            "=" * 50,
            f"Task: {state.goal}",
            f"Status: {state.status.value}",
            f"Steps: {completed} completed, {failed} failed (total {total})",
            "=" * 50,
        ]

        for s in state.steps:
            status = (chr(10003) if s.plan_step and s.plan_step.status == StepStatus.COMPLETED
                      else chr(10007) if s.plan_step and s.plan_step.status == StepStatus.FAILED
                      else chr(183))
            action_desc = s.action.description if s.action else "pending"
            lines.append(f"  {status} {s.step_id}: {action_desc}")
            if s.thought:
                lines.append(f"      Thought: {s.thought.thought[:100]}")
            if s.observation:
                lines.append(f"      Result: {s.observation.summary}")

        # 最终答案
        if state.final_answer:
            lines.append("")
            lines.append("Final Answer:")
            lines.append(state.final_answer)

        return "\\n".join(lines)


# ── Progress Formatter (Manus-style) ──────────────────────────────

class DefaultProgressFormatter(ProgressFormatter):
    """Manus 风格的进度展示格式器。"""

    def format_progress(self, state: LoopState) -> str:
        total = len(state.steps)
        completed = sum(1 for s in state.steps
                        if s.plan_step and s.plan_step.status == StepStatus.COMPLETED)
        running = sum(1 for s in state.steps
                      if s.plan_step and s.plan_step.status == StepStatus.IN_PROGRESS)

        lines = [
            f"Task Progress: [{state.goal[:50]}...]",
        ]

        for i, s in enumerate(state.steps):
            if s.plan_step is None:
                continue

            prefix = chr(9500) if i < total - 1 else chr(9492)

            if s.plan_step.status == StepStatus.COMPLETED:
                icon = chr(10003)
            elif s.plan_step.status == StepStatus.IN_PROGRESS:
                icon = "->"
            elif s.plan_step.status == StepStatus.FAILED:
                icon = chr(10007)
            else:
                icon = ".."

            desc = s.action.description[:60] if s.action and s.action.description else s.plan_step.action[:60]
            lines.append(f"{prefix}{chr(9472)} {icon} {s.step_id}: {desc}")

        return "\\n".join(lines)

    def format_step_start(self, step: StepProgress) -> str:
        return f"  -> {step.step_id}: {step.description}"

    def format_step_complete(self, step: StepProgress) -> str:
        icon = chr(10003) if step.status == StepStatus.COMPLETED else chr(10007)
        return f"  {icon} {step.step_id}: {step.description}"
