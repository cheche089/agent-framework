from __future__ import annotations
from typing import Any, Dict, List, Optional
from ..core.interfaces import BaseTool, ToolRegistry
from ..core.types import ExecutionContext, ToolResult, ToolSpec


class DefaultToolRegistry(ToolRegistry):
    """基于字典的工具注册中心。"""

    def __init__(self):
        self._tools: Dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        if tool.name in self._tools:
            raise ValueError(f"工具 '{tool.name}' 已注册")
        self._tools[tool.name] = tool

    def unregister(self, name: str) -> None:
        self._tools.pop(name, None)

    def get(self, name: str) -> Optional[BaseTool]:
        return self._tools.get(name)

    def list_specs(self) -> List[ToolSpec]:
        return [t.to_spec() for t in self._tools.values()]

    async def execute(self, name: str, ctx: ExecutionContext, **kwargs: Any) -> ToolResult:
        tool = self.get(name)
        if tool is None:
            return ToolResult.fail(f"工具 '{name}' 未注册")
        return await tool.execute(ctx, **kwargs)
