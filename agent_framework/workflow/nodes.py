from __future__ import annotations
from typing import Any, Callable, Dict, List, Optional
from ..core.types import ExecutionContext, NodeType, WorkflowNode


class ActionNode:
    """动作节点：执行一个具体的操作（工具调用或 LLM 调用）。"""
    pass


class ConditionNode:
    """条件节点：根据条件结果选择分支。"""
    pass


class LoopNode:
    """循环节点：重复执行子节点直到满足条件。"""
    pass


class ParallelNode:
    """并行节点：并行执行多个子节点。"""
    pass


def create_action_node(
    node_id: str,
    tool_name: str,
    params: Optional[Dict[str, Any]] = None,
) -> WorkflowNode:
    """创建一个动作节点。"""
    return WorkflowNode(
        id=node_id,
        type=NodeType.ACTION,
        config={"tool": tool_name, "params": params or {}},
    )


def create_condition_node(
    node_id: str,
    condition: str,
    if_true: str,
    if_false: str,
) -> WorkflowNode:
    """创建一个条件节点。"""
    return WorkflowNode(
        id=node_id,
        type=NodeType.CONDITION,
        config={
            "condition": condition,
            "if_true": if_true,
            "if_false": if_false,
        },
    )


def create_sequence(nodes: List[WorkflowNode]) -> WorkflowNode:
    """将多个节点组合为顺序执行序列。"""
    if not nodes:
        raise ValueError("序列至少需要一个节点")
    root = nodes[0]
    for i in range(len(nodes) - 1):
        nodes[i].next_on_success = nodes[i + 1].id
    return root
