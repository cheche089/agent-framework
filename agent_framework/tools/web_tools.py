"""Web and Skill management tools for the Agent framework.

Provides:
- WebSearchTool: Search the web (auto-detects weather queries → uses wttr.in)
- WeatherTool: Query weather for any city
- HttpRequestTool: Make HTTP requests
- SearchSkillsTool: Search for installable skills
- InstallSkillTool: Install skills from URLs
- AutoInstallFlow: Complete flow: detect need → search → ask → install
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional, Tuple

from ..core.interfaces import BaseTool
from ..core.types import ExecutionContext, ToolResult
from ..web.search import web_search, weather_query, format_weather_display, http_request
from ..skills.installer import SkillInstaller
from ..skills.registry import SkillRegistry

# ── 预配置的 Skill 市场源 ─────────────────────────────────────

SKILL_MARKET_SOURCES = [
    "https://raw.githubusercontent.com/cheche089/openclaw-skills/main/index.json",
    "https://raw.githubusercontent.com/topics/agent-skills/main/index.json",
]


# ═══════════════════════════════════════════════════════════════
# 天气查询工具
# ═══════════════════════════════════════════════════════════════

class WeatherTool(BaseTool):
    """查询指定城市的实时天气和未来预报。"""

    name = "weather"
    description = "查询任意城市的实时天气和未来预报，返回温度、湿度、风速、逐时预报等详细信息。"
    parameters = {
        "type": "object",
        "properties": {
            "location": {
                "type": "string",
                "description": "城市名，如：北京、上海、衡水、New York、London",
            },
        },
        "required": ["location"],
    }

    async def execute(self, ctx: ExecutionContext, **kwargs: Any) -> ToolResult:
        location = kwargs.get("location", "")
        if not location:
            return ToolResult.fail("请指定城市名")

        try:
            data = await weather_query(location)
            formatted = format_weather_display(data)
            return ToolResult.ok(formatted, location=location, success=data.get("success", False))
        except Exception as e:
            return ToolResult.fail(f"天气查询失败: {e}")


# ═══════════════════════════════════════════════════════════════
# 联网搜索工具（自动识别天气查询）
# ═══════════════════════════════════════════════════════════════

class WebSearchTool(BaseTool):
    """搜索互联网获取信息。自动识别天气查询并返回结构化天气数据。"""

    name = "web_search"
    description = "搜索互联网获取实时信息、新闻、天气、数据等。输入城市名+天气可自动获取详细天气数据。"
    parameters = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "搜索关键词，如：'衡水今天天气'、'2024年奥运会'",
            },
            "num_results": {
                "type": "integer",
                "description": "返回结果数 (1-10)",
                "default": 5,
            },
        },
        "required": ["query"],
    }

    async def execute(self, ctx: ExecutionContext, **kwargs: Any) -> ToolResult:
        query = kwargs.get("query", "")
        num = min(kwargs.get("num_results", 5), 10)

        if not query:
            return ToolResult.fail("请输入搜索关键词")

        try:
            results = await web_search(query, num_results=num)

            # web_search already handles weather internally via wttr.in
            if results and results[0].get("_weather"):
                return ToolResult.ok(results[0]["snippet"], result_count=1, is_weather=True)

            if results and "error" in results[0]:
                return ToolResult.fail(f"搜索失败: {results[0]['error']}")

            output_lines = [f"搜索: {query}", ""]
            for i, r in enumerate(results, 1):
                title = r.get("title", "Untitled")
                url = r.get("url", "")
                snippet = r.get("snippet", "")
                output_lines.append(f"{i}. {title}")
                if url:
                    output_lines.append(f"   {url}")
                if snippet:
                    output_lines.append(f"   {snippet}")
                output_lines.append("")

            return ToolResult.ok("\n".join(output_lines), result_count=len(results))
        except Exception as e:
            return ToolResult.fail(f"搜索失败: {e}")


# ═══════════════════════════════════════════════════════════════
# HTTP 请求工具
# ═══════════════════════════════════════════════════════════════

class HttpRequestTool(BaseTool):
    """发起 HTTP 请求获取网页或 API 数据。"""

    name = "http_request"
    description = "发起 HTTP 请求获取网页内容或 API 数据。"
    parameters = {
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "请求的 URL"},
            "method": {
                "type": "string", "enum": ["GET", "POST"], "default": "GET",
            },
        },
        "required": ["url"],
    }

    async def execute(self, ctx: ExecutionContext, **kwargs: Any) -> ToolResult:
        url = kwargs.get("url", "")
        method = kwargs.get("method", "GET")

        if not url:
            return ToolResult.fail("请输入 URL")

        try:
            result = await http_request(url, method=method)
            if result.get("success"):
                is_github = result.get("_from_github", False)

                content = result.get("content", "")

                if is_github:
                    # GitHub raw 内容：提取标题和前面部分
                    lines = content.split("\n")
                    title = ""
                    for line in lines:
                        if line.startswith("# "):
                            title = line.strip("# ").strip()
                            break
                    excerpt = "\n".join(lines[:100])
                    return ToolResult.ok(
                        f"📦 GitHub 项目：{title or url}\n\n{excerpt[:5000]}",
                        url=url,
                        from_github=True,
                    )

                return ToolResult.ok(
                    content[:5000],
                    url=url,
                    status_code=result.get("status_code"),
                )
            else:
                return ToolResult.fail(f"请求失败: {result.get('error', 'unknown')}")
        except PermissionError as e:
            return ToolResult.fail(f"访问被拒绝: {e}")
        except Exception as e:
            return ToolResult.fail(f"请求出错: {e}")


# ═══════════════════════════════════════════════════════════════
# Skill 搜索工具 + 自动安装流程
# ═══════════════════════════════════════════════════════════════

class SearchSkillsTool(BaseTool):
    """在 Skill 市场中搜索可安装的 Skill。"""

    name = "search_skills"
    description = "在 Skill 市场中搜索可安装的 Skill。当用户需要当前系统没有的能力时使用此工具。"
    parameters = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "搜索关键词，如：weather、code_review、web_search"},
        },
        "required": ["query"],
    }

    def __init__(self, installer: Optional[SkillInstaller] = None):
        super().__init__()
        self._installer = installer or SkillInstaller()

    async def execute(self, ctx: ExecutionContext, **kwargs: Any) -> ToolResult:
        query = kwargs.get("query", "")
        if not query:
            return ToolResult.fail("请输入搜索关键词")

        results = await self._search_market(query)

        if not results:
            return ToolResult.ok(
                f"未找到与 '{query}' 相关的 Skill。\n"
                f"💡 提示：你可以访问 GitHub 搜索 openclaw-skills 仓库，或创建自己的 Skill。"
            )

        output = [f"找到 {len(results)} 个与 '{query}' 相关的 Skill：\n"]
        for i, s in enumerate(results, 1):
            src_icon = "📦" if s.get("source") == "market" else "🌐"
            output.append(f"{i}. {src_icon} {s['name']}")
            if s.get("description"):
                output.append(f"   {s['description'][:120]}")
            output.append(f"   安装地址: {s['url']}")
            output.append("")

        output.append("💡 如需安装，回复 install <编号> 即可自动下载安装")

        return ToolResult.ok(
            "\n".join(output),
            result_count=len(results),
            results=results,
            _requires_install_choice=True,
        )

    async def _search_market(self, query: str) -> List[Dict[str, str]]:
        results = []
        seen = set()

        # 1. 从 Skill 市场源获取
        for source_url in SKILL_MARKET_SOURCES:
            try:
                resp = await http_request(source_url)
                if resp.get("success"):
                    import json as _json
                    data = _json.loads(resp["content"])
                    skills = data if isinstance(data, list) else data.get("skills", [])
                    for s in skills:
                        name = s.get("name", "")
                        desc = s.get("description", "")
                        if name and (query.lower() in name.lower() or query.lower() in desc.lower()):
                            if name not in seen:
                                seen.add(name)
                                results.append({
                                    "name": name,
                                    "description": desc,
                                    "url": s.get("url", s.get("file", "")),
                                    "source": "market",
                                })
            except Exception:
                continue

        # 2. 联网搜索补充
        if len(results) < 5:
            try:
                web_results = await web_search(f"skill openclaw agent {query}", num_results=5)
                for r in web_results:
                    url = r.get("url", "")
                    if url and url not in seen and "error" not in r:
                        seen.add(url)
                        results.append({
                            "name": url.rstrip("/").split("/")[-1].replace(".md", "").replace("SKILL", query)[:40],
                            "description": r.get("snippet", "")[:120],
                            "url": url,
                            "source": "web",
                        })
            except Exception:
                pass

        return results


class InstallSkillTool(BaseTool):
    """从 URL 安装一个 Skill 到本地。"""

    name = "install_skill"
    description = "下载并安装一个 Skill（支持 URL 或 GitHub 地址）。安装后可立即使用。"
    parameters = {
        "type": "object",
        "properties": {
            "source": {"type": "string", "description": "Skill 文件的 URL 或 GitHub 地址"},
        },
        "required": ["source"],
    }

    def __init__(self, installer: Optional[SkillInstaller] = None, registry: Optional[SkillRegistry] = None):
        super().__init__()
        self._installer = installer or SkillInstaller()
        self._registry = registry

    async def execute(self, ctx: ExecutionContext, **kwargs: Any) -> ToolResult:
        source = kwargs.get("source", "")
        if not source:
            return ToolResult.fail("请提供 Skill 源的 URL")

        try:
            skill = await self._installer.install_from_url(source)
            if self._registry:
                self._registry.register(skill)

            return ToolResult.ok(
                f"✅ 已成功安装 Skill: {skill.name}\n"
                f"📝 说明: {skill.description}\n"
                f"📐 指令长度: {len(skill.instructions)} 字符\n"
                f"现在就可以使用这个 Skill 了！",
                skill_name=skill.name,
            )
        except Exception as e:
            return ToolResult.fail(f"❌ 安装失败: {e}")


class ListSkillsTool(BaseTool):
    """列出已安装的 Skill。"""

    name = "list_skills"
    description = "列出所有已安装的 Skill。"
    parameters = {"type": "object", "properties": {}}

    def __init__(self, installer: Optional[SkillInstaller] = None, registry: Optional[SkillRegistry] = None):
        super().__init__()
        self._installer = installer or SkillInstaller()
        self._registry = registry

    async def execute(self, ctx: ExecutionContext, **kwargs: Any) -> ToolResult:
        try:
            store_skills = self._installer.list_installed()
            registry_skills = self._registry.list() if self._registry else []

            seen = set()
            all_skills = []
            for skill in store_skills + registry_skills:
                if skill.name not in seen:
                    seen.add(skill.name)
                    all_skills.append(skill)

            if not all_skills:
                return ToolResult.ok(
                    "📭 暂无已安装的 Skill\n"
                    "使用 search_skills(query) 搜索可安装的 Skill。"
                )

            output = [f"已安装 {len(all_skills)} 个 Skill：", ""]
            for s in all_skills:
                output.append(f"  📦 {s.name}")
                if s.description:
                    output.append(f"     {s.description}")
                output.append("")

            return ToolResult.ok("\n".join(output), skill_count=len(all_skills))
        except Exception as e:
            return ToolResult.fail(f"列出 Skill 失败: {e}")


class RunSkillTool(BaseTool):
    """执行一个已安装的 Skill。"""

    name = "run_skill"
    description = "执行一个已安装的 Skill。需要先通过 list_skills 查看可用 Skill。"
    parameters = {
        "type": "object",
        "properties": {
            "skill_name": {"type": "string", "description": "Skill 名称"},
            "params": {
                "type": "object",
                "description": "传递给 Skill 的参数",
                "default": {},
            },
        },
        "required": ["skill_name"],
    }

    def __init__(self, installer: Optional[SkillInstaller] = None, registry: Optional[SkillRegistry] = None):
        super().__init__()
        self._installer = installer or SkillInstaller()
        self._registry = registry

    async def execute(self, ctx: ExecutionContext, **kwargs: Any) -> ToolResult:
        skill_name = kwargs.get("skill_name", "")
        params = kwargs.get("params", {})

        if not skill_name:
            return ToolResult.fail("请输入 Skill 名称")

        try:
            skill = None
            if self._registry:
                skill = self._registry.get(skill_name)
            if not skill:
                for s in self._installer.list_installed():
                    if s.name == skill_name:
                        skill = s
                        break
            if not skill:
                return ToolResult.fail(f"Skill '{skill_name}' 未安装。使用 search_skills 搜索并安装。")

            instructions = skill.instructions
            for k, v in params.items():
                instructions = instructions.replace("{{" + k + "}}", str(v))
                instructions = instructions.replace("${" + k + "}", str(v))

            return ToolResult.ok(
                f"执行 Skill: {skill_name}\n\n{instructions}",
                skill_name=skill_name,
            )
        except Exception as e:
            return ToolResult.fail(f"执行失败: {e}")


# ═══════════════════════════════════════════════════════════════
# 一键自动安装流程
# ═══════════════════════════════════════════════════════════════

class AutoInstallFlow:
    """完整的 Skill 自动安装流程。

    用法：
        当用户请求一个当前系统不具备的能力时：
        1. search_skills(query) — 搜索相关 Skill
        2. 展示给用户，询问是否安装
        3. 用户确认后，install_skill(url) — 自动下载安装
        4. 安装后立即使用
    """

    def __init__(self, installer: Optional[SkillInstaller] = None, registry: Optional[SkillRegistry] = None):
        self._installer = installer or SkillInstaller()
        self._registry = registry or SkillRegistry()
        self._last_search_results: List[Dict[str, str]] = []

    async def search(self, query: str) -> List[Dict[str, str]]:
        """搜索 Skill，并缓存结果。"""
        self._last_search_results = await self._search_all_sources(query)
        return self._last_search_results

    async def install_by_index(self, index: int) -> str:
        """按编号安装缓存的 Skill。"""
        if index < 0 or index >= len(self._last_search_results):
            return "❌ 编号无效"
        skill_info = self._last_search_results[index]
        return await self.install(skill_info["url"])

    async def install(self, url: str) -> str:
        """安装 Skill。"""
        try:
            skill = await self._installer.install_from_url(url)
            self._registry.register(skill)
            return (
                f"✅ 已成功安装 Skill: {skill.name}\n"
                f"📝 {skill.description}\n"
                f"现在你可以使用这个 Skill 了！"
            )
        except Exception as e:
            return f"❌ 安装失败: {e}"

    def format_results(self) -> str:
        """将搜索结果格式化为用户友好的消息。"""
        if not self._last_search_results:
            return "未找到相关 Skill"

        output = [f"找到 {len(self._last_search_results)} 个相关 Skill：\n"]
        for i, s in enumerate(self._last_search_results, 1):
            output.append(f"{i}. 📦 {s['name']}")
            if s.get("description"):
                output.append(f"   {s['description'][:120]}")
            output.append("")
        output.append("💡 想安装哪个？回复数字编号即可自动安装")

        return "\n".join(output)

    async def _search_all_sources(self, query: str) -> List[Dict[str, str]]:
        results = []
        seen = set()

        for source_url in SKILL_MARKET_SOURCES:
            try:
                resp = await http_request(source_url)
                if resp.get("success"):
                    import json as _json
                    data = _json.loads(resp["content"])
                    skills = data if isinstance(data, list) else data.get("skills", [])
                    for s in skills:
                        name = s.get("name", "")
                        desc = s.get("description", "")
                        if name and (query.lower() in name.lower() or query.lower() in desc.lower()):
                            if name not in seen:
                                seen.add(name)
                                results.append({
                                    "name": name,
                                    "description": desc,
                                    "url": s.get("url", s.get("file", "")),
                                })
            except Exception:
                continue

        if len(results) < 5:
            try:
                web_results = await web_search(f"SKILL.md agent {query}", num_results=5)
                for r in web_results:
                    url = r.get("url", "")
                    if url and url not in seen:
                        seen.add(url)
                        results.append({
                            "name": url.rstrip("/").split("/")[-1].replace(".md", "").replace("SKILL", query)[:40],
                            "description": r.get("snippet", "")[:120],
                            "url": url,
                        })
            except Exception:
                pass

        return results