"""规划引擎 — 整合策略，管理规划生命周期，支持 LLM 重规划。

增强版 (v2.0) 新增：
- 任务理解阶段 (Task Understanding)：使用 LLM 分析任务目标
- 增强重规划：使用 LoopState 的 Thought/Action/Observation 上下文
- 更结构化的任务分解
"""

from __future__ import annotations
import logging
from typing import Any, Dict, List, Optional

from ..core.interfaces import PlannerEngine, PlanningStrategy
from ..core.types import (
    ExecutionContext, LoopState, Plan, PlanStep, StepStatus, ToolSpec,
)
from ..llm import LLMClient, LLMConfig, LLMMessage
from .strategies import LinearStrategy

logger = logging.getLogger(__name__)


# ── Added prompts ─────────────────────────────────────────────

REPLAN_SYSTEM_PROMPT = """你是一个任务重规划助手。用户有一个正在执行的计划，其中一些步骤失败了。
请分析失败原因，然后调整剩余步骤。

规划目标：{goal}

已完成的步骤：
{completed_steps}

失败的步骤及反馈：
{failed_steps}

待执行的步骤：
{pending_steps}

可用工具：
{tools_desc}

请输出调整后的剩余步骤列表（包含需要修正的步骤）。注意：
- 可以修改待执行步骤的顺序、参数
- 可以为失败的步骤添加修正/重试步骤
- 如果某个步骤无法修复，将其标记为 status: "skipped" 并给出原因"""


TASK_UNDERSTAND_PROMPT = """你是一个任务分析专家。在开始执行任务之前，你需要先深入理解用户的目标。

提供的任务：{goal}
可用工具：{tools_desc}

请分析并输出：
1. 任务本质：这个任务要达成什么核心目标？
2. 关键信息：需要哪些关键信息/数据？
3. 风险点：可能遇到的困难或陷阱
4. 执行策略：推荐的执行路径和步骤顺序

基于以上分析，生成可执行的计划步骤。每个步骤必须对应一个工具调用或明确的行动。"""


UNDERSTAND_SCHEMA = {
    "name": "task_understanding",
    "type": "object",
    "properties": {
        "core_goal": {"type": "string", "description": "任务核心目标"},
        "key_info_needed": {"type": "array", "items": {"type": "string"}, "description": "需要的关键信息"},
        "risks": {"type": "array", "items": {"type": "string"}, "description": "可能的风险点"},
        "execution_strategy": {"type": "string", "description": "推荐的执行策略"},
    },
    "required": ["core_goal", "key_info_needed", "risks", "execution_strategy"],
}


# ── Enhanced planner ──────────────────────────────────────────

class DefaultPlannerEngine(PlannerEngine):
    """默认规划引擎，使用策略模式支持不同的分解方式。

    增强版 (v2.0)：
    - 任务理解阶段 (understand_task)：用 LLM 先分析任务再生成计划
    - 增强重规划 (replan_with_loop_state)：使用 LoopState 上下文
    - 向后兼容原始接口
    """

    def __init__(
        self,
        strategy: Optional[PlanningStrategy] = None,
        llm: Optional[LLMClient] = None,
        llm_config: Optional[LLMConfig] = None,
    ):
        self._strategy = strategy
        self._llm = llm
        self._llm_config = llm_config or LLMConfig()
        self._llm_available = llm is not None

    # ── Task Understanding (新増) ─────────────────────────────

    async def understand_task(
        self, goal: str, tools: List[ToolSpec], context: ExecutionContext
    ) -> Dict[str, Any]:
        """任务理解阶段：使用 LLM 分析任务目标，识别关键信息和风险。

        返回结构化的任务理解结果。
        """
        if not self._llm:
            return {
                "core_goal": goal,
                "key_info_needed": [],
                "risks": [],
                "execution_strategy": "Execute step by step",
            }

        tools_desc = self._format_tools(tools)
        messages = [
            LLMMessage(
                role="system",
                content=TASK_UNDERSTAND_PROMPT.format(
                    goal=goal, tools_desc=tools_desc
                ),
            ),
            LLMMessage(
                role="user",
                content=f"请分析这个任务并给出执行计划：{goal}",
            ),
        ]

        try:
            result = await self._llm.chat_structured(
                messages, UNDERSTAND_SCHEMA, self._llm_config
            )
            logger.info(
                f"Task understanding: core_goal={result.get('core_goal', '')[:60]}"
            )
            return result
        except Exception as e:
            logger.warning(f"Task understanding failed: {e}, using default")
            return {
                "core_goal": goal,
                "key_info_needed": [],
                "risks": [],
                "execution_strategy": f"Execute step by step (LLM unavailable: {e})",
            }

    # ── Planning (兼容原接口) ────────────────────────────────

    async def plan(
        self, goal: str, tools: List[ToolSpec], context: ExecutionContext
    ) -> Plan:
        """生成执行计划。

        增强行为：
        1. 先进行任务理解（如果 LLM 可用）
        2. 将理解结果注入策略分解
        3. 生成带依赖关系的步骤列表
        """
        if self._strategy is None:
            self._strategy = (
                LinearStrategy(llm=self._llm, llm_config=self._llm_config)
                if self._llm
                else LinearStrategy()
            )

        # 任务理解
        task_analysis = await self.understand_task(goal, tools, context)

        # 将任务理解结果存入上下文
        context.metadata["task_analysis"] = task_analysis

        # 策略分解
        steps = await self._strategy.decompose(goal, tools, context)
        return Plan(goal=goal, steps=steps, status=StepStatus.PENDING)

    # ── Re-planning ───────────────────────────────────────────

    async def replan(
        self,
        plan: Plan,
        feedback: str,
        tools: List[ToolSpec],
        context: ExecutionContext,
    ) -> Plan:
        """根据执行反馈调整计划。

        兼容原始接口。内部增强：
        - 使用 context 中的 task_analysis 作为上下文
        - 更好的错误分析和恢复策略
        """
        if not self._llm:
            return self._fallback_replan(plan, feedback)

        completed = [
            s for s in plan.steps if s.status == StepStatus.COMPLETED
        ]
        failed = [
            s
            for s in plan.steps
            if s.status in (StepStatus.FAILED, StepStatus.SKIPPED)
        ]
        pending = [
            s for s in plan.steps if s.status == StepStatus.PENDING
        ]

        if not failed and not pending:
            return plan
        if not failed:
            return plan

        tools_desc = (
            "\n".join(f"- {t.name}: {t.description}" for t in tools)
            if tools
            else "(暂无可用工具)"
        )

        completed_str = (
            "\n".join(
                f"  [{s.id}] {s.action} -> {s.result or 'ok'}"
                for s in completed
            )
            or "  (无)"
        )
        failed_str = "\n".join(
            f"  [{s.id}] {s.action}\n    期望: {s.expected_outcome}\n    反馈: {feedback}"
            for s in failed
        )
        pending_str = (
            "\n".join(f"  [{s.id}] {s.action}" for s in pending)
            or "  (无)"
        )

        system_prompt = REPLAN_SYSTEM_PROMPT.format(
            goal=plan.goal,
            completed_steps=completed_str,
            failed_steps=failed_str,
            pending_steps=pending_str,
            tools_desc=tools_desc,
        )

        # 注入任务理解上下文
        task_analysis = context.metadata.get("task_analysis", {})
        user_content = (
            f"执行步骤 [{failed[0].id}] 时失败，反馈：{feedback}\n\n"
        )
        if task_analysis.get("risks"):
            user_content += (
                f"之前识别的风险：{', '.join(task_analysis['risks'][:3])}\n\n"
            )
        user_content += "请给出修正后的剩余步骤。"

        messages = [
            LLMMessage(role="system", content=system_prompt),
            LLMMessage(role="user", content=user_content),
        ]

        schema = {
            "name": "replan",
            "type": "object",
            "properties": {
                "revised_steps": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "string"},
                            "action": {"type": "string"},
                            "expected_outcome": {"type": "string"},
                            "depends_on": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                            "status": {
                                "type": "string",
                                "enum": ["pending", "skipped"],
                            },
                        },
                        "required": [
                            "id",
                            "action",
                            "expected_outcome",
                            "status",
                        ],
                    },
                }
            },
            "required": ["revised_steps"],
        }

        try:
            result = await self._llm.chat_structured(
                messages, schema, self._llm_config
            )
            revised = result.get("revised_steps", [])
            new_steps = []
            id_counter = len(plan.steps) + 1
            for s in revised:
                status = (
                    StepStatus.SKIPPED
                    if s.get("status") == "skipped"
                    else StepStatus.PENDING
                )
                new_steps.append(
                    PlanStep(
                        id=s.get("id", f"step_{id_counter}"),
                        action=s.get("action", ""),
                        expected_outcome=s.get("expected_outcome", ""),
                        depends_on=s.get("depends_on", []),
                        status=status,
                    )
                )
                id_counter += 1
            plan.steps = completed + failed + new_steps
            return plan
        except Exception as e:
            return self._fallback_replan(plan, f"LLM 重规划失败: {e}")

    # ── Enhanced Replan with LoopState ────────────────────────

    async def replan_with_loop_state(
        self,
        plan: Plan,
        loop_state: LoopState,
        tools: List[ToolSpec],
        context: ExecutionContext,
    ) -> Plan:
        """使用 LoopState 上下文进行增强重规划。

        相较于 replan()，此方法使用更丰富的上下文：
        - 每个步骤的 Thought/Action/Observation
        - Harness 指标
        - 重规划计数
        """
        # 从 LoopState 构建反馈
        feedback_parts = []
        for ls in loop_state.steps:
            if ls.plan_step and ls.plan_step.status == StepStatus.FAILED:
                obs_text = (
                    ls.observation.summary if ls.observation else "no observation"
                )
                thought_text = (
                    ls.thought.thought[:100] if ls.thought else "no thought"
                )
                feedback_parts.append(
                    f"[{ls.step_id}] thought: {thought_text}, result: {obs_text}"
                )

        feedback = "; ".join(feedback_parts) or "steps need revision"

        # 使用增强的 replan
        return await self.replan(plan, feedback, tools, context)

    # ── Fallback ──────────────────────────────────────────────

    def _fallback_replan(self, plan: Plan, feedback: str) -> Plan:
        """LLM 不可用时的回退重规划。"""
        for step in plan.steps:
            if step.status == StepStatus.FAILED:
                plan.steps.append(
                    PlanStep(
                        id=f"{step.id}_retry",
                        action=step.action,
                        expected_outcome=f"重试: {feedback[:80]}",
                        depends_on=[step.id],
                        status=StepStatus.PENDING,
                    )
                )
        return plan

    # ── Helper ────────────────────────────────────────────────

    def _format_tools(self, tools: List[ToolSpec]) -> str:
        if not tools:
            return "(暂无可用工具)"
        lines = []
        for t in tools:
            lines.append(f"- {t.name}: {t.description}")
            if t.parameters.get("properties"):
                for pname, pinfo in t.parameters["properties"].items():
                    lines.append(f"    {pname}: {pinfo.get('description', '')}")
        return "\n".join(lines)
