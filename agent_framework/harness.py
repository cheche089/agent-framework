"""Harness Engineering 模块 — 提供执行与控制框架。

功能：
1. 安全护栏 (Guardrails)：划定行为边界，防止越权/违规操作
2. 反馈回路 (Feedback Loops)：监控执行过程，发现错误时自我纠正或请求人类介入
3. 工具调用管理：统一的接口层，防止信息过载
4. 执行上下文控制：确保 Agent 按照预定方向持续正确地执行
5. 指标收集：记录执行过程中的各类指标供分析
"""

from __future__ import annotations
import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

from .core.interfaces import HarnessEngine
from .core.types import (
    AgentAction, AgentLoopStep, ExecutionContext, LoopDecision,
    LoopState, TaskStatus, ToolResult,
)

logger = logging.getLogger(__name__)


# ── Metric types ───────────────────────────────────────────────

@dataclass
class HarnessMetric:
    tool_calls: int = 0
    tool_errors: int = 0
    blocked_calls: int = 0
    replan_requests: int = 0
    human_interventions: int = 0
    total_duration_ms: float = 0.0
    step_metrics: List[Dict[str, Any]] = field(default_factory=list)


# ── Guardrail rules ────────────────────────────────────────────

@dataclass
class GuardrailRule:
    """安全护栏规则定义。"""
    name: str
    rule_type: str  # "pre_tool" | "post_tool" | "action" | "path"
    check_fn: Callable[[AgentAction, ExecutionContext], Tuple[bool, str]]
    severity: str = "error"  # "error" | "warn"
    enabled: bool = True


# ── Default Harness Engine ─────────────────────────────────────

class DefaultHarnessEngine(HarnessEngine):
    """默认 Harness 引擎，提供安全护栏、反馈回路和控制框架。

    配置选项：
    - max_tool_calls_per_step: 每步最大工具调用数
    - max_consecutive_errors: 最大连续错误数
    - allowed_tools: 允许的工具白名单（空=全部允许）
    - denied_tools: 禁止的工具黑名单
    - human_intervention_threshold: 触发人类介入的阈值
    - auto_heal: 是否自动尝试修复
    """

    def __init__(
        self,
        max_tool_calls_per_step: int = 5,
        max_consecutive_errors: int = 3,
        allowed_tools: Optional[List[str]] = None,
        denied_tools: Optional[List[str]] = None,
        human_intervention_threshold: int = 2,
        auto_heal: bool = True,
    ):
        self._max_tool_calls = max_tool_calls_per_step
        self._max_errors = max_consecutive_errors
        self._allowed_tools = allowed_tools
        self._denied_tools = denied_tools or [
            "rm", "del", "format", "shutdown", "reboot", "poweroff",
            "reset", "init", "drop", "truncate",
        ]
        self._human_threshold = human_intervention_threshold
        self._auto_heal = auto_heal

        self._metrics = HarnessMetric()
        self._consecutive_errors = 0
        self._tool_call_count = 0
        self._guardrails: List[GuardrailRule] = []
        self._callbacks: Dict[str, List[Callable]] = {
            "on_blocked": [],
            "on_error": [],
            "on_replan": [],
            "on_human_needed": [],
            "on_tool_call": [],
        }

        # 注册默认护栏规则
        self._register_default_guardrails()

    # ── Guardrail management ─────────────────────────────────────

    def add_guardrail(self, rule: GuardrailRule) -> None:
        self._guardrails.append(rule)

    def remove_guardrail(self, name: str) -> bool:
        for i, r in enumerate(self._guardrails):
            if r.name == name:
                self._guardrails.pop(i)
                return True
        return False

    def _register_default_guardrails(self) -> None:
        """注册默认的安全护栏规则。"""

        # 禁止危险命令
        self.add_guardrail(GuardrailRule(
            name="denied_tools",
            rule_type="pre_tool",
            check_fn=self._check_denied_tools,
            severity="error",
        ))

        # 工具白名单
        if self._allowed_tools:
            self.add_guardrail(GuardrailRule(
                name="allowed_tools",
                rule_type="pre_tool",
                check_fn=self._check_allowed_tools,
                severity="error",
            ))

        # 最大工具调用次数
        self.add_guardrail(GuardrailRule(
            name="max_tool_calls",
            rule_type="pre_tool",
            check_fn=self._check_max_tool_calls,
            severity="error",
        ))

    def _check_denied_tools(self, action: AgentAction,
                            context: ExecutionContext) -> Tuple[bool, str]:
        if self._denied_tools and action.tool_name in self._denied_tools:
            return False, f"Tool '{action.tool_name}' is in the denied list"
        return True, ""

    def _check_allowed_tools(self, action: AgentAction,
                             context: ExecutionContext) -> Tuple[bool, str]:
        if self._allowed_tools and action.tool_name not in self._allowed_tools:
            return False, f"Tool '{action.tool_name}' is not in the allowed list"
        return True, ""

    def _check_max_tool_calls(self, action: AgentAction,
                              context: ExecutionContext) -> Tuple[bool, str]:
        if self._tool_call_count >= self._max_tool_calls:
            return False, f"Exceeded max tool calls ({self._max_tool_calls})"
        return True, ""

    # ── Callback management ──────────────────────────────────────

    def register_callback(self, event: str, handler: Callable) -> None:
        if event in self._callbacks:
            self._callbacks[event].append(handler)

    def _fire_callbacks(self, event: str, *args: Any, **kwargs: Any) -> None:
        for handler in self._callbacks.get(event, []):
            try:
                handler(*args, **kwargs)
            except Exception as e:
                logger.warning(f"Callback '{event}' error: {e}")

    # ── HarnessEngine implementation ────────────────────────────

    async def pre_tool_check(self, action: AgentAction,
                             context: ExecutionContext) -> Tuple[bool, str]:
        """工具调用前检查：安全护栏校验。"""
        for rule in self._guardrails:
            if not rule.enabled:
                continue
            if rule.rule_type != "pre_tool":
                continue
            allowed, reason = rule.check_fn(action, context)
            if not allowed:
                self._metrics.blocked_calls += 1
                self._fire_callbacks("on_blocked", action, rule.name, reason)
                logger.warning(f"Guardrail '{rule.name}' blocked: {reason}")
                return False, f"[{rule.severity}] {rule.name}: {reason}"

        self._tool_call_count += 1
        return True, ""

    async def post_tool_check(self, action: AgentAction, result: ToolResult,
                              context: ExecutionContext) -> Tuple[bool, str]:
        """工具调用后检查：验证结果、错误处理。"""
        self._metrics.tool_calls += 1

        if not result.success:
            self._metrics.tool_errors += 1
            self._consecutive_errors += 1

            self._fire_callbacks("on_error", action, result)

            # 自动修复逻辑
            if self._auto_heal and self._consecutive_errors < self._max_errors:
                logger.info(f"Auto-heal: retrying after error ({self._consecutive_errors}/{self._max_errors})")
                return True, "auto_heal_retry"

            if self._consecutive_errors >= self._human_threshold:
                self._fire_callbacks("on_human_needed", action, result)
        else:
            self._consecutive_errors = 0

        return True, ""

    async def log_feedback(self, step: AgentLoopStep,
                           context: ExecutionContext) -> None:
        """记录步骤执行的反馈信息到指标中。"""
        metric = {
            "step_id": step.step_id,
            "thought": step.thought.thought[:100] if step.thought else "",
            "action": step.action.tool_name if step.action else "",
            "success": step.observation.result.success if step.observation else False,
            "duration_ms": step.duration_ms,
            "decision": step.decision.value,
            "retry_count": step.retry_count,
        }
        self._metrics.step_metrics.append(metric)
        self._metrics.total_duration_ms += step.duration_ms

    async def human_intervention_needed(self, reason: str,
                                        context: ExecutionContext) -> None:
        """请求人类介入。"""
        self._metrics.human_interventions += 1
        logger.warning(f"Human intervention needed: {reason}")
        self._fire_callbacks("on_human_needed", reason)
        # 在非交互模式下，记录需要人类介入但不阻塞
        return

    def get_metrics(self) -> Dict[str, Any]:
        """获取收集的指标。"""
        return {
            "tool_calls": self._metrics.tool_calls,
            "tool_errors": self._metrics.tool_errors,
            "blocked_calls": self._metrics.blocked_calls,
            "replan_requests": self._metrics.replan_requests,
            "human_interventions": self._metrics.human_interventions,
            "total_duration_ms": self._metrics.total_duration_ms,
            "step_count": len(self._metrics.step_metrics),
            "consecutive_errors": self._consecutive_errors,
        }

    def reset_metrics(self) -> None:
        """重置所有指标。"""
        self._metrics = HarnessMetric()
        self._consecutive_errors = 0
        self._tool_call_count = 0


# ── Safety Harness — strict mode ──────────────────────────────

class StrictHarnessEngine(DefaultHarnessEngine):
    """严格模式的 Harness 引擎。

    更严格的安全策略：
    - 只允许白名单中的工具
    - 更少的重试次数
    - 更早触发人类介入
    - 禁止所有危险/系统命令
    """

    def __init__(self):
        super().__init__(
            max_tool_calls_per_step=3,
            max_consecutive_errors=1,
            allowed_tools=["read_file", "write_file", "shell", "search", "list_dir"],
            denied_tools=[
                "rm", "del", "format", "shutdown", "reboot", "poweroff",
                "reset", "init", "drop", "truncate", "mv", "cp", "chmod",
                "chown", "kill", "pkill", "docker", "sudo", "su",
            ],
            human_intervention_threshold=1,
            auto_heal=False,
        )
