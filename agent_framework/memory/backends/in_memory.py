"""内存记忆后端 — 支持 TF-IDF 语义检索。"""

from __future__ import annotations
import math
import time
import re
from collections import Counter
from typing import Any, Dict, List, Optional
from ...core.interfaces import MemoryBackend
from ...core.types import MemoryItem


class InMemoryBackend(MemoryBackend):
    """基于字典的内存记忆后端，支持 TF-IDF 语义检索。

    TODO: 如需更好的语义检索效果，可接入 embedding 模型（如 sentence-transformers）。
    """

    def __init__(self):
        self._items: Dict[str, MemoryItem] = {}

    async def store(self, item: MemoryItem) -> None:
        if item.timestamp is None:
            item.timestamp = time.time()
        self._items[item.key] = item

    async def retrieve(
        self, query: str, limit: int = 10, filters: Optional[Dict[str, Any]] = None
    ) -> List[MemoryItem]:
        """TF-IDF 语义检索 + 可选过滤。

        1. 先把整个语料库分词，构建倒排索引
        2. 对查询也分词
        3. 用 TF-IDF 余弦相似度打分
        4. 应用过滤器
        5. 返回 top-k
        """
        if not self._items:
            return []

        query_trimmed = query.strip()
        # 空查询：返回所有（可按过滤），再按时间倒序
        if not query_trimmed:
            results = list(self._items.values())
            if filters:
                results = [r for r in results if self._matches_filters(r, filters)]
            results.sort(key=lambda x: x.timestamp or 0, reverse=True)
            return results[:limit]

        # 分词
        query_tokens = self._tokenize(query_trimmed)
        if not query_tokens:
            return []

        # 文档集合
        docs = list(self._items.values())

        # 构建倒排索引: token -> {doc_index -> count}
        inverted_index: Dict[str, Dict[int, int]] = {}
        doc_token_counts: List[Counter] = []
        for idx, doc in enumerate(docs):
            text = f"{doc.key} {doc.value}"
            tokens = self._tokenize(text)
            doc_token_counts.append(Counter(tokens))
            for token in set(tokens):
                if token not in inverted_index:
                    inverted_index[token] = {}
                inverted_index[token][idx] = doc_token_counts[idx][token]

        n_docs = len(docs)
        query_counter = Counter(query_tokens)

        # 计算 TF-IDF 余弦相似度
        scores: List[float] = [0.0] * n_docs

        # 查询向量的模长
        query_norm = math.sqrt(sum((1 + math.log10(c)) ** 2 for c in query_counter.values()))

        for token, qty in query_counter.items():
            df = len(inverted_index.get(token, {}))
            if df == 0:
                continue
            idf = math.log10(n_docs / df) + 1 if n_docs > df else 1.0
            q_tfidf = (1 + math.log10(qty)) * idf

            for doc_idx, count in inverted_index.get(token, {}).items():
                d_tfidf = (1 + math.log10(count)) * idf
                scores[doc_idx] += q_tfidf * d_tfidf

        # 归一化
        if query_norm > 0:
            for i in range(n_docs):
                doc_norm = math.sqrt(sum(
                    (1 + math.log10(doc_token_counts[i][t])) ** 2
                    for t in doc_token_counts[i]
                ))
                if doc_norm > 0:
                    scores[i] /= (query_norm * doc_norm)

        # 构建 (分数, 文档) 对，应用过滤，排序
        scored = []
        for i, doc in enumerate(docs):
            if filters and not self._matches_filters(doc, filters):
                continue
            scored.append((scores[i], i, doc))

        scored.sort(key=lambda x: (-x[0], -(x[2].timestamp or 0)))

        return [doc for _, _, doc in scored[:limit]]

    async def forget(self, key: str) -> bool:
        if key in self._items:
            del self._items[key]
            return True
        return False

    async def clear(self) -> None:
        self._items.clear()

    # ── 辅助方法 ──────────────────────────────────────────

    def _tokenize(self, text: str) -> List[str]:
        """将文本分词为小写 token 列表。"""
        text = str(text).lower()
        # 支持中文和英文混合分词
        # 英文按空格和标点分割，中文按单字（简单实现）
        tokens = []
        # 英文部分：按非字母数字分割
        for word in re.split(r"[^a-z0-9\u4e00-\u9fff]+", text):
            if not word:
                continue
            # 中文：拆成单字（n-gram 更准确但开销大）
            if re.match(r"^[\u4e00-\u9fff]+$", word):
                for char in word:
                    tokens.append(char)
                # 也保留整词（长度 > 1 的中文词）
                if len(word) > 1:
                    tokens.append(word)
            else:
                tokens.append(word)
        return [t for t in tokens if len(t) >= 1]

    def _matches_filters(self, item: MemoryItem, filters: Dict[str, Any]) -> bool:
        """检查记忆项是否匹配所有过滤条件。"""
        for key, value in filters.items():
            if key == "key_prefix":
                if not item.key.startswith(value):
                    return False
            elif key == "timestamp_after":
                if (item.timestamp or 0) < value:
                    return False
            elif key == "timestamp_before":
                if (item.timestamp or 0) > value:
                    return False
            elif key in item.metadata:
                if item.metadata[key] != value:
                    return False
            else:
                return False
        return True

