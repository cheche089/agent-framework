from __future__ import annotations
import json
import os
from typing import Any, Dict, Optional
from ..core.interfaces import SkillLoader
from ..core.types import SkillSpec


class YamlSkillLoader(SkillLoader):
    """从 YAML 文件加载技能。

    TODO: 安装 PyYAML 后支持真正的 YAML 解析。
    """

    async def load(self, source: str) -> SkillSpec:
        """从文件路径加载技能定义。"""
        if not os.path.exists(source):
            raise FileNotFoundError(f"技能文件不存在: {source}")

        with open(source, "r", encoding="utf-8") as f:
            content = f.read()

        # 简单解析：假设格式为 key: value 每行
        lines = content.strip().split("\n")
        metadata: Dict[str, Any] = {}
        name = os.path.splitext(os.path.basename(source))[0]
        description = ""
        instructions = ""
        required_tools: list = []

        for line in lines:
            if line.startswith("#") or not line.strip():
                continue
            if ":" in line:
                key, _, value = line.partition(":")
                key = key.strip().lower()
                value = value.strip()
                if key == "name":
                    name = value
                elif key == "description":
                    description = value
                elif key == "requires":
                    required_tools = [t.strip() for t in value.split(",") if t.strip()]
                else:
                    metadata[key] = value
            else:
                instructions += line + "\n"

        return SkillSpec(
            name=name,
            description=description or f"从 {source} 加载的技能",
            instructions=instructions.strip() or content,
            required_tools=required_tools,
            metadata=metadata,
        )


class MarkdownSkillLoader(SkillLoader):
    """从 Markdown 文件加载技能。"""

    async def load(self, source: str) -> SkillSpec:
        if not os.path.exists(source):
            raise FileNotFoundError(f"技能文件不存在: {source}")

        with open(source, "r", encoding="utf-8") as f:
            content = f.read()

        name = os.path.splitext(os.path.basename(source))[0]
        lines = content.split("\n")
        description = ""
        instructions = content

        for i, line in enumerate(lines):
            if line.startswith("# ") and i < 5:
                name = line.strip("# ")
            elif line.startswith("## Description") and i + 1 < len(lines):
                description = lines[i + 1].strip()

        return SkillSpec(
            name=name,
            description=description,
            instructions=instructions,
            metadata={"source": source, "format": "markdown"},
        )
