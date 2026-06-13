"""沙箱安全策略引擎。"""

from __future__ import annotations
import time
from typing import Any, Dict, List, Optional, Tuple
from ..core.interfaces import PolicyRule
from ..core.types import ExecutionContext, SandboxMode


class AllowListRule(PolicyRule):
    """白名单规则：只允许在名单中的命令/路径。

    allowed: 允许的命令名列表（小写）。
    """

    def __init__(self, allowed: Optional[List[str]] = None):
        self._allowed = [a.lower() for a in (allowed or [])]

    async def check(
        self, action: str, target: str, context: ExecutionContext
    ) -> Tuple[bool, str]:
        if action == "command":
            cmd = target.split()[0].lower() if target else ""
            if self._allowed and cmd not in self._allowed:
                return False, f"命令 '{cmd}' 不在白名单中"
        return True, ""


class DenyListRule(PolicyRule):
    """黑名单规则：拒绝名单中的命令/路径。"""

    def __init__(self, denied: Optional[List[str]] = None):
        self._denied = [d.lower() for d in (denied or [])]

    async def check(
        self, action: str, target: str, context: ExecutionContext
    ) -> Tuple[bool, str]:
        if action == "command":
            cmd = target.split()[0].lower() if target else ""
            if cmd in self._denied:
                return False, f"命令 '{cmd}' 在黑名单中"
        return True, ""


class TimeoutRule(PolicyRule):
    """超时限制规则。"""

    def __init__(self, max_seconds: int = 60):
        self._max = max_seconds

    async def check(
        self, action: str, target: str, context: ExecutionContext
    ) -> Tuple[bool, str]:
        return True, ""


class DefaultPolicyEngine:
    """默认策略引擎，按沙箱模式组合策略规则。"""

    def __init__(self):
        self._rules: Dict[SandboxMode, List[PolicyRule]] = {
            SandboxMode.RESTRICTED: [
                DenyListRule(denied=["rm", "del", "format", "shutdown", "reboot", "poweroff"]),
                TimeoutRule(max_seconds=30),
            ],
            SandboxMode.ISOLATED: [
                AllowListRule(allowed=["echo", "ls", "cat", "pwd", "python", "node", "head", "tail", "wc", "sort", "grep"]),
                TimeoutRule(max_seconds=15),
            ],
            SandboxMode.PERMISSIVE: [],
        }

    async def check(
        self, action: str, target: str, mode: SandboxMode, context: ExecutionContext
    ) -> Tuple[bool, str]:
        rules = self._rules.get(mode, [])
        for rule in rules:
            allowed, reason = await rule.check(action, target, context)
            if not allowed:
                return False, reason
        return True, ""
