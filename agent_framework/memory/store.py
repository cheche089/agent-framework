"""记忆管理器 — 支持 LLM 摘要压缩。"""

from __future__ import annotations
from typing import Any, Dict, List, Optional
from ..core.interfaces import MemoryBackend, MemoryStore
from ..core.types import MemoryItem
from ..llm import LLMClient, LLMConfig, LLMMessage
from .backends import InMemoryBackend


SUMMARY_SYSTEM_PROMPT = """你是一个记忆摘要助手。下面是一组记忆条目，请生成一段简洁的摘要，
提取关键信息，包括：主要主题、重要的事实/数据、关键的时间点。
摘要应当保留具体数值和名称，不超过 200 字。"""


class DefaultMemoryStore(MemoryStore):
    """默认记忆管理器，支持 LLM 摘要压缩。"""

    def __init__(
        self,
        backend: Optional[MemoryBackend] = None,
        llm: Optional[LLMClient] = None,
        llm_config: Optional[LLMConfig] = None,
    ):
        self._backend = backend or InMemoryBackend()
        self._llm = llm
        self._llm_config = llm_config or LLMConfig()

    async def remember(
        self, key: str, value: Any, metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        item = MemoryItem(key=key, value=value, metadata=metadata or {})
        await self._backend.store(item)

    async def recall(self, query: str, limit: int = 10) -> List[MemoryItem]:
        return await self._backend.retrieve(query, limit=limit)

    async def forget(self, key: str) -> bool:
        return await self._backend.forget(key)

    async def summarize(self) -> str:
        """使用 LLM 压缩记忆为自然语言摘要。

        获取所有记忆条目，提交给 LLM 生成摘要。
        如果 LLM 不可用，回退到简单的统计摘要。
        """
        items = await self._backend.retrieve("", limit=1000)
        if not items:
            return "暂无记忆"

        if self._llm is None:
            return self._fallback_summarize(items)

        # 构建记忆文本
        lines = []
        for i, item in enumerate(items[:100], 1):
            meta_str = ""
            if item.metadata:
                meta_str = f" [元数据: {item.metadata}]"
            lines.append(f"{i}. key={item.key}, value={item.value}{meta_str}")

        memory_text = "\n".join(lines)

        # 如果记忆太多，分批处理
        if len(lines) > 50:
            return await self._batch_summarize(items)

        messages = [
            LLMMessage(role="system", content=SUMMARY_SYSTEM_PROMPT),
            LLMMessage(role="user", content=f"请为以下记忆条目生成摘要：\n\n{memory_text}"),
        ]

        try:
            summary = await self._llm.chat(messages, self._llm_config)
            return f"[LLM 摘要] {summary.strip()}"
        except Exception as e:
            return self._fallback_summarize(items, str(e))

    async def _batch_summarize(self, items: List[MemoryItem]) -> str:
        """分批处理大量记忆，然后合并摘要。"""
        batch_size = 30
        summaries = []
        for i in range(0, len(items), batch_size):
            batch = items[i:i + batch_size]
            lines = [f"{j+1}. key={item.key}, value={item.value}" for j, item in enumerate(batch)]
            batch_text = "\n".join(lines)
            try:
                msg = [
                    LLMMessage(role="system", content=SUMMARY_SYSTEM_PROMPT),
                    LLMMessage(role="user", content=f"请为以下记忆条目生成摘要：\n\n{batch_text}"),
                ]
                s = await self._llm.chat(msg, self._llm_config)
                summaries.append(s.strip())
            except Exception:
                summaries.append(f"批次 {i//batch_size + 1}: {len(batch)} 条记录")
        return f"[LLM 批处理摘要]\n" + "\n---\n".join(summaries[:5])

    def _fallback_summarize(self, items: List[MemoryItem], error: str = "") -> str:
        """LLM 不可用时的回退摘要。"""
        tags: Dict[str, int] = {}
        for item in items:
            if isinstance(item.key, str):
                parts = item.key.split("_")
                tag = parts[0] if len(parts) > 1 else item.key
                tags[tag] = tags.get(tag, 0) + 1

        tag_summary = ", ".join(f"{k}({v}条)" for k, v in sorted(tags.items(), key=lambda x: -x[1])[:10])
        parts = [f"共 {len(items)} 条记忆"]
        if tag_summary:
            parts.append(f"按标签: {tag_summary}")
        if error:
            parts.append(f"[LLM 摘要失败: {error[:60]}]")
        return "；".join(parts)
