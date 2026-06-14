"""Docker 沙箱 — 使用 Docker 容器实现命令隔离执行。"""

from __future__ import annotations
import asyncio
import json
import os
import subprocess
import tempfile
import time
from typing import Optional
from ..core.interfaces import Sandbox
from ..core.types import ExecutionContext, SandboxMode, SandboxResult
from .policies import DefaultPolicyEngine


DEFAULT_DOCKER_IMAGE = "python:3.11-slim"


class DockerSandbox(Sandbox):
    """基于 Docker 容器的隔离沙箱。

    每个命令在独立的临时容器中执行，容器有资源限制、网络断开。
    需要主机安装 Docker 并确保当前用户有权限运行 docker 命令。

    特点:
    - 完全的文件系统隔离
    - 可配置内存/CPU 限制
    - 默认禁用网络
    - 自动清理容器
    - 挂载工作目录实现文件交换
    """

    def __init__(
        self,
        image: str = DEFAULT_DOCKER_IMAGE,
        memory_limit: str = "512m",
        cpu_limit: float = 1.0,
        network_disabled: bool = True,
        workdir_mount: Optional[str] = None,
        policy_engine: Optional[DefaultPolicyEngine] = None,
    ):
        self._image = image
        self._memory_limit = memory_limit
        self._cpu_limit = cpu_limit
        self._network_disabled = network_disabled
        self._workdir_mount = workdir_mount
        self._mode = SandboxMode.ISOLATED
        self._policies = policy_engine or DefaultPolicyEngine()

    async def execute_command(
        self, command: str, timeout: int = 30
    ) -> SandboxResult:
        """在 Docker 容器中执行命令。"""
        # 策略检查
        allowed, reason = await self._policies.check(
            "command", command, self._mode, ExecutionContext()
        )
        if not allowed:
            return SandboxResult(
                success=False, error=f"策略拒绝: {reason}", exit_code=-1
            )

        start = time.time()
        container_name = f"agent-sandbox-{int(start)}"

        try:
            # 构建 docker run 命令
            docker_cmd = [
                "docker", "run", "--rm",
                "--name", container_name,
                "--memory", self._memory_limit,
                "--cpus", str(self._cpu_limit),
            ]

            if self._network_disabled:
                docker_cmd.append("--network")
                docker_cmd.append("none")

            # 只读根文件系统
            docker_cmd.append("--read-only")

            # 挂载临时目录用于 /tmp
            docker_cmd.extend(["--tmpfs", "/tmp:size=64m"])

            # 挂载工作目录（如果指定）
            if self._workdir_mount:
                host_dir = os.path.abspath(self._workdir_mount)
                container_dir = "/workspace"
                docker_cmd.extend(["-v", f"{host_dir}:{container_dir}"])
                docker_cmd.extend(["-w", container_dir])

            # 安全选项：禁止提权
            docker_cmd.extend(["--security-opt", "no-new-privileges:true"])
            docker_cmd.extend(["--cap-drop", "ALL"])

            # 镜像和命令
            docker_cmd.append(self._image)

            # 在容器内执行命令 - 使用 shlex.quote 避免注入
            import shlex
            safe_cmd = " ".join(shlex.quote(c) for c in shlex.split(command))
            docker_cmd.extend(["/bin/sh", "-c", safe_cmd])

            proc = await asyncio.create_subprocess_exec(
                *docker_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(), timeout=timeout
                )
                elapsed = (time.time() - start) * 1000
                stdout_str = stdout.decode("utf-8", errors="replace")
                stderr_str = stderr.decode("utf-8", errors="replace")

                return SandboxResult(
                    success=proc.returncode == 0,
                    stdout=stdout_str,
                    stderr=stderr_str,
                    exit_code=proc.returncode or 0,
                    duration_ms=elapsed,
                )
            except asyncio.TimeoutError:
                # 超时时强制杀死容器
                try:
                    kill_proc = await asyncio.create_subprocess_exec(
                        "docker", "kill", container_name,
                        stdout=asyncio.subprocess.DEVNULL,
                        stderr=asyncio.subprocess.DEVNULL,
                    )
                    await kill_proc.wait()
                except Exception:
                    pass
                return SandboxResult(
                    success=False, error=f"命令执行超时 ({timeout}s)",
                    duration_ms=timeout * 1000,
                )

        except FileNotFoundError:
            return SandboxResult(
                success=False,
                error="Docker 未安装或不可用。请安装 Docker 或使用 LocalSandbox。",
                exit_code=-1,
            )
        except Exception as e:
            return SandboxResult(success=False, error=f"Docker 执行失败: {e}")

    async def read_file(self, path: str) -> str:
        """通过 Docker 容器读取文件。"""
        allowed, reason = await self._policies.check(
            "read", path, self._mode, ExecutionContext()
        )
        if not allowed:
            raise PermissionError(f"策略拒绝: {reason}")

        result = await self.execute_command(f"cat {path}")
        if result.success:
            return result.stdout
        raise FileNotFoundError(f"读取文件失败: {result.error}")

    async def write_file(self, path: str, content: str) -> None:
        """通过 Docker 容器写入文件。"""
        allowed, reason = await self._policies.check(
            "write", path, self._mode, ExecutionContext()
        )
        if not allowed:
            raise PermissionError(f"策略拒绝: {reason}")

        import shlex, base64
        # 安全方式：通过 base64 编码传输内容，避免 shell 转义问题
        encoded = base64.b64encode(content.encode("utf-8")).decode("ascii")
        safe_path = shlex.quote(path)
        cmd = f"mkdir -p $(dirname {safe_path}) && echo '{encoded}' | base64 -d > {safe_path}"
        result = await self.execute_command(cmd)
        if not result.success:
            raise IOError(f"写入文件失败: {result.error}")

    async def set_mode(self, mode: SandboxMode) -> None:
        self._mode = mode

    async def _run_docker(self, args: list) -> subprocess.CompletedProcess:
        """运行 docker 命令（跨平台兼容）。"""
        # Windows 上用 shell=True 避免 create_subprocess_exec 的权限问题
        try:
            proc = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: subprocess.run(
                    ["docker"] + args,
                    capture_output=True,
                    timeout=30,
                )
            )
            return proc
        except FileNotFoundError:
            raise RuntimeError("Docker not found")

    async def ensure_image(self) -> bool:
        """确保 Docker 镜像已拉取。"""
        try:
            import subprocess as sp_mod
            proc = await self._run_docker(["image", "inspect", self._image])
            if proc.returncode == 0:
                return True
            pull_proc = await self._run_docker(["pull", self._image])
            return pull_proc.returncode == 0
        except (RuntimeError, Exception):
            return False

