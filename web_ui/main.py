"""OpenAgent Web UI — 全功能版
核心设计：所有输出都是人类可读的自然语言
"""

import asyncio, json, os, re, sys, uuid
from datetime import datetime
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

sys.path.insert(0, str(Path(__file__).parent.parent))

app = FastAPI(title="OpenAgent Web UI")
app.add_middleware(CORSMiddleware, allow_origins=["http://127.0.0.1:8080", "http://localhost:8080"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

CONFIG_DIR = Path(__file__).parent.parent / ".openagent"
CONFIG_DIR.mkdir(parents=True, exist_ok=True)
CONFIG_FILE = CONFIG_DIR / "config.json"
CONV_DIR = CONFIG_DIR / "conversations"
CONV_DIR.mkdir(exist_ok=True)

SKILLS_DIR = CONFIG_DIR / "skills"
SKILLS_DIR.mkdir(exist_ok=True)


def load_config():
    if CONFIG_FILE.exists():
        return json.loads(CONFIG_FILE.read_text("utf-8"))
    return {"api_keys": {}, "provider": "openai", "model": "gpt-4o", "temperature": 0.3, "max_tokens": 4096, "system_prompt": ""}

def save_config(cfg):
    CONFIG_FILE.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), "utf-8")

def load_conv(cid):
    p = CONV_DIR / f"{cid}.json"
    if p.exists():
        return json.loads(p.read_text("utf-8"))
    return {"id": cid, "messages": [], "full_history": []}

def save_conv(conv):
    (CONV_DIR / f"{conv['id']}.json").write_text(json.dumps(conv, indent=2, ensure_ascii=False), "utf-8")

def list_convs():
    res = []
    for f in sorted(CONV_DIR.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True):
        try:
            d = json.loads(f.read_text("utf-8"))
            res.append({"id": d["id"], "title": d.get("title",""), "created_at": d.get("created_at",""), "updated_at": d.get("updated_at",""), "messages": d.get("messages",[])})
        except: pass
    return res[:50]


PROVIDERS = {
    "openai": {"name": "OpenAI", "base_url": "https://api.openai.com/v1", "models": ["gpt-4o","gpt-4o-mini","gpt-4-turbo","o1","o3-mini"], "env_key": "OPENAI_API_KEY", "api_type": "openai"},
    "deepseek": {"name": "DeepSeek", "base_url": "https://api.deepseek.com/v1", "models": ["deepseek-chat","deepseek-reasoner"], "env_key": "DEEPSEEK_API_KEY", "api_type": "openai"},
    "qwen": {"name": "通义千问", "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1", "models": ["qwen-max","qwen-plus","qwen-turbo","qwen-long"], "env_key": "QWEN_API_KEY", "api_type": "openai"},
    "zhipu": {"name": "智谱 GLM", "base_url": "https://open.bigmodel.cn/api/paas/v4", "models": ["glm-4-plus","glm-4-flash","glm-4-air"], "env_key": "ZHIPU_API_KEY", "api_type": "openai"},
    "kimi": {"name": "Moonshot Kimi", "base_url": "https://api.moonshot.cn/v1", "models": ["moonshot-v1-8k","moonshot-v1-32k","moonshot-v1-128k"], "env_key": "MOONSHOT_API_KEY", "api_type": "openai"},
    "anthropic": {"name": "Anthropic Claude", "base_url": "https://api.anthropic.com/v1", "models": ["claude-3-5-sonnet-20241022","claude-3-opus-20240229","claude-3-haiku-20240307","claude-3-7-sonnet-20250219"], "env_key": "ANTHROPIC_API_KEY", "api_type": "anthropic"},
    "google": {"name": "Google Gemini", "base_url": "https://generativelanguage.googleapis.com/v1beta/openai", "models": ["gemini-2.0-flash","gemini-2.0-pro","gemini-1.5-pro"], "env_key": "GOOGLE_API_KEY", "api_type": "openai"},
    "doubao": {"name": "豆包", "base_url": "https://ark.cn-beijing.volces.com/api/v3", "models": ["doubao-pro-32k","doubao-pro-128k","doubao-lite-32k"], "env_key": "DOUBAO_API_KEY", "api_type": "openai"},
}


# ── 工具执行器：所有输出都是自然语言 ───────────────────────────

_tool_impls = {}

async def _get_web_search():
    if "web_search" not in _tool_impls:
        from agent_framework.web.search import web_search as _ws
        _tool_impls["web_search"] = _ws
    return _tool_impls["web_search"]

async def _get_skill_installer():
    if "installer" not in _tool_impls:
        from agent_framework.skills.installer import SkillInstaller
        _tool_impls["installer"] = SkillInstaller()
    return _tool_impls["installer"]

async def _get_skill_registry():
    if "registry" not in _tool_impls:
        from agent_framework.skills.registry import SkillRegistry
        _tool_impls["registry"] = SkillRegistry()
    return _tool_impls["registry"]

async def _get_http_client():
    if "http_client" not in _tool_impls:
        from agent_framework.web.search import WebClient
        _tool_impls["http_client"] = WebClient()
    return _tool_impls["http_client"]


# ── 工具定义 ───────────────────────────────────────────────────

TOOL_DEFS = [
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "搜索互联网获取实时信息，比如新闻、天气、数据、百科等。输入搜索关键词即可",
            "parameters": {"type": "object", "properties": {"query": {"type": "string", "description": "搜索关键词"}}, "required": ["query"]}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "fetch_url",
            "description": "获取网页内容或调用 API 接口",
            "parameters": {"type": "object", "properties": {"url": {"type": "string", "description": "网页地址"}}, "required": ["url"]}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_skills",
            "description": "在网络上搜索可下载安装的 Skill（功能扩展包）。当你遇到不会做、做不了的事情时，使用这个功能来搜索别人做好的 Skill。比如查天气、翻译、P图、写文档等",
            "parameters": {"type": "object", "properties": {"query": {"type": "string", "description": "想要的功能关键词，比如：天气、翻译、图片处理"}}, "required": ["query"]}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "install_skill",
            "description": "安装一个 Skill（功能扩展包）。安装后就可以使用它的能力了",
            "parameters": {"type": "object", "properties": {"source": {"type": "string", "description": "Skill 的下载地址"}}, "required": ["source"]}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_skills",
            "description": "查看已经安装了哪些 Skill",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "confirm_install",
            "description": "用户确认安装某个 Skill 后，使用之前 search_skills 的结果进行安装",
            "parameters": {"type": "object", "properties": {"skill_index": {"type": "integer", "description": "用户选择的 Skill 编号，从 1 开始"}}, "required": ["skill_index"]}
        }
    },
]

TOOL_NAMES = {t["function"]["name"] for t in TOOL_DEFS}

# 缓存上一次 search_skills 的结果
_last_skill_search_results = []


async def execute_tool(name, args_dict):
    """执行工具，返回自然语言文本。

    所有工具的输出都是人类可读的自然语言，不会返回任何 JSON 或代码。
    """
    global _last_skill_search_results

    try:
        # ── 1. 联网搜索 ──
        if name == "web_search":
            query = args_dict.get("query", "")
            if not query:
                return {"content": "请告诉我你想搜索什么"}

            from agent_framework.web.search import web_search, weather_query, format_weather_display

            # 检测天气查询
            weather_kw = ["天气", "weather", "气温", "温度", "°C", "°F", "下雨", "下雪", "台风"]
            is_weather = any(kw in query for kw in weather_kw)

            if is_weather:
                # 提取城市名
                for kw in ["天气", "weather", "今天", "明天", "后天", "气温", "温度", "怎么样", "如何", "怎样", "？", "?", "的"]:
                    query = query.replace(kw, "")
                query = re.sub(r"[？?，,。.！!\s]", "", query).strip()

                if query:
                    wdata = await weather_query(query)
                    text = format_weather_display(wdata)
                    return {"content": text, "_weather": True}

            # 普通搜索
            ws = await _get_web_search()
            results = await ws(query, num_results=5)

            if not results:
                return {"content": f"搜索「{query}」没有找到结果，可以换个关键词试试"}

            lines = [f"以下是搜索「{query}」找到的结果：\n"]
            for i, r in enumerate(results, 1):
                title = r.get("title", "无标题")
                url = r.get("url", "")
                snippet = r.get("snippet", "")
                lines.append(f"{i}. {title}")
                if snippet:
                    lines.append(f"   {snippet}")
                lines.append("")

            return {"content": "\n".join(lines)}

        # ── 2. 获取网页（含 GitHub 自动转 raw）──
        elif name == "fetch_url":
            url = args_dict.get("url", "")
            if not url:
                return {"content": "请提供要访问的网址"}

            client = await _get_http_client()
            result = await client.request(url)

            if not result.get("success"):
                return {"content": f"访问 {url} 失败了：{result.get('error', '未知错误')}"}

            content = result.get("content", "")

            # 判断是否为 GitHub raw 内容（Markdown）
            is_github = result.get("_from_github", False) or "raw.githubusercontent.com" in result.get("actual_url", "")

            if is_github:
                # 提取标题
                title_line = ""
                lines = content.split("\n")
                for line in lines:
                    if line.startswith("# "):
                        title_line = line.strip("# ").strip()
                        break
                first_part = "\n".join(lines[:80])
                return {"content": f"这是 {title_line or url} 项目的内容：\n\n{first_part[:4000]}"}

            return {"content": f"成功获取{url}的内容：\n\n{content[:3000]}"}

        # ── 3. 搜索 Skill ──
        elif name == "search_skills":
            query = args_dict.get("query", "")
            if not query:
                return {"content": "你想搜索什么样的 Skill？可以告诉我关键词，比如查天气、翻译文档、整理文件等"}

            from agent_framework.web.search import http_request, web_search

            results = []
            seen = set()
            _last_skill_search_results = []

            # 从 Skill 市场搜索
            market_urls = [
                "https://raw.githubusercontent.com/cheche089/openclaw-skills/main/index.json",
            ]

            for src_url in market_urls:
                try:
                    resp = await http_request(src_url)
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

            # 联网搜索补充
            if len(results) < 5:
                try:
                    web_results = await web_search(f"SKILL.md openclaw skill {query}", num_results=5)
                    for r in web_results:
                        url = r.get("url", "")
                        if url and url not in seen:
                            seen.add(url)
                            name = url.rstrip("/").split("/")[-1].replace(".md", "").replace("SKILL", query)[:40]
                            results.append({"name": name, "desc": r.get("snippet", "")[:100], "url": url})
                except:
                    pass

            if not results:
                return {"content": f"目前没找到和「{query}」相关的 Skill，你可以试试其他关键词，或者我直接帮你联网搜索相关信息？"}

            _last_skill_search_results = results

            lines = [f"我找到了 {len(results)} 个和「{query}」相关的功能扩展包：\n"]
            for i, s in enumerate(results, 1):
                lines.append(f"{i}️⃣  {s['name']}")
                if s.get("desc"):
                    lines.append(f"   简介：{s['desc'][:100]}")
                lines.append("")

            lines.append("你想安装哪一个？直接告诉我编号就行，比如「装第1个」。如果暂时不需要，也可以说「不用了」")

            return {"content": "\n".join(lines), "_has_skills": len(results) > 0}

        # ── 4. 确认安装 Skill ──
        elif name == "confirm_install":
            idx = args_dict.get("skill_index", 0) - 1
            if idx < 0 or idx >= len(_last_skill_search_results):
                return {"content": "编号好像不对，让我重新搜索一下吧？"}

            skill_info = _last_skill_search_results[idx]
            installer = await _get_skill_installer()

            try:
                skill = await installer.install_from_url(skill_info["url"])
                reg = await _get_skill_registry()
                reg.register(skill)
                return {"content": f"安装成功！「{skill['name']}」已经可以使用了，现在让我用它的能力来帮你解决问题吧。"}
            except Exception as e:
                return {"content": f"安装出了点问题：{e}。要不要试试换个来源？"}

        # ── 5. 安装 Skill（直接给 URL）──
        elif name == "install_skill":
            source = args_dict.get("source", "")
            if not source:
                return {"content": "请提供 Skill 的下载地址"}

            installer = await _get_skill_installer()
            try:
                skill = await installer.install_from_url(source)
                reg = await _get_skill_registry()
                reg.register(skill)
                return {"content": f"「{skill.name}」安装成功！{skill.description}"}
            except Exception as e:
                return {"content": f"安装失败了：{e}"}

        # ── 6. 查看已安装的 Skill ──
        elif name == "list_skills":
            reg = await _get_skill_registry()
            skills = reg.list()
            if not skills:
                return {"content": "目前还没有安装任何 Skill。你可以告诉我你想要什么功能，我帮你去找合适的 Skill 来安装。"}
            lines = ["已经安装了以下 Skill：\n"]
            for s in skills:
                lines.append(f"📦 {s.name}")
                if s.description:
                    lines.append(f"   简介：{s.description}")
                lines.append("")
            return {"content": "\n".join(lines)}

    except Exception as e:
        return {"content": f"出了点小问题：{e}，要不我们换个方式试试？"}

    return {"content": "我不太理解这个操作，你可以再详细说说你想要什么吗？"}


# ── 工具调用解析（兼容各类模型）────────────────────────────────

def extract_tool_calls(text):
    """从 LLM 回复中提取工具调用。"""
    calls = []

    # 原生 function calling 格式
    try:
        data = json.loads(text) if isinstance(text, str) else text
        if isinstance(data, dict):
            return [data]
    except:
        pass

    # XML 格式
    xml_pattern = r'<invoke\s+name="([^"]+)"\s*>.*?</invoke>'
    for match in re.finditer(xml_pattern, text, re.DOTALL):
        name = match.group(1)
        if name not in TOOL_NAMES:
            continue
        args_text = match.group(0)
        params = {}
        param_pattern = r'<parameter\s+name="([^"]+)"\s*>([^<]*)</parameter>'
        for pm in re.finditer(param_pattern, args_text, re.DOTALL):
            params[pm.group(1)] = pm.group(2).strip()
        if params:
            calls.append({"name": name, "arguments": params})

    # JSON 格式
    json_pattern = r'\`\`\`json\s*(\{.*?\})\s*\`\`\`'
    for match in re.finditer(json_pattern, text, re.DOTALL):
        try:
            data = json.loads(match.group(1))
            if isinstance(data, dict) and data.get("tool") in TOOL_NAMES:
                calls.append({"name": data["tool"], "arguments": data.get("params", {})})
        except:
            pass

    return calls


# ── 对话管理 ──────────────────────────────────────────────────

class ConversationStore:
    def __init__(self):
        self._convs = {}

    def get_or_create(self, cid, user_msgs=None):
        if cid in self._convs:
            return self._convs[cid]
        conv_file = CONV_DIR / f"{cid}.json"
        if conv_file.exists():
            try:
                data = json.loads(conv_file.read_text("utf-8"))
                history = data.get("full_history", [])
                self._convs[cid] = history
                return history
            except:
                pass
        history = []
        if user_msgs:
            for m in user_msgs:
                history.append({"role": m["role"], "content": m["content"]})
        self._convs[cid] = history
        return history

    def add_message(self, cid, msg):
        if cid not in self._convs:
            self._convs[cid] = []
        self._convs[cid].append(msg)

    def save(self, cid, display_messages=None, title=None):
        history = self._convs.get(cid, [])
        conv_file = CONV_DIR / f"{cid}.json"
        data = {"id": cid}
        if conv_file.exists():
            try:
                data = json.loads(conv_file.read_text("utf-8"))
            except:
                pass
        if display_messages:
            data["messages"] = display_messages
        data["full_history"] = history
        data["updated_at"] = datetime.now().isoformat()
        if title:
            data["title"] = title
        if "created_at" not in data:
            data["created_at"] = datetime.now().isoformat()
        try:
            conv_file.write_text(json.dumps(data, indent=2, ensure_ascii=False), "utf-8")
        except:
            pass

    def cleanup(self, cid):
        self._convs.pop(cid, None)

    def get_summary(self, cid, max_turns=6):
        history = self._convs.get(cid, [])
        if not history:
            return ""
        recent = history[-max_turns*2:] if len(history) > max_turns*2 else history
        lines = []
        for m in recent:
            role = "用户" if m["role"] == "user" else "助手"
            content = (m.get("content") or "")[:200]
            if content:
                lines.append(f"{role}：{content}")
        return "\n".join(lines)


_conv_store = ConversationStore()


# ── 系统提示词（中文，引导自然对话）──────────────────────────

SYSTEM_PROMPT = """当前日期：2026年6月14日，星期日。

你是 OpenAgent，一个智能 AI 助手。你的所有回复必须用中文，而且必须说人能听懂的话。

【你的能力】
1. **联网搜索**：任何你不知道的事、新闻、天气、数据，都可以用 web_search 搜索
2. **获取网页**：用 fetch_url 看网页内容
3. **安装功能包（Skill）**：当你遇到不会做的事情时，用 search_skills 去网上找别人做好的功能包，推荐给用户安装

【重要规则】
- 用户问你天气、新闻、实时信息 → 直接用 web_search 搜索
- 如果你不知道某件事怎么做，或者没有相应的能力 → 用 search_skills 搜索相关功能包
- 搜索到功能包后，用自然语言告诉用户找到了什么、能做什么用，问用户要不要安装
- 用户同意安装 → 用 confirm_install 安装（注意：用户说"好"、"行"、"装吧"、"第1个"就等于同意）
- 安装完成后，马上用装好的功能帮用户解决问题
- **所有回复必须是人话**，不要说"根据搜索结果"这种机器语言
- 不要输出 JSON、代码块、XML 标签——除非用户明确要求你写代码
- 如果用户说"不用了"、"不需要"、"算了"→ 跳过安装，直接回答

【回复风格示例】
✅ 正确（搜索后）：
"北京今天的天气是：晴天，温度 22~30°C，风不大，很适合出门！"

✅ 正确（推荐 Skill 时）：
"我搜到了一个查天气的功能包，可以帮你查看实时天气和未来几天的预报。要装一下试试吗？"

✅ 正确（安装后）：
"安装好了！现在我来帮你查一下衡水的天气……"

❌ 错误：
"根据 web_search 工具返回的结果，天气数据显示..."
"返回结果：{...json...}"
"代码如下：\n```\n..."
"""


# ── WebSocket 处理器（核心对话引擎）──────────────────────────

@app.websocket("/ws/agent")
async def ws_agent(ws: WebSocket):
    await ws.accept()
    try:
        data = await ws.receive_json()
        pid = data.get("provider_id", "openai")
        model = data.get("model", "gpt-4o")
        frontend_msgs = data.get("messages", [])
        temp = data.get("temperature", 0.3)
        mt = data.get("max_tokens", 4096)
        user_sp = data.get("system_prompt", "")
        cid = data.get("conversation_id", "")

        cfg = load_config()
        provider = PROVIDERS.get(pid)
        if not provider:
            await ws.send_json({"type": "error", "content": f"不支持的厂商：{pid}"})
            await ws.close(); return

        api_key = cfg.get("api_keys", {}).get(pid) or os.getenv(provider["env_key"])
        if not api_key:
            await ws.send_json({"type": "error", "content": f"请先配置 {provider['name']} 的 API 密钥"})
            await ws.close(); return

        # 系统提示词
        system_content = user_sp + "\n\n" + SYSTEM_PROMPT if user_sp else SYSTEM_PROMPT

        # 获取用户最新消息
        last_user_msg = ""
        for m in reversed(frontend_msgs):
            if m.get("role") == "user":
                last_user_msg = m["content"]
                break
        if not last_user_msg:
            await ws.send_json({"type": "error", "content": "没有收到消息"})
            await ws.close(); return

        # 加载对话历史
        history = _conv_store.get_or_create(cid, frontend_msgs[:-1])

        # 上下文增强：历史较长时加入摘要
        enhanced_msg = last_user_msg
        if len(history) > 6:
            summary = _conv_store.get_summary(cid, max_turns=4)
            if summary:
                enhanced_msg = f"【对话回顾】\n{summary}\n\n【现在的问题】\n{last_user_msg}"

        # ── 对话循环（最多 3 轮工具调用） ──
        max_rounds = 3
        round_num = 0
        while round_num < max_rounds:
            round_num += 1

            # 构建消息：system + 完整的 tool_call/tool_result 历史 + 当前用户输入
            chat_msgs = [{"role": "system", "content": system_content}]
            chat_msgs.extend(history)
            if round_num == 1:
                chat_msgs.append({"role": "user", "content": enhanced_msg})
            else:
                # 后续轮次：告诉 LLM 基于工具结果回复
                chat_msgs.append({"role": "user", "content": "基于上面的工具执行结果，用自然语言回答用户。如果是天气数据就直接告诉用户，如果是 Skill 搜索结果就问用户要不要安装"})

            headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
            base_url = provider["base_url"].rstrip("/")

            async with httpx.AsyncClient(timeout=300) as client:
                await ws.send_json({"type": "status", "content": "正在思考..."})

                probe_body = {
                    "model": model,
                    "messages": chat_msgs,
                    "temperature": temp,
                    "max_tokens": mt,
                    "tools": TOOL_DEFS,
                    "tool_choice": "auto",
                }

                resp = await client.post(f"{base_url}/chat/completions", json=probe_body, headers=headers)
                if resp.status_code != 200:
                    err = (await resp.aread()).decode("utf-8", errors="replace")[:500]
                    await ws.send_json({"type": "error", "content": f"API 出错了：{err}"})
                    await ws.close(); return

                resp_data = resp.json()
                choice = resp_data["choices"][0]
                msg = choice.get("message", {})
                content = msg.get("content", "") or ""
                tool_calls = msg.get("tool_calls", None)

                # ── 没有工具调用：直接返回LLM的回答 ──
                if not tool_calls:
                    if content:
                        chunk_size = max(1, len(content) // min(20, max(1, len(content))))
                        for i in range(0, len(content), chunk_size):
                            chunk = content[i:i+chunk_size]
                            await ws.send_json({"type": "chunk", "content": chunk})
                            await asyncio.sleep(0.005)
                    await ws.send_json({"type": "done", "content": content})
                    _conv_store.add_message(cid, {"role": "assistant", "content": content})

                    # 保存对话
                    display = []
                    for m in _conv_store.get_or_create(cid):
                        if m["role"] in ("user", "assistant"):
                            display.append({"role": m["role"], "content": m["content"]})
                    _conv_store.save(cid, display, title=content[:48])

                    await ws.close()
                    return

                # ── 有工具调用：执行工具 ──
                assistant_msg = {"role": "assistant", "content": content or None}
                assistant_msg["tool_calls"] = [
                    {"id": tc["id"], "type": "function", "function": tc["function"]}
                    for tc in tool_calls
                ]
                _conv_store.add_message(cid, assistant_msg)

                for tc in tool_calls:
                    fn_name = tc["function"]["name"]
                    try:
                        fn_args = json.loads(tc["function"]["arguments"])
                    except:
                        fn_args = {}

                    status_texts = {
                        "web_search": "正在搜索...",
                        "fetch_url": "正在获取网页...",
                        "search_skills": "正在搜索可用的功能包...",
                        "install_skill": "正在安装...",
                        "confirm_install": "正在安装...",
                        "list_skills": "正在查询...",
                    }
                    await ws.send_json({"type": "status", "content": status_texts.get(fn_name, "处理中...")})

                    result = await execute_tool(fn_name, fn_args)
                    result_text = result.get("content", "")

                    # 工具结果作为 tool 消息加入历史
                    _conv_store.add_message(cid, {
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "content": result_text,
                    })

        # 超过轮数限制
        await ws.send_json({"type": "error", "content": "处理步骤太多了，我们重新开始吧"})
        await ws.close()

    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await ws.send_json({"type": "error", "content": f"出了点问题：{str(e)[:200]}"})
            await ws.close()
        except:
            pass


# ── REST API ──────────────────────────────────────────────────

@app.get("/api/providers")
def get_providers():
    result = []
    for pid, p in PROVIDERS.items():
        env_val = os.getenv(p["env_key"])
        result.append({"id": pid, "name": p["name"], "models": p["models"], "env_key": p["env_key"], "has_env_key": bool(env_val)})
    return result

@app.get("/api/config")
def get_config():
    cfg = load_config()
    env_keys = {}
    for pid, p in PROVIDERS.items():
        env_val = os.getenv(p["env_key"])
        if env_val: env_keys[pid] = True
    cfg["_env_keys"] = env_keys
    return cfg

@app.post("/api/config")
async def save_config_api(cfg: dict):
    save_config(cfg)
    return {"status": "ok"}

@app.get("/api/conversations")
def get_conversations():
    return list_convs()

@app.post("/api/conversations")
async def create_conversation(conv: dict):
    conv["id"] = conv.get("id", str(uuid.uuid4()))
    conv["created_at"] = conv.get("created_at", datetime.now().isoformat())
    conv["updated_at"] = datetime.now().isoformat()
    conv["messages"] = conv.get("messages", [])
    conv["full_history"] = conv.get("full_history", [])
    save_conv(conv)
    return conv

@app.delete("/api/conversations/{cid}")
def remove_conversation(cid: str):
    p = CONV_DIR / f"{cid}.json"
    if p.exists(): p.unlink()
    _conv_store.cleanup(cid)
    return {"status": "ok"}

@app.get("/api/conversations/{cid}")
def get_conversation(cid: str):
    p = CONV_DIR / f"{cid}.json"
    if not p.exists(): raise HTTPException(404, "未找到对话")
    return json.loads(p.read_text("utf-8"))

@app.get("/api/skills")
def get_skills():
    reg = None
    if "registry" in _tool_impls:
        reg = _tool_impls["registry"]
    if not reg:
        return []
    skills = reg.list()
    return [{"id": s.name, "name": s.name, "description": s.description} for s in skills]


# ── 静态文件 ───────────────────────────────────────────────────

static_dir = Path(__file__).parent / "static"

@app.get("/app.js")
async def get_app_js():
    return FileResponse(os.path.join(str(static_dir), "app.js"), headers={"Cache-Control": "no-cache, no-store, must-revalidate"})

@app.get("/styles.css")
async def get_styles_css():
    return FileResponse(os.path.join(str(static_dir), "styles.css"), headers={"Cache-Control": "no-cache, no-store, must-revalidate"})

@app.get("/favicon.ico")
async def get_favicon():
    ico_path = os.path.join(str(static_dir), "favicon.ico")
    if os.path.exists(ico_path):
        return FileResponse(ico_path, headers={"Cache-Control": "no-cache"})
    from fastapi.responses import Response
    return Response(status_code=204)

app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8080, log_level="info")
