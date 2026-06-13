"""上下文管理器 — 支持 LLM 摘要压缩和滑动窗口。"""

from __future__ import annotations
from typing import Any, Dict, List, Optional
from ..core.interfaces import ContextManager, TokenCounter
from ..core.types import ContextLimit, Message, MessageRole
from ..llm import LLMClient, LLMConfig, LLMMessage
from .window import SlidingWindowStrategy, estimate_tokens


COMPRESS_SYSTEM_PROMPT = """你是对话摘要助手。将下面的人类助手对话历史压缩为一段简洁的中文摘要，
保留所有关键信息：用户需求、已采取的行动、发现的结果、未解决的问题。
摘要不超过 300 字。注意只输出摘要本身，不要添加任何额外说明。"""


class SimpleTokenCounter(TokenCounter):
    def count(self, text: str) -> int:
        return estimate_tokens(text)


class DefaultContextManager(ContextManager):
    """默认上下文管理器，支持 LLM 摘要压缩。"""

    def __init__(
        self,
        limit: Optional[ContextLimit] = None,
        llm: Optional[LLMClient] = None,
        llm_config: Optional[LLMConfig] = None,
    ):
        self._limit = limit or ContextLimit()
        self._messages: List[Message] = []
        self._counter = SimpleTokenCounter()
        self._window = SlidingWindowStrategy(self._limit)
        self._llm = llm
        self._llm_config = llm_config or LLMConfig()
        self._compressed: List[str] = []  # 已压缩的摘要历史

    async def add_message(self, message: Message) -> None:
        self._messages.append(message)

    async def build_prompt(self) -> List[Message]:
        """构建 prompt：系统指令 + 历史摘要 + 当前窗口内容。"""
        if self._compressed:
            summary_text = "\n".join(self._compressed[-3:])  # 最近3次摘要
            summary_msg = Message(
                role=MessageRole.SYSTEM,
                content=f"[历史对话摘要]\n{summary_text}",
                metadata={"type": "compressed_history"},
            )
            return [summary_msg] + self._window.apply(self._messages)
        return self._window.apply(self._messages)

    async def compress(self) -> None:
        """使用 LLM 压缩上下文。

        策略：当 token 超过限制时，从最早的消息开始分批压缩。
        将压缩后的摘要作为一条带标记的 system 消息保留。
        """
        if self.token_count() <= self._limit.max_tokens * 0.8:
            return  # 还没到需要压缩的程度

        # 找到需要压缩的消息（保留最近的 8 轮 + 所有 system 消息）
        system_msgs = [m for m in self._messages if m.role == MessageRole.SYSTEM
                       and m.metadata.get("type") != "compressed_history"]
        non_system = [m for m in self._messages if m not in system_msgs]

        if len(non_system) <= 6:
            return  # 消息太少，不需要压缩

        # 选出要压缩的早期消息（保留最近 6 轮）
        to_compress = non_system[:-6]
        keep = non_system[-6:]

        # 生成压缩摘要
        summary = await self._summarize_messages(to_compress)
        if summary:
            self._compressed.append(summary)
            self._messages = system_msgs + keep
        else:
            # LLM 不可用则直接丢弃最早的 1/3
            drop_count = max(len(non_system) // 3, 3)
            self._messages = system_msgs + non_system[drop_count:]

    async def _summarize_messages(self, messages: List[Message]) -> Optional[str]:
        """使用 LLM 压缩一组消息为摘要。"""
        if not messages or not self._llm:
            return None

        lines = []
        for m in messages:
            prefix = f"[{m.role.value}]"
            content = m.content[:200] if len(m.content) > 200 else m.content
            lines.append(f"{prefix}: {content}")
        text = "\n".join(lines)

        # 太长则分段
        if len(text) > 8000:
            text = text[:8000] + "\n...(省略)"

        try:
            msgs = [
                LLMMessage(role="system", content=COMPRESS_SYSTEM_PROMPT),
                LLMMessage(role="user", content=f"请压缩以下对话历史：\n\n{text}"),
            ]
            return await self._llm.chat(msgs, self._llm_config)
        except Exception:
            return None

    def token_count(self) -> int:
        return sum(self._counter.count(m.content) for m in self._messages)
