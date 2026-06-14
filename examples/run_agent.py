"""OpenAgent 交互式 Agent CLI — 全功能版

功能：
- 🌐 联网搜索（自动识别天气→天气 API，GitHub 自动 raw 转换）
- 📦 Skill 自动发现 + 一键安装
- 🧠 上下文增强（历史对话摘要）
- ✅ 时间自动识别（当前日期已注入）
"""

import asyncio, os, sys, json, re
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from agent_framework.llm import LLMMessage, create_client, list_providers
from agent_framework.skills.installer import SkillInstaller
from agent_framework.skills.registry import SkillRegistry
from agent_framework.web.search import web_search, weather_query, format_weather_display, http_request

SYSTEM_PROMPT = """当前日期：2026年6月14日，星期日。

你是一个 AI 编程助手，拥有完整的互联网访问能力。

【可用工具（直接写在回复中使用）】
- web_search(query: 搜索词) — 搜索互联网获取实时信息、新闻、天气、百科等
- fetch_url(url: URL) — 获取网页内容（GitHub 链接自动识别）
- search_skills(query: 搜索词) — 搜索可安装的 Skill 功能包
- confirm_install(index: 编号) — 安装指定编号的 Skill
- list_skills() — 列出已安装的 Skill

【关键规则】
1. 用户问天气、气温 → 先用 web_search 搜索
2. 用户问新闻、实时信息、不知道的事 → 使用 web_search()
3. 用户需求当前不具备的能力 → 使用 search_skills() 搜索相关 Skill，用自然语言告诉用户找到了什么、有什么用，问要不要安装
4. 用户说"好"、"行"、"装吧"、"第1个" → 用 confirm_install() 安装
5. 安装完成后 → 立即用装好的 Skill 帮用户解决问题
6. 用中文回答，说人能听懂的话，不要输出 JSON 或代码
7. 每一轮只调用一个工具，等结果返回后再进行下一步"""


class InteractiveAgent:
    def __init__(self):
        self.llm = self._create_client()
        self.messages = []
        self.skill_installer = SkillInstaller()
        self.skill_registry = SkillRegistry()
        self._search_cache = []

    def _create_client(self):
        providers = list_providers()
        pid = os.getenv('LLM_PROVIDER', 'openai')
        for p in providers:
            if os.getenv(p.get('env_key', p['id'].upper() + '_API_KEY')):
                pid = p['id']
                break
        print(f'  [已连接: {pid}]')
        return create_client(pid)

    # ══════════════════════════════════════════════════════════════
    # 工具执行器
    # ══════════════════════════════════════════════════════════════

    async def run_tool(self, name: str, args: dict) -> str:
        try:
            # ── 1. 联网搜索（自动识别天气和 GitHub）──
            if name == "web_search":
                query = args.get("query", "")
                if not query:
                    return "你想搜什么？告诉我关键词就行"

                # 天气自动检测
                weather_kw = ["天气", "weather", "气温", "温度", "下雨", "下雪", "台风"]
                if any(kw in query for kw in weather_kw):
                    city = re.sub(r"[天气weather今天明天后天气温温度怎么样如何？?\s]", "", query).strip()
                    if city:
                        print(f"\n  🌤️  正在查询 {city} 天气...")
                        wd = await weather_query(city)
                        return format_weather_display(wd)

                print(f"\n  🔍 搜索: {query}")
                results = await web_search(query, num_results=5)
                if not results or results[0].get("error"):
                    return f"搜索「{query}」没有找到结果，可以换个关键词试试"

                lines = [f"以下是搜索「{query}」找到的结果：\n"]
                for i, r in enumerate(results, 1):
                    title = r.get("title", "无标题")
                    url = r.get("url", "")
                    snippet = r.get("snippet", "")
                    lines.append(f"{i}. {title}")
                    if url:
                        lines.append(f"   {url}")
                    if snippet:
                        lines.append(f"   {snippet}")
                    lines.append("")
                return "\n".join(lines)

            # ── 2. 获取网页（GitHub 自动转 raw）──
            elif name == "fetch_url":
                url = args.get("url", "")
                if not url:
                    return "请提供要访问的网址"
                print(f"\n  🌐 获取网页: {url}")
                result = await http_request(url)
                if not result.get("success"):
                    return f"访问失败：{result.get('error', '未知错误')}"

                content = result.get("content", "")
                is_github = result.get("_from_github", False) or "raw.githubusercontent.com" in result.get("actual_url", "")

                if is_github:
                    lines = content.split("\n")
                    title = next((l.strip("# ").strip() for l in lines if l.startswith("# ")), url.split("/")[-1])
                    excerpt = "\n".join(lines[:100])
                    return f"📦 项目：{title}\n\n{excerpt[:4000]}"

                return f"网页内容：\n\n{content[:3000]}"

            # ── 3. 搜索 Skill ──
            elif name == "search_skills":
                query = args.get("query", "通用")
                return await self._search_all_skills(query)

            # ── 4. 确认安装 Skill ──
            elif name == "confirm_install":
                idx = args.get("index", 1) - 1
                if idx < 0 or idx >= len(self._search_cache):
                    return "编号不太对，我重新搜一下？"
                info = self._search_cache[idx]
                print(f"\n  📥 正在安装: {info['name']}...")
                try:
                    skill = await self.skill_installer.install_from_url(info["url"])
                    self.skill_registry.register(skill)
                    for s in self.skill_installer.list_installed():
                        if s.name == skill.name:
                            self.skill_registry.register(s)
                            break
                    return f"✅ 安装成功！「{skill.name}」已经可以使用了。"
                except Exception as e:
                    return f"❌ 安装失败：{e}"

            # ── 5. 列出已安装 ──
            elif name == "list_skills":
                skills = self.skill_registry.list()
                if not skills:
                    return "📭 暂无已安装的 Skill。使用 /search 搜索或直接在对话中告诉我你想要什么功能。"
                lines = [f"📦 已安装 {len(skills)} 个 Skill：\n"]
                for s in skills:
                    lines.append(f"  - {s.name}：{s.description}")
                return "\n".join(lines)

        except Exception as e:
            return f"操作出了点小问题：{e}，可以换个方式试试"

        return "不太明白你的意思，能再说说吗？"

    async def _search_all_skills(self, query: str) -> str:
        results = []
        seen = set()
        self._search_cache = []

        # 从 Skill 市场搜索
        market_urls = [
            "https://raw.githubusercontent.com/cheche089/openclaw-skills/main/index.json",
        ]
        for url in market_urls:
            try:
                resp = await http_request(url)
                if resp.get("success"):
                    data = json.loads(resp["content"])
                    skills = data if isinstance(data, list) else data.get("skills", [])
                    for s in skills:
                        n, d = s.get("name", ""), s.get("description", "")
                        if n and n not in seen and (query.lower() in n.lower() or query.lower() in d.lower()):
                            seen.add(n)
                            results.append({"name": n, "desc": d, "url": s.get("url", s.get("file", ""))})
            except:
                pass

        # 联网补充
        if len(results) < 3:
            try:
                web_results = await web_search(f"SKILL.md openclaw {query}", num_results=5)
                for r in web_results:
                    url = r.get("url", "")
                    if url and url not in seen:
                        seen.add(url)
                        name = url.split("/")[-1].replace(".md", "").replace("SKILL", query)[:40]
                        results.append({"name": name, "desc": r.get("snippet", "")[:100], "url": url})
            except:
                pass

        if not results:
            return f"🔎 没找到和「{query}」相关的 Skill，可以换个关键词试试"

        self._search_cache = results
        lines = [f"🔎 找到 {len(results)} 个和「{query}」相关的 Skill：\n"]
        for i, s in enumerate(results, 1):
            lines.append(f"{i}. 📦 {s['name']}")
            if s.get("desc"):
                lines.append(f"   {s['desc'][:120]}")
            lines.append("")
        lines.append("💡 想安装哪个？回复 install <编号> 即可自动下载安装，如 install 1")
        return "\n".join(lines)

    # ══════════════════════════════════════════════════════════════
    # LLM 调度
    # ══════════════════════════════════════════════════════════════

    async def chat(self, user_input: str) -> str:
        if not self.messages:
            self.messages.append(LLMMessage(role="system", content=SYSTEM_PROMPT))

        # 上下文增强
        enhanced = self._build_context(user_input)
        self.messages.append(LLMMessage(role="user", content=enhanced))

        for _ in range(3):
            resp = await self.llm.chat(self.messages)
            self.messages.append(LLMMessage(role="assistant", content=resp))

            tool_calls = self._parse_tool_calls(resp)
            if not tool_calls:
                return resp

            for name, args in tool_calls:
                tool_output = await self.run_tool(name, args)
                self.messages.append(LLMMessage(role="user", content=tool_output))

        return self.messages[-1].content if self.messages else "处理超时了，重新试试？"

    def _parse_tool_calls(self, text: str):
        calls = []
        patterns = {
            "web_search": r'web_search\s*\(\s*["\']?(.+?)["\']?\s*\)',
            "fetch_url": r'fetch_url\s*\(\s*["\']?(.+?)["\']?\s*\)',
            "search_skills": r'search_skills\s*\(\s*["\']?(.+?)["\']?\s*\)',
            "confirm_install": r'confirm_install\s*\(\s*["\']?\s*(\d+)\s*["\']?\s*\)',
            "list_skills": r'list_skills\s*\(\s*\)',
        }
        for name, pattern in patterns.items():
            for match in re.finditer(pattern, text, re.IGNORECASE):
                if name == "list_skills":
                    calls.append((name, {}))
                elif name == "confirm_install":
                    calls.append((name, {"index": int(match.group(1))}))
                elif name == "fetch_url":
                    calls.append((name, {"url": match.group(1).strip()}))
                else:
                    calls.append((name, {"query": match.group(1).strip()}))
                break
        return calls

    def _build_context(self, user_input: str) -> str:
        parts = []
        if len(self.messages) > 4:
            recent = self.messages[-6:]
            summary = []
            for m in recent:
                role = "用户" if m.role == "user" else "助手"
                summary.append(f"{role}：{m.content[:150]}")
            parts.append("【之前的对话】\n" + "\n".join(summary))
        installed = self.skill_registry.list()
        if installed:
            skill_lines = [f"  已安装：{', '.join(s.name for s in installed)}"]
            parts.append("【我的能力】\n" + "\n".join(skill_lines))
        parts.append(f"【用户的问题】\n{user_input}")
        return "\n\n".join(parts)

    async def handle_install_choice(self, reply: str) -> str:
        try:
            idx = int(reply.strip()) - 1
            if 0 <= idx < len(self._search_cache):
                info = self._search_cache[idx]
                print(f"\n  📥 正在安装: {info['name']}...")
                skill = await self.skill_installer.install_from_url(info["url"])
                self.skill_registry.register(skill)
                for s in self.skill_installer.list_installed():
                    if s.name == skill.name:
                        self.skill_registry.register(s)
                        break
                return f"✅ 安装成功！「{skill.name}」已经可以使用了。"
            return "❌ 编号无效"
        except ValueError:
            return "❌ 请输入数字编号"

    # ══════════════════════════════════════════════════════════════
    # 主循环
    # ══════════════════════════════════════════════════════════════

    async def run(self):
        print("=" * 60)
        print("  🌐 OpenAgent — 智能 AI 助手")
        print("  ✅ 联网搜索  ✅ 天气查询  ✅ GitHub 项目查看")
        print("  ✅ Skill 自动发现 + 一键安装  ✅ 上下文增强")
        print("  输入 exit 退出 | /help 帮助 | /skills 查看 Skill")
        print("=" * 60)
        print()

        # 网络检查
        print("  📡 检查网络...", end=" ")
        try:
            test = await weather_query("北京")
            if test.get("success"):
                print("网络正常 ✅")
            else:
                print("网络受限 ⚠️")
        except:
            print("检查跳过")
        print()

        while True:
            raw = input(">>> ").strip()
            if not raw:
                continue
            cmd = raw.lower()
            if cmd in ("exit", "quit", "q"):
                print("再见！")
                break
            if cmd == "/help":
                print("  /help        显示帮助")
                print("  /skills      查看已安装的 Skill")
                print("  /search <关键词>  搜索 Skill 市场")
                print("  install <编号>   安装搜索结果中的 Skill")
                print("  也可以直接在对话中说需求，我会自动处理")
                continue
            if cmd == "/skills":
                skills = self.skill_registry.list()
                if not skills:
                    print("  📭 暂无已安装的 Skill（使用 /search 搜索）")
                else:
                    print(f"  📦 已安装 {len(skills)} 个 Skill：")
                    for s in skills:
                        print(f"    - {s.name}：{s.description}")
                continue
            if cmd.startswith("/search "):
                query = raw[8:].strip()
                print(f"\n  🔎 搜索 Skill 市场: {query}...")
                result = await self._search_all_skills(query)
                print(f"\n{result}")
                continue
            if cmd == "/search":
                print("  用法: /search <关键词>")
                continue
            if cmd.startswith("install "):
                reply = raw[8:].strip()
                result = await self.handle_install_choice(reply)
                print(f"\n{result}")
                continue

            # 核心对话
            print()
            response = await self.chat(raw)
            print(response)
            print()

            # 如果 LLM 建议安装 Skill，等待用户选择
            if "想安装" in response and "编号" in response:
                choice = input(">>> ").strip()
                if choice.lower() not in ("no", "n", "不", "算了", "跳过"):
                    result = await self.handle_install_choice(choice)
                    print(f"\n{result}")


if __name__ == "__main__":
    agent = InteractiveAgent()
    asyncio.run(agent.run())
