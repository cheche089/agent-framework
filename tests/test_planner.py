"""规划引擎测试。"""

import pytest
from agent_framework.planner.engine import DefaultPlannerEngine
from agent_framework.core.types import ExecutionContext, StepStatus


@pytest.mark.asyncio
async def test_create_plan():
    engine = DefaultPlannerEngine()
    ctx = ExecutionContext()
    plan = await engine.plan("测试目标", [], ctx)
    assert plan is not None
    assert plan.goal == "测试目标"
    assert len(plan.steps) > 0


@pytest.mark.asyncio
async def test_plan_steps_have_ids():
    engine = DefaultPlannerEngine()
    ctx = ExecutionContext()
    plan = await engine.plan("测试目标", [], ctx)
    for step in plan.steps:
        assert step.id is not None
        assert len(step.id) > 0


@pytest.mark.asyncio
async def test_replan_with_feedback():
    engine = DefaultPlannerEngine()
    ctx = ExecutionContext()
    plan = await engine.plan("测试目标", [], ctx)
    plan.steps[0].status = StepStatus.FAILED
    new_plan = await engine.replan(plan, "步骤失败: 测试错误", [], ctx)
    assert len(new_plan.steps) > 2


@pytest.mark.asyncio
async def test_empty_goal():
    engine = DefaultPlannerEngine()
    ctx = ExecutionContext()
    plan = await engine.plan("", [], ctx)
    assert plan is not None
    assert len(plan.steps) > 0
