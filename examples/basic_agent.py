"""Agent 框架完整使用示例 — 展示所有模块和 LLM 集成。"""

import asyncio
import os

# LLM 模块
from agent_framework.llm import LLMClient, OpenAIClient, LLMConfig, LLMMessage

# Agent 核心
from agent_framework import Agent, AgentConfig
from agent_framework.tools.registry import DefaultToolRegistry
from agent_framework.tools.builtin import FileReadTool, FileWriteTool, ShellTool
from agent_framework.planner.engine import DefaultPlannerEngine
from agent_framework.planner.strategies import LinearStrategy
from agent_framework.memory.store import DefaultMemoryStore
from agent_framework.context.manager import DefaultContextManager
from agent_framework.workflow.engine import DefaultWorkflowEngine
from agent_framework.skills.manager import DefaultSkillManager
from agent_framework.sandbox.sandbox import LocalSandbox
from agent_framework.sandbox.docker_sandbox import DockerSandbox
from agent_framework.core.types import (
    ExecutionContext, NodeType, WorkflowNode,
    SandboxMode, PlanStep, StepStatus,
)
from agent_framework.workflow.nodes import create_action_node


async def demo_llm_basic():
    """演示 LLM 基本调用。"""
    print("=== 1. LLM 基本调用 ===")
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("  跳过 LLM 演示 (OPENAI_API_KEY 未设置)")
        return None

    client = OpenAIClient(LLMConfig(model="gpt-4o", temperature=0.3))
    messages = [
        LLMMessage(role="system", content="你是一个助手"),
        LLMMessage(role="user", content="用一句话介绍你自己"),
    ]
    response = await client.chat(messages)
    print(f"  LLM 响应: {response[:100]}...")
    return client


async def demo_planner_with_llm(llm: LLMClient):
    """演示 LLM 智能分解。"""
    print("\n=== 2. 规划系统 (LLM 分解) ===")
    registry = DefaultToolRegistry()
    registry.register(FileReadTool())
    registry.register(FileWriteTool())
    registry.register(ShellTool())

    strategy = LinearStrategy(llm=llm, llm_config=LLMConfig(model="gpt-4o-mini"))
    engine = DefaultPlannerEngine(strategy=strategy, llm=llm)

    plan = await engine.plan("读取当前目录的文件列表并保存到 summary.txt", registry.list_specs(), ExecutionContext())
    print(f"  目标: {plan.goal}")
    print(f"  步骤数: {len(plan.steps)}")
    for s in plan.steps:
        print(f"    [{s.id}] {s.action}")
        print(f"         期望: {s.expected_outcome[:60]}...")
        if s.depends_on:
            print(f"         依赖: {s.depends_on}")


async def demo_memory_with_llm(llm: LLMClient):
    """演示 LLM 记忆摘要。"""
    print("\n=== 3. 记忆系统 (LLM 摘要) ===")
    store = DefaultMemoryStore(llm=llm)
    await store.remember("user_name", "张三", {"type": "profile"})
    await store.remember("user_goal", "学习 Python 编程", {"type": "preference"})
    await store.remember("progress", "已完成基础语法", {"type": "progress"})
    await store.remember("next_step", "学习面向对象编程", {"type": "plan"})

    items = await store.recall("用户", limit=10)
    print(f"  检索到 {len(items)} 条记忆")
    summary = await store.summarize()
    print(f"  摘要: {summary[:200]}...")


async def demo_context_compression(llm: LLMClient):
    """演示上下文压缩。"""
    print("\n=== 4. 上下文管理 (LLM 压缩) ===")
    from agent_framework.core.types import Message, MessageRole

    mgr = DefaultContextManager(llm=llm)
    await mgr.add_message(Message(role=MessageRole.SYSTEM, content="你是一个助手"))

    for i in range(15):
        await mgr.add_message(Message(
            role=MessageRole.USER if i % 2 == 0 else MessageRole.ASSISTANT,
            content=f"第{i+1}轮对话的内容包含一些重要信息，需要被保留在上下文中",
        ))

    print(f"  压缩前: {mgr.token_count()} tokens, {len(mgr._messages)} 条消息")
    await mgr.compress()
    print(f"  压缩后: {mgr.token_count()} tokens, {len(mgr._messages)} 条消息")


async def demo_workflow_with_tools():
    """演示工作流 + ToolRegistry。"""
    print("\n=== 5. 工作流 (ToolRegistry 连接) ===")
    registry = DefaultToolRegistry()
    registry.register(ShellTool())

    engine = DefaultWorkflowEngine()
    workflow = WorkflowNode(
        id="demo_wf",
        type=NodeType.SEQUENCE,
        children=[
            create_action_node("step1", "shell", {"command": "echo 步骤1完成"}),
            create_action_node("step2", "shell", {"command": "echo 步骤2完成"}),
        ],
    )
    ctx = ExecutionContext()
    ctx.metadata["tool_registry"] = registry

    result = await engine.execute(workflow, ctx)
    for node_id, output in result.items():
        print(f"  {node_id}: {output}")


async def demo_skills(llm: LLMClient):
    """演示技能系统。"""
    print("\n=== 6. 技能系统 (LLM 执行) ===")
    import tempfile

    skill_content = """# code_review

## Description
对 Python 代码进行审查，检查常见的代码质量问题

## Instructions
1. 读取指定文件的内容
2. 检查以下问题：
   - 缺少类型注解
   - 未使用的导入
   - 长函数（超过 50 行）
   - 缺少异常处理
3. 输出审查结果列表

## Requires
read_file
"""

    mgr = DefaultSkillManager(llm=llm)
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, encoding="utf-8") as f:
        f.write(skill_content)
        tmp_path = f.name

    try:
        spec = await mgr.load_skill(tmp_path)
        print(f"  已加载技能: {spec.name}")

        ctx = ExecutionContext()
        result = await mgr.execute_skill("code_review", {"file_path": "example.py"}, ctx)
        print(f"  执行结果: {result[:200]}...")
    finally:
        import os as os_mod
        os_mod.unlink(tmp_path)


async def demo_sandbox():
    """演示沙箱系统。"""
    print("\n=== 7. 沙箱系统 (本地/策略) ===")
    sandbox = LocalSandbox()

    # 受限模式下执行命令
    result = await sandbox.execute_command("echo 'Hello from sandbox'")
    print(f"  本地沙箱: success={result.success}, stdout={result.stdout.strip()}")

    # 策略检查
    from agent_framework.sandbox.policies import DefaultPolicyEngine
    from agent_framework.core.types import SandboxMode
    engine = DefaultPolicyEngine()
    allowed, reason = await engine.check("command", "rm -rf /", SandboxMode.RESTRICTED, None)
    print(f"  策略拦截: allowed={allowed}, reason={reason}")

    # 尝试 Docker 沙箱（如果 Docker 可用）
    docker_sb = DockerSandbox()
    available = await docker_sb.ensure_image()
    if available:
        d_result = await docker_sb.execute_command("echo 'Hello from Docker'")
        print(f"  Docker 沙箱: success={d_result.success}, stdout={d_result.stdout.strip()}")
    else:
        print("  Docker 沙箱: Docker 不可用，跳过")


async def demo_memory_retrieval():
    """演示 TF-IDF 语义检索。"""
    print("\n=== 8. 记忆检索 (TF-IDF) ===")
    from agent_framework.memory.backends import InMemoryBackend
    from agent_framework.core.types import MemoryItem

    backend = InMemoryBackend()
    items = [
        MemoryItem(key="python_intro", value="Python 是动态类型的编程语言"),
        MemoryItem(key="java_intro", value="Java 是静态类型的编程语言"),
        MemoryItem(key="python_web", value="Flask 和 Django 是 Python Web 框架"),
        MemoryItem(key="data_science", value="NumPy 和 Pandas 用于数据处理"),
        MemoryItem(key="machine_learning", value="PyTorch 和 TensorFlow 用于深度学习"),
    ]
    for item in items:
        await backend.store(item)

    results = await backend.retrieve("Python 框架", limit=3)
    print(f"  查询 'Python 框架':")
    for r in results:
        print(f"    [{r.key}] {r.value}")


async def main():
    print("=" * 60)
    print("Agent 框架 — 完整功能演示")
    print("=" * 60)

    # LLM 演示（需要 OPENAI_API_KEY）
    llm = await demo_llm_basic()

    if llm:
        await demo_planner_with_llm(llm)
        await demo_memory_with_llm(llm)
        await demo_context_compression(llm)
        await demo_skills(llm)
    else:
        print("\n  [跳过 LLM 相关演示 — 设置 OPENAI_API_KEY 后重试]")

    # 无需 LLM 的演示
    await demo_workflow_with_tools()
    await demo_sandbox()
    await demo_memory_retrieval()

    print("\n" + "=" * 60)
    print("演示完成！")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
