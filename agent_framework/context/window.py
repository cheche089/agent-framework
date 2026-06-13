from __future__ import annotations
from typing import List
from ..core.types import ContextLimit, Message, MessageRole


def estimate_tokens(text: str) -> int:
    """粗略估算 token 数量（约 4 字符/token）。"""
    return len(text) // 4 + 1


class SlidingWindowStrategy:
    """滑动窗口策略：保留最近的 N 轮对话。"""

    def __init__(self, limit: ContextLimit):
        self.limit = limit

    def apply(self, messages: List[Message]) -> List[Message]:
        """应用窗口策略，返回裁剪后的消息列表。"""
        total_tokens = sum(estimate_tokens(m.content) for m in messages)
        if total_tokens <= self.limit.max_tokens - self.limit.reserved_tokens:
            return messages

        # 保留 system 消息 + 最近的 user/assistant 消息
        system_msgs = [m for m in messages if m.role == MessageRole.SYSTEM]
        others = [m for m in messages if m.role != MessageRole.SYSTEM]

        # 从最旧开始丢弃
        pruned = list(others)
        while pruned:
            token_count = sum(estimate_tokens(m.content) for m in system_msgs) + \
                          sum(estimate_tokens(m.content) for m in pruned)
            if token_count <= self.limit.max_tokens - self.limit.reserved_tokens:
                break
            pruned.pop(0)

        return system_msgs + pruned


class ImportanceStrategy:
    """按重要性裁剪策略。

    TODO: 接入 LLM 评估每条消息的重要性。
    """
    pass
