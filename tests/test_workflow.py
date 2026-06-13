"""工作流引擎测试。"""

import pytest
from agent_framework.workflow.engine import DefaultWorkflowEngine
from agent_framework.workflow.nodes import create_action_node
from agent_framework.core.types import ExecutionContext, NodeType, WorkflowNode


@pytest.mark.asyncio
async def test_action_node():
    engine = DefaultWorkflowEngine()
    node = create_action_node("test", "echo", {"text": "hello"})
    ctx = ExecutionContext()
    result = await engine.execute(node, ctx)
    assert "test" in result


@pytest.mark.asyncio
async def test_sequence():
    engine = DefaultWorkflowEngine()
    node1 = create_action_node("step1", "tool1")
    node2 = create_action_node("step2", "tool2")
    sequence = WorkflowNode(
        id="root",
        type=NodeType.SEQUENCE,
        children=[node1, node2],
    )
    ctx = ExecutionContext()
    result = await engine.execute(sequence, ctx)
    assert "step1" in result
    assert "step2" in result
