"""线性分解策略 — 接入 LLM 进行智能目标分解。"""

from __future__ import annotations
from typing import Any, Dict, List, Optional
from ...core.interfaces import PlanningStrategy
from ...core.types import ExecutionContext, PlanStep, StepStatus, ToolSpec
from ...llm import LLMClient, LLMConfig, LLMMessage


DECOMPOSE_SYSTEM_PROMPT = """你是一个任务规划助手。你的任务是将用户的目标分解为可执行的步骤。

可用的工具：
{tools_desc}

请将目标分解为最多 8 个步骤，按执行顺序排列。对每个步骤输出：
- id: 唯一标识符 (step_1, step_2, ...)
- action: 要执行的动作，格式为 tool_name(param1=value1, param2=value2)
- expected_outcome: 预期的执行结果描述
- depends_on: 依赖的步骤 id 列表（依赖多步用逗号分隔）

思考过程：先理解目标的本质，确定需要调用哪些工具，然后按依赖关系排序。"""


class LinearStrategy(PlanningStrategy):
    """线性分解策略：使用 LLM 将目标智能分解为有序步骤。"""

    def __init__(self, llm: Optional[LLMClient] = None, llm_config: Optional[LLMConfig] = None):
        self._llm = llm
        self._llm_config = llm_config or LLMConfig()

    async def decompose(
        self, goal: str, tools: List[ToolSpec], context: ExecutionContext
    ) -> List[PlanStep]:
        """使用 LLM 将目标分解为可执行步骤。"""
        if self._llm is None:
            return self._fallback_decompose(goal)

        # 构建工具描述
        tools_lines = []
        for t in tools:
            tools_lines.append(f"- {t.name}: {t.description}")
            if t.parameters.get("properties"):
                props = t.parameters["properties"]
                required = t.parameters.get("required", [])
                for pname, pinfo in props.items():
                    req = "必填" if pname in required else "可选"
                    tools_lines.append(f"    {pname} ({req}): {pinfo.get('description', '')}")
        tools_desc = "\n".join(tools_lines) if tools_lines else "（暂无可用工具）"

        system_prompt = DECOMPOSE_SYSTEM_PROMPT.format(tools_desc=tools_desc)

        messages = [
            LLMMessage(role="system", content=system_prompt),
            LLMMessage(role="user", content=f"请将以下目标分解为步骤：\n\n{goal}"),
        ]

        schema = {
            "name": "task_plan",
            "type": "object",
            "properties": {
                "steps": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "string", "description": "步骤标识 step_1, step_2 ..."},
                            "action": {"type": "string", "description": "工具调用表达式"},
                            "expected_outcome": {"type": "string", "description": "预期结果"},
                            "depends_on": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "依赖的步骤id列表",
                            },
                        },
                        "required": ["id", "action", "expected_outcome"],
                    },
                }
            },
            "required": ["steps"],
        }

        try:
            result = await self._llm.chat_structured(messages, schema, self._llm_config)
            steps_data = result.get("steps", [])
            return [
                PlanStep(
                    id=s.get("id", f"step_{i+1}"),
                    action=s.get("action", ""),
                    expected_outcome=s.get("expected_outcome", ""),
                    depends_on=s.get("depends_on", []),
                    status=StepStatus.PENDING,
                )
                for i, s in enumerate(steps_data)
            ]
        except Exception as e:
            # LLM 调用失败时回退
            return self._fallback_decompose(goal, str(e))

    def _fallback_decompose(self, goal: str, error: str = "") -> List[PlanStep]:
        """LLM 不可用时的回退分解。"""
        if error:
            prefix = f"[LLM 不可用: {error[:80]}]\n"
        else:
            prefix = "[LLM 未配置，使用默认分解]\n"

        return [
            PlanStep(
                id="step_1",
                action="understand_goal",
                expected_outcome=f"{prefix}理解目标: {goal[:80]}...",
                status=StepStatus.PENDING,
            ),
            PlanStep(
                id="step_2",
                action="execute_plan",
                expected_outcome="执行计划完成",
                depends_on=["step_1"],
                status=StepStatus.PENDING,
            ),
        ]
