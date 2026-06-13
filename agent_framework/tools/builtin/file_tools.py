from __future__ import annotations
import os
import asyncio
from typing import Any
from ..base import BaseTool, ExecutionContext, ToolResult


class FileReadTool(BaseTool):
    """读取文件内容。"""
    name = "read_file"
    description = "读取指定路径的文本文件内容"
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "文件路径"},
            "encoding": {"type": "string", "description": "文件编码，默认 utf-8"},
        },
        "required": ["path"],
    }

    async def execute(self, ctx: ExecutionContext, **kwargs: Any) -> ToolResult:
        path = kwargs.get("path", "")
        encoding = kwargs.get("encoding", "utf-8")
        if not path or '..' in path.split(os.sep):
            return ToolResult.fail(f"Security: path traversal detected in '{path}'")
        try:
            with open(path, "r", encoding=encoding) as f:
                content = f.read()
            return ToolResult.ok(content, path=path, size=len(content))
        except Exception as e:
            return ToolResult.fail(f"读取文件失败: {e}")


class FileWriteTool(BaseTool):
    """写入文件内容。"""
    name = "write_file"
    description = "向指定路径的文件写入内容（会覆盖已有文件）"
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "文件路径"},
            "content": {"type": "string", "description": "写入的内容"},
            "encoding": {"type": "string", "description": "文件编码，默认 utf-8"},
        },
        "required": ["path", "content"],
    }

    async def execute(self, ctx: ExecutionContext, **kwargs: Any) -> ToolResult:
        path = kwargs.get("path", "")
        content = kwargs.get("content", "")
        encoding = kwargs.get("encoding", "utf-8")
        if not path or '..' in path.split(os.sep):
            return ToolResult.fail(f"Security: path traversal detected in '{path}'")
        try:
            os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
            with open(path, "w", encoding=encoding) as f:
                f.write(content)
            return ToolResult.ok(f"已写入 {len(content)} 字符到 {path}", path=path)
        except Exception as e:
            return ToolResult.fail(f"写入文件失败: {e}")


class ShellTool(BaseTool):
    """执行 shell 命令。"""
    name = "shell"
    description = "在本地执行一条 shell 命令并返回输出"
    parameters = {
        "type": "object",
        "properties": {
            "command": {"type": "string", "description": "要执行的命令"},
            "timeout": {"type": "integer", "description": "超时秒数，默认 30"},
        },
        "required": ["command"],
    }

    async def execute(self, ctx: ExecutionContext, **kwargs: Any) -> ToolResult:
        command = kwargs.get("command", "")
        timeout = kwargs.get("timeout", 30)
        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            return ToolResult.ok(
                stdout.decode("utf-8", errors="replace"),
                stderr=stderr.decode("utf-8", errors="replace"),
                exit_code=proc.returncode,
            )
        except asyncio.TimeoutError:
            return ToolResult.fail(f"命令执行超时 ({timeout}s)")
        except Exception as e:
            return ToolResult.fail(f"命令执行失败: {e}")

