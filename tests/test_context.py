"""上下文管理测试。"""

import pytest
from agent_framework.context.manager import DefaultContextManager
from agent_framework.core.types import ContextLimit, Message, MessageRole


@pytest.mark.asyncio
async def test_add_message():
    mgr = DefaultContextManager()
    msg = Message(role=MessageRole.USER, content="hello")
    await mgr.add_message(msg)
    assert mgr.token_count() > 0


@pytest.mark.asyncio
async def test_build_prompt():
    mgr = DefaultContextManager()
    await mgr.add_message(Message(role=MessageRole.SYSTEM, content="你是助手"))
    await mgr.add_message(Message(role=MessageRole.USER, content="你好"))

    prompt = await mgr.build_prompt()
    assert len(prompt) == 2
    assert prompt[0].role == MessageRole.SYSTEM


@pytest.mark.asyncio
async def test_window_cutoff():
    limit = ContextLimit(max_tokens=10)
    mgr = DefaultContextManager(limit=limit)
    for i in range(5):
        await mgr.add_message(Message(
            role=MessageRole.USER,
            content=f"这是第{i+1}条很长很长的测试消息内容"
        ))
    prompt = await mgr.build_prompt()
    assert len(prompt) < 5


@pytest.mark.asyncio
async def test_compress():
    mgr = DefaultContextManager()
    for i in range(20):
        await mgr.add_message(Message(role=MessageRole.USER, content=f"msg{i}"))
    await mgr.compress()
    assert mgr.token_count() < 1000
