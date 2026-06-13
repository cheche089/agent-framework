"""工具系统测试。"""

import pytest
from agent_framework.tools.registry import DefaultToolRegistry
from agent_framework.tools.builtin import FileReadTool, FileWriteTool, ShellTool
from agent_framework.core.types import ExecutionContext


@pytest.mark.asyncio
async def test_register_and_get():
    registry = DefaultToolRegistry()
    tool = FileReadTool()
    registry.register(tool)
    assert registry.get("read_file") is tool


@pytest.mark.asyncio
async def test_double_register():
    registry = DefaultToolRegistry()
    registry.register(FileReadTool())
    with pytest.raises(ValueError, match="已注册"):
        registry.register(FileReadTool())


@pytest.mark.asyncio
async def test_unregister():
    registry = DefaultToolRegistry()
    registry.register(FileReadTool())
    registry.unregister("read_file")
    assert registry.get("read_file") is None


@pytest.mark.asyncio
async def test_list_specs():
    registry = DefaultToolRegistry()
    registry.register(FileReadTool())
    registry.register(FileWriteTool())
    specs = registry.list_specs()
    assert len(specs) == 2
    names = [s.name for s in specs]
    assert "read_file" in names
    assert "write_file" in names


@pytest.mark.asyncio
async def test_execute_unknown():
    registry = DefaultToolRegistry()
    ctx = ExecutionContext()
    result = await registry.execute("unknown_tool", ctx)
    assert not result.success
    assert "未注册" in (result.error or "")


@pytest.mark.asyncio
async def test_execute_nonexistent_file():
    registry = DefaultToolRegistry()
    registry.register(FileReadTool())
    ctx = ExecutionContext()
    result = await registry.execute("read_file", ctx, path="/nonexistent/file.txt")
    assert not result.success
    assert result.error is not None
