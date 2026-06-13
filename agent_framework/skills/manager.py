"""技能管理器 — 支持 LLM 指令注入执行。"""

from __future__ import annotations
import os
from typing import Any, Dict, List, Optional
from ..core.interfaces import SkillLoader, SkillManager
from ..core.types import ExecutionContext, SkillSpec
from ..llm import LLMClient, LLMConfig, LLMMessage
from .loader import MarkdownSkillLoader, YamlSkillLoader


SKILL_EXEC_SYSTEM_TEMPLATE = """你正在执行一个预定义的"技能"。请严格按照以下指令操作。

技能名称: {skill_name}
技能描述: {skill_description}

执行指令:
{instructions}

可用工具：
{tools_desc}

请严格按照指令执行，每一步输出执行结果。"""


class DefaultSkillManager(SkillManager):
    """默认技能管理器，支持 LLM 指令注入执行。"""

    def __init__(
        self,
        llm: Optional[LLMClient] = None,
        llm_config: Optional[LLMConfig] = None,
    ):
        self._skills: Dict[str, SkillSpec] = {}
        self._loaders: List[SkillLoader] = [MarkdownSkillLoader(), YamlSkillLoader()]
        self._llm = llm
        self._llm_config = llm_config or LLMConfig()

    def add_loader(self, loader: SkillLoader) -> None:
        self._loaders.append(loader)

    async def load_skill(self, source: str) -> SkillSpec:
        """从源加载技能。"""
        ext = os.path.splitext(source)[1].lower()
        for loader in self._loaders:
            spec = await loader.load(source)
            self._skills[spec.name] = spec
            return spec
        raise ValueError(f"不支持的文件格式: {ext}")

    async def execute_skill(
        self, name: str, params: Dict[str, Any], context: ExecutionContext
    ) -> str:
        """执行技能 — 将技能指令注入 LLM 提示并执行。

        步骤：
        1. 查找已加载的技能
        2. 构建包含技能指令的系统提示
        3. 注入工具列表
        4. 调用 LLM 执行指令
        5. 如果 LLM 不可用，返回指令文本
        """
        spec = self._skills.get(name)
        if spec is None:
            raise KeyError(f"技能 '{name}' 未加载")

        # 获取可用工具列表
        tools_desc = ""
        tool_registry = context.metadata.get("tool_registry")
        if tool_registry:
            specs = tool_registry.list_specs()
            tools_lines = []
            for t in specs:
                tools_lines.append(f"- {t.name}: {t.description}")
            tools_desc = "\n".join(tools_lines) if tools_lines else "（无）"

        # 用参数替换指令中的占位符
        instructions = spec.instructions
        for k, v in params.items():
            instructions = instructions.replace(f"{{{{{k}}}}}", str(v))
            instructions = instructions.replace(f"${{{k}}}", str(v))

        if self._llm is None:
            return f"[LLM 未配置] 技能 '{name}' 指令:\n{instructions[:500]}..."

        # 构建 LLM 提示
        system_prompt = SKILL_EXEC_SYSTEM_TEMPLATE.format(
            skill_name=spec.name,
            skill_description=spec.description,
            instructions=instructions,
            tools_desc=tools_desc,
        )

        user_prompt = f"请执行技能 '{name}'。"
        if params:
            user_prompt += f"\n参数:\n"
            for k, v in params.items():
                user_prompt += f"  {k}: {v}\n"

        messages = [
            LLMMessage(role="system", content=system_prompt),
            LLMMessage(role="user", content=user_prompt),
        ]

        try:
            cfg = LLMConfig(
                model=self._llm_config.model,
                temperature=0.2,  # 技能执行需要低温度以保证精确性
                max_tokens=self._llm_config.max_tokens,
            )
            return await self._llm.chat(messages, cfg)
        except Exception as e:
            return f"[LLM 执行失败] 技能 '{name}' 出错: {e}\n\n指令原文:\n{instructions[:500]}"

    def list_skills(self) -> List[SkillSpec]:
        return list(self._skills.values())

    async def unload_skill(self, name: str) -> bool:
        if name in self._skills:
            del self._skills[name]
            return True
        return False
