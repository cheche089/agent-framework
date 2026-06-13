"""沙箱系统测试。"""

import pytest
from agent_framework.sandbox.sandbox import LocalSandbox
from agent_framework.sandbox.policies import DefaultPolicyEngine
from agent_framework.core.types import SandboxMode


@pytest.mark.asyncio
async def test_set_mode():
    sandbox = LocalSandbox()
    assert sandbox is not None
    await sandbox.set_mode(SandboxMode.PERMISSIVE)


@pytest.mark.asyncio
async def test_execute_allowed():
    sandbox = LocalSandbox()
    await sandbox.set_mode(SandboxMode.PERMISSIVE)
    result = await sandbox.execute_command("echo hello")
    assert result.success
    assert "hello" in result.stdout


@pytest.mark.asyncio
async def test_policy_block():
    engine = DefaultPolicyEngine()
    allowed, reason = await engine.check(
        "command", "rm -rf /", SandboxMode.RESTRICTED, None
    )
    assert not allowed
    assert "rm" in reason
