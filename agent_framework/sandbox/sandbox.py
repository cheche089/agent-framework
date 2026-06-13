"""Local sandbox - uses subprocess.run for cross-platform compatibility."""

from __future__ import annotations
import asyncio
import os
import subprocess
import time
from typing import Optional
from ..core.interfaces import Sandbox
from ..core.types import ExecutionContext, SandboxMode, SandboxResult
from .policies import DefaultPolicyEngine


class LocalSandbox(Sandbox):

    def __init__(self, policy_engine: Optional[DefaultPolicyEngine] = None):
        self._mode = SandboxMode.RESTRICTED
        self._policies = policy_engine or DefaultPolicyEngine()
        self._workdir = os.getcwd()

    async def execute_command(self, command: str, timeout: int = 30) -> SandboxResult:
        allowed, reason = await self._policies.check("command", command, self._mode, ExecutionContext())
        if not allowed:
            return SandboxResult(success=False, error=str("Policy denied: " + reason), exit_code=-1)

        start = time.time()
        try:
            proc = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: subprocess.run(
                    command,
                    capture_output=True,
                    shell=True,
                    cwd=self._workdir,
                    timeout=timeout,
                )
            )
            elapsed = (time.time() - start) * 1000
            return SandboxResult(
                success=(proc.returncode == 0),
                stdout=proc.stdout.decode("utf-8", errors="replace") if proc.stdout else "",
                stderr=proc.stderr.decode("utf-8", errors="replace") if proc.stderr else "",
                exit_code=proc.returncode or 0,
                duration_ms=elapsed,
            )
        except subprocess.TimeoutExpired:
            return SandboxResult(success=False, error=str("Timeout"), duration_ms=timeout * 1000)
        except Exception as e:
            return SandboxResult(success=False, error=str(e))

    async def read_file(self, path: str) -> str:
        allowed, reason = await self._policies.check("read", path, self._mode, ExecutionContext())
        if not allowed:
            raise PermissionError(str("Policy denied: " + reason))
        with open(path, "r", encoding="utf-8") as f:
            return f.read()

    async def write_file(self, path: str, content: str) -> None:
        allowed, reason = await self._policies.check("write", path, self._mode, ExecutionContext())
        if not allowed:
            raise PermissionError(str("Policy denied: " + reason))
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)

    async def set_mode(self, mode: SandboxMode) -> None:
        self._mode = mode
