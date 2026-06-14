"""上下文增强模块 — 增强 Agent 对话中的上下文管理。

核心能力：
1. 历史对话摘要与注入
2. 记忆摘要自动注入
3. 长短上下文结合（Recency + Summary）
4. 用户画像感知
"""

from __future__ import annotations
import json
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ..core.types import ContextLimit, Message, MessageRole
from ..llm import LLMClient, LLMConfig, LLMMessage

logger = logging.getLogger(__name__)


@dataclass
class ConversationTurn:
    role: str
    content: str
    timestamp: float = 0.0
    token_count: int = 0


@dataclass
class ContextEnhancerConfig:
    """配置上下文增强策略。"""
    max_recent_turns: int = 6         # 保留最近 N 轮对话
    max_summary_turns: int = 20        # 超过 N 轮后开始摘要
    summary_prompt: str = "你是一个对话摘要助手。将以下对话内容压缩为一段简洁的摘要，保留关键决策、结论和用户需求。不超过 150 字。"
    enable_memory_injection: bool = True
    enable_user_profile: bool = True
    enable_recency_bias: bool = True   # 最近消息权重更高


class ContextEnhancer:
    """增强 Agent 上下文质量，解决"上下文太短"问题。

    策略：
    - 保留最近的 N 轮原始对话（Recency）
    - 对较早的对话生成摘要（Summary）
    - 将记忆系统的关键信息注入
    - 跟踪用户画像
    """

    def __init__(
        self,
        config: Optional[ContextEnhancerConfig] = None,
        llm: Optional[LLMClient] = None,
        llm_config: Optional[LLMConfig] = None,
    ):
        self._config = config or ContextEnhancerConfig()
        self._history: List[ConversationTurn] = []
        self._summaries: List[str] = []
        self._user_profile: Dict[str, Any] = {}
        self._llm = llm
        self._llm_config = llm_config or LLMConfig()

    def add_turn(self, role: str, content: str) -> None:
        """添加一轮对话。"""
        self._history.append(ConversationTurn(
            role=role,
            content=content,
            timestamp=time.time(),
        ))
        # 自动触发摘要
        if len(self._history) > self._config.max_summary_turns:
            self._auto_summarize()

    def _auto_summarize(self) -> None:
        """自动对旧对话生成摘要。"""
        if len(self._history) <= self._config.max_recent_turns:
            return

        # 取出要压缩的部分（保留最近 N 轮不动）
        to_summarize = self._history[
            :-(self._config.max_recent_turns)
        ]

        # 如果已有摘要，把旧摘要也纳入
        summary_text = "\n".join(
            f"[{t.role}] {t.content[:200]}"
            for t in to_summarize
        )

        if self._llm:
            summary = self._summarize_with_llm(summary_text)
        else:
            summary = self._fallback_summarize(to_summarize)

        if summary:
            self._summaries.append(f"[摘要 {len(self._summaries) + 1}] {summary}")

        # 移除已被压缩的历史
        self._history = self._history[-(self._config.max_recent_turns):]

    def _summarize_with_llm(self, text: str) -> str:
        """使用 LLM 生成摘要。"""
        try:
            messages = [
                LLMMessage(role="system", content=self._config.summary_prompt),
                LLMMessage(role="user", content=text[:4000]),
            ]
            return self._llm.chat(messages, self._llm_config)
        except Exception as e:
            logger.warning(f"LLM summary failed: {e}")
            return ""

    def _fallback_summarize(self, turns: List[ConversationTurn]) -> str:
        """回退摘要：提取关键信息。"""
        user_topics = {}
        decisions = []
        for t in turns:
            if t.role == "user":
                words = t.content.split()[:10]
                for w in words:
                    if len(w) > 2:
                        user_topics[w] = user_topics.get(w, 0) + 1
            elif t.role == "assistant" and any(kw in t.content for kw in ["完成", "结论", "结果", "总结"]):
                decisions.append(t.content[:100])

        parts = [f"共 {len(turns)} 轮对话"]
        top_topics = sorted(user_topics.items(), key=lambda x: -x[1])[:5]
        if top_topics:
            parts.append(f"关键话题: {', '.join(k for k, v in top_topics)}")
        if decisions:
            parts.append(f"关键结论: {decisions[-1]}")
        return "; ".join(parts)

    def build_enhanced_context(self, user_input: str) -> str:
        """构建增强后的上下文 prompt。

        返回格式：
        [系统指令]
        [近期对话摘要]
        [记忆信息]
        [用户画像]
        [最近 N 轮对话]
        [当前输入]
        """
        parts = []

        # 1. 历史摘要
        if self._summaries:
            summary_block = "\n".join(self._summaries[-3:])  # 最近 3 条摘要
            parts.append(f"[历史对话摘要]\n{summary_block}")

        # 2. 用户画像
        if self._config.enable_user_profile and self._user_profile:
            profile_str = json.dumps(self._user_profile, ensure_ascii=False)
            parts.append(f"[用户画像]\n{profile_str[:500]}")

        # 3. 最近对话（Recency）
        if self._history:
            recent = []
            for t in self._history[-self._config.max_recent_turns:]:
                label = "用户" if t.role == "user" else "AI"
                recent.append(f"{label}: {t.content[:300]}")
            parts.append("[最近对话]\n" + "\n".join(recent))

        # 4. 当前输入
        parts.append(f"[当前输入]\n{user_input}")

        return "\n\n".join(parts)

    def update_user_profile(self, key: str, value: Any) -> None:
        """更新用户画像信息。"""
        self._user_profile[key] = value

    def get_profile_summary(self) -> str:
        """获取用户画像摘要。"""
        if not self._user_profile:
            return ""
        items = [f"{k}: {v}" for k, v in self._user_profile.items()]
        return "用户画像: " + "; ".join(items)

    def clear_history(self) -> None:
        """清空对话历史（保留摘要和画像）。"""
        self._history = []

    def reset(self) -> None:
        """完全重置上下文。"""
        self._history = []
        self._summaries = []
        self._user_profile = {}
