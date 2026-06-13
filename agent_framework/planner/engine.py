"""规划引擎 — 整合策略，管理规划生命周期，支持 LLM 重规划。"""

from __future__ import annotations
from typing import List, Optional
from ..core.interfaces import PlannerEngine, PlanningStrategy
from ..core.types import ExecutionContext, Plan, PlanStep, StepStatus, ToolSpec
from ..llm import LLMClient, LLMConfig, LLMMessage
from .strategies import LinearStrategy


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


class DefaultPlannerEngine(PlannerEngine):
    """默认规划引擎，使用策略模式支持不同的分解方式。"""

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

    async def plan(
        self, goal: str, tools: List[ToolSpec], context: ExecutionContext
    ) -> Plan:
        if self._strategy is None:
            # 如果未指定策略，尝试创建一个已注入 LLM 的 LinearStrategy
            self._strategy = LinearStrategy(llm=self._llm, llm_config=self._llm_config
            ) if self._llm else LinearStrategy()
        steps = await self._strategy.decompose(goal, tools, context)
        return Plan(goal=goal, steps=steps, status=StepStatus.PENDING)

    async def replan(
        self,
        plan: Plan,
        feedback: str,
        tools: List[ToolSpec],
        context: ExecutionContext,
    ) -> Plan:
        """根据执行反馈调整计划。

        1. 收集已完成/失败/待执行的步骤
        2. 使用 LLM 分析失败原因并生成修正方案
        3. 如果 LLM 不可用，使用简单的重试策略
        """
        if not self._llm:
            return self._fallback_replan(plan, feedback)

        completed = [s for s in plan.steps if s.status == StepStatus.COMPLETED]
        failed = [s for s in plan.steps if s.status in (StepStatus.FAILED, StepStatus.SKIPPED)]
        pending = [s for s in plan.steps if s.status == StepStatus.PENDING]

        # 如果所有步骤已完成或全部待执行，不需要重规划
        if not failed and not pending:
            return plan
        if not failed:
            return plan

        tools_desc = "\n".join(f"- {t.name}: {t.description}" for t in tools) if tools else "(暂无可用的工具)"

        completed_str = "\n".join(f"  [{s.id}] {s.action} -> {s.result or 'ok'}" for s in completed) or "  （无）"
        failed_str = "\n".join(f"  [{s.id}] {s.action}\n    期望: {s.expected_outcome}\n    反馈: {feedback}" for s in failed)
        pending_str = "\n".join(f"  [{s.id}] {s.action}" for s in pending) or "  （无）"

        system_prompt = REPLAN_SYSTEM_PROMPT.format(
            goal=plan.goal,
            completed_steps=completed_str,
            failed_steps=failed_str,
            pending_steps=pending_str,
            tools_desc=tools_desc,
        )

        messages = [
            LLMMessage(role="system", content=system_prompt),
            LLMMessage(role="user", content=f"执行步骤 [{failed[0].id}] 时失败，反馈：{feedback}\n\n请给出修正后的剩余步骤。"),
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
                            "depends_on": {"type": "array", "items": {"type": "string"}},
                            "status": {"type": "string", "enum": ["pending", "skipped"]},
                        },
                        "required": ["id", "action", "expected_outcome", "status"],
                    },
                }
            },
            "required": ["revised_steps"],
        }

        try:
            result = await self._llm.chat_structured(messages, schema, self._llm_config)
            revised = result.get("revised_steps", [])
            new_steps = []
            id_counter = len(plan.steps) + 1
            for s in revised:
                status = StepStatus.SKIPPED if s.get("status") == "skipped" else StepStatus.PENDING
                new_steps.append(PlanStep(
                    id=s.get("id", f"step_{id_counter}"),
                    action=s.get("action", ""),
                    expected_outcome=s.get("expected_outcome", ""),
                    depends_on=s.get("depends_on", []),
                    status=status,
                ))
                id_counter += 1
            plan.steps = completed + failed + new_steps
            return plan
        except Exception as e:
            return self._fallback_replan(plan, f"LLM 重规划失败: {e}")

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
