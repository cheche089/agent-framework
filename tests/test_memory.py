"""记忆系统测试。"""

import pytest
from agent_framework.memory.store import DefaultMemoryStore


@pytest.mark.asyncio
async def test_remember_and_recall():
    store = DefaultMemoryStore()
    await store.remember("key1", "value1", {"type": "test"})
    results = await store.recall("key1")
    assert len(results) == 1
    assert results[0].key == "key1"
    assert results[0].value == "value1"


@pytest.mark.asyncio
async def test_recall_no_match():
    store = DefaultMemoryStore()
    results = await store.recall("nonexistent")
    assert len(results) == 0


@pytest.mark.asyncio
async def test_forget():
    store = DefaultMemoryStore()
    await store.remember("key1", "value1")
    result = await store.forget("key1")
    assert result is True
    results = await store.recall("key1")
    assert len(results) == 0


@pytest.mark.asyncio
async def test_forget_nonexistent():
    store = DefaultMemoryStore()
    result = await store.forget("nonexistent")
    assert result is False


@pytest.mark.asyncio
async def test_summarize():
    store = DefaultMemoryStore()
    await store.remember("a", "1")
    await store.remember("b", "2")
    summary = await store.summarize()
    assert "2" in summary
