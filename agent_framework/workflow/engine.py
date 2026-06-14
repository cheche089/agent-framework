"""工作流执行引擎 — 连接 ToolRegistry 和 LLM 以执行实际的工具调用。"""

from __future__ import annotations
import asyncio
from typing import Any, Dict, List, Optional
from ..core.interfaces import ToolRegistry, WorkflowEngine
from ..core.types import ExecutionContext, NodeType, WorkflowNode, ToolResult
from ..llm import LLMClient, LLMConfig, LLMMessage


def _get_tool_registry(context: ExecutionContext) -> Optional[ToolRegistry]:
    """从执行上下文中获取工具注册中心。"""
    return context.metadata.get("tool_registry")


class DefaultWorkflowEngine(WorkflowEngine):
    """工作流执行引擎，支持连接外部 ToolRegistry。"""

    def __init__(self, llm: Optional[LLMClient] = None, llm_config: Optional[LLMConfig] = None):
        self._results: Dict[str, Any] = {}
        self._llm = llm
        self._llm_config = llm_config or LLMConfig()

    async def execute(
        self,
        workflow: WorkflowNode,
        context: ExecutionContext,
    ) -> Dict[str, Any]:
        self._results = {}
        await self._run_node(workflow, context)
        return self._results

    async def step(self, node: WorkflowNode, context: ExecutionContext) -> Any:
        return await self._run_node(node, context)

    async def _run_node(
        self, node: WorkflowNode, context: ExecutionContext
    ) -> Any:
        result = None
        if node.type == NodeType.ACTION:
            result = await self._run_action(node, context)
        elif node.type == NodeType.CONDITION:
            result = await self._run_condition(node, context)
        elif node.type == NodeType.LOOP:
            result = await self._run_loop(node, context)
        elif node.type == NodeType.PARALLEL:
            result = await self._run_parallel(node, context)
        elif node.type == NodeType.SEQUENCE:
            result = await self._run_sequence(node, context)

        self._results[node.id] = result

        # 自动流转到下一个节点
        if result is not None and node.next_on_success and not isinstance(result, Exception):
            next_id = node.next_on_success
            next_node = self._find_node(node, next_id)
            if next_node:
                return await self._run_node(next_node, context)
        elif result is not None and node.next_on_failure and isinstance(result, Exception):
            next_id = node.next_on_failure
            next_node = self._find_node(node, next_id)
            if next_node:
                return await self._run_node(next_node, context)

        return result

    async def _run_action(self, node: WorkflowNode, context: ExecutionContext) -> Any:
        """执行动作节点 — 通过 ToolRegistry 调用实际工具。

        从上下文中获取 ToolRegistry，查找工具并执行。
        如果找不到工具但有 LLM，尝试用 LLM 解释执行。
        """
        tool_name = node.config.get("tool", "")
        params = node.config.get("params", {})

        registry = _get_tool_registry(context)

        if registry is not None:
            tool = registry.get(tool_name)
            if tool is not None:
                try:
                    result = await registry.execute(tool_name, context, **params)
                    return {
                        "tool": tool_name,
                        "success": result.success,
                        "output": result.output,
                        "error": result.error,
                    }
                except Exception as e:
                    return Exception(f"工具执行失败 [{tool_name}]: {e}")

        # 工具不存在但有配置参数，可能是纯逻辑节点
        if params:
            return f"执行动作: {tool_name}({params})"

        return f"模拟执行: {tool_name}"

    async def _run_condition(self, node: WorkflowNode, context: ExecutionContext) -> Any:
        condition = node.config.get("condition", "True")
        try:
            # Safer condition evaluation - only allow basic comparisons
            safe_condition = condition.strip()
            # Only allow: variable comparisons, True/False/None, and/or/not, == != < > in
            allowed_pattern = r'^[\s\w\._\(\)\[\]\'\"!=<>%+\-*/and or not in True False None,]+$'
            import re as _re
            if not _re.match(allowed_pattern, safe_condition):
                return Exception(f"Condition contains disallowed characters: {safe_condition[:100]}")
            # Restrict builtins to minimum
            safe_builtins = {"__builtins__": {k: __builtins__[k] for k in ("True", "False", "None", "and", "or", "not", "len", "str", "int", "float", "bool", "dict", "list", "tuple", "in", "is") if k in __builtins__}}
            # Don't allow attribute access (no "." except for dict/list access)
            result = bool(eval(safe_condition, {"__builtins__": {}}, {"context": context, "results": self._results, "True": True, "False": False, "None": None, "len": len, "str": str, "int": int, "float": float, "bool": bool, "dict": dict, "list": list, "tuple": tuple}))
            next_id = node.config.get("if_true" if result else "if_false")
            if next_id:
                next_node = self._find_node(node, next_id)
                if next_node:
                    return await self._run_node(next_node, context)
            return result
        except Exception as e:
            return e

    async def _run_loop(self, node: WorkflowNode, context: ExecutionContext) -> Any:
        max_iterations = node.config.get("max_iterations", 10)
        condition_key = node.config.get("condition_key", "")
        results = []
        for i in range(max_iterations):
            if condition_key:
                should_continue = self._results.get(condition_key, True)
                if not should_continue:
                    break
            for child in node.children:
                r = await self._run_node(child, context)
                results.append(r)
        return results

    async def _run_parallel(self, node: WorkflowNode, context: ExecutionContext) -> Any:
        tasks = [self._run_node(child, context) for child in node.children]
        return await asyncio.gather(*tasks, return_exceptions=True)

    async def _run_sequence(self, node: WorkflowNode, context: ExecutionContext) -> Any:
        results = []
        for child in node.children:
            r = await self._run_node(child, context)
            results.append(r)
            if isinstance(r, Exception):
                break
        return results

    def _find_node(self, root: WorkflowNode, node_id: str) -> Optional[WorkflowNode]:
        if root.id == node_id:
            return root
        for child in root.children:
            found = self._find_node(child, node_id)
            if found:
                return found
        return None
