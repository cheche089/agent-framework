"""OpenAgent Web UI - FastAPI Backend"""
import asyncio, json, os, sys, uuid
from datetime import datetime
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

app = FastAPI(title="OpenAgent Web UI")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

CONFIG_DIR = Path(__file__).parent.parent / ".openagent"
if not CONFIG_DIR.exists():
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
CONFIG_FILE = CONFIG_DIR / "config.json"
CONV_DIR = CONFIG_DIR / "conversations"
CONV_DIR.mkdir(exist_ok=True)

def load_config():
    if CONFIG_FILE.exists():
        return json.loads(CONFIG_FILE.read_text("utf-8"))
    return {"api_keys": {}, "provider": "openai", "model": "gpt-4o", "temperature": 0.3, "max_tokens": 4096, "system_prompt": ""}

def save_config(cfg):
    CONFIG_FILE.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), "utf-8")

def load_convs():
    res = []
    for f in sorted(CONV_DIR.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True):
        try: res.append(json.loads(f.read_text("utf-8")))
        except: pass
    return res[:50]

def save_conv(conv):
    (CONV_DIR / f"{conv['id']}.json").write_text(json.dumps(conv, indent=2, ensure_ascii=False), "utf-8")

def del_conv(cid):
    p = CONV_DIR / f"{cid}.json"
    if p.exists(): p.unlink()

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


# === Web Search ===
async def web_search(query: str, num_results: int = 5) -> list:
    """Search the web using DuckDuckGo HTML API (no API key needed)."""
    results = []
    try:
        url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            resp = await client.get(url, headers=headers)
            html = resp.text
            blocks = re.findall(r'<a rel="nofollow" class="result__a" href="(.*?)">.*?</a>.*?<a class="result__snippet" href=".*?">(.*?)</a>', html, re.DOTALL)
            for href, snippet in blocks[:num_results]:
                snippet_clean = re.sub(r'<.*?>', '', snippet).strip()
                results.append({'title': href[:60], 'url': href, 'snippet': snippet_clean})
    except Exception as e:
        results.append({'error': str(e)})
    return results


# === Curated Skills Definitions ===
CURATED_SKILLS = {
    "web_search": {
        "name": "\u8054\u7f51\u641c\u7d22",
        "description": "\u641c\u7d22\u4e92\u8054\u7f51\u83b7\u53d6\u5b9e\u65f6\u4fe1\u606f\uff0c\u652f\u6301\u641c\u7d22\u7f51\u9875\u3001\u65b0\u95fb\u7b49",
        "instructions": "\u4f60\u662f\u4e00\u4e2a\u641c\u7d22\u52a9\u624b\u3002\u7528\u6237\u4f1a\u7ed9\u4f60\u4e00\u4e2a\u95ee\u9898\uff0c\u8bf7\u4f7f\u7528 web_search \u5de5\u5177\u641c\u7d22\u4e92\u8054\u7f51\uff0c\u7136\u540e\u7ed9\u51fa\u5b8c\u6574\u7684\u56de\u7b54\u3002",
        "requires": ["web_search"],
        "category": "search",
    },
    "code_review": {
        "name": "\u4ee3\u7801\u5ba1\u67e5",
        "description": "\u5bf9 Python \u4ee3\u7801\u8fdb\u884c\u5ba1\u67e5\uff0c\u68c0\u67e5\u5e38\u89c1\u7684\u4ee3\u7801\u8d28\u91cf\u95ee\u9898",
        "instructions": "\u4f60\u662f\u4e00\u4e2a\u4ee3\u7801\u5ba1\u67e5\u52a9\u624b\u3002\u8bf7\u5ba1\u67e5\u7528\u6237\u63d0\u4f9b\u7684\u4ee3\u7801\uff0c\u68c0\u67e5\u7c7b\u578b\u6ce8\u91ca\u3001\u672a\u4f7f\u7528\u7684\u5bfc\u5165\u3001\u8d85\u957f\u51fd\u6570\u3001\u5f02\u5e38\u5904\u7406\u548c\u5b89\u5168\u6f0f\u6d1e\uff0c\u7ed9\u51fa\u6539\u8fdb\u5efa\u8bae\u3002",
        "requires": ["read_file"],
        "category": "development",
    },
    "summarize": {
        "name": "\u5185\u5bb9\u603b\u7ed3",
        "description": "\u5bf9\u6587\u672c\u3001\u7f51\u9875\u6216\u6587\u4ef6\u5185\u5bb9\u8fdb\u884c\u667a\u80fd\u603b\u7ed3\u548c\u63d0\u70bc",
        "instructions": "\u4f60\u662f\u4e00\u4e2a\u603b\u7ed3\u52a9\u624b\u3002\u8bf7\u5bf9\u7528\u6237\u63d0\u4f9b\u7684\u5185\u5bb9\u8fdb\u884c\u603b\u7ed3\uff1a\u63d0\u53d6\u5173\u952e\u4fe1\u606f\u3001\u4fdd\u7559\u91cd\u8981\u6570\u636e\u3001\u8f93\u51fa\u7ed3\u6784\u5316\u603b\u7ed3\u3001\u63d0\u70bc 3-5 \u4e2a\u8981\u70b9\u3002",
        "requires": [],
        "category": "productivity",
    },
    "file_organizer": {
        "name": "\u6587\u4ef6\u6574\u7406",
        "description": "\u81ea\u52a8\u5206\u7c7b\u3001\u547d\u540d\u548c\u7ec4\u7ec7\u6587\u4ef6\u5939\u4e2d\u7684\u6587\u4ef6",
        "instructions": "\u4f60\u662f\u4e00\u4e2a\u6587\u4ef6\u6574\u7406\u52a9\u624b\u3002\u5e2e\u52a9\u7528\u6237\u6574\u7406\u76ee\u6807\u76ee\u5f55\u4e0b\u7684\u6587\u4ef6\uff1a\u6309\u6269\u5c55\u540d\u5206\u7c7b\u3001\u521b\u5efa\u6587\u4ef6\u5939\u3001\u79fb\u52a8\u6587\u4ef6\u3002\u786e\u8ba4\u540e\u6267\u884c\u3002",
        "requires": ["shell"],
        "category": "productivity",
    },
}

SKILLS_DIR = CONFIG_DIR / "skills"
SKILLS_DIR.mkdir(exist_ok=True)

def get_installed_skills():
    skills = []
    for f in sorted(SKILLS_DIR.glob("*.json")):
        try:
            skills.append(json.loads(f.read_text("utf-8")))
        except:
            pass
    return skills

def save_installed_skill(skill: dict):
    (SKILLS_DIR / f"{skill['id']}.json").write_text(json.dumps(skill, indent=2, ensure_ascii=False), "utf-8")

def remove_installed_skill(skill_id: str):
    p = SKILLS_DIR / f"{skill_id}.json"
    if p.exists(): p.unlink()


@app.get("/api/providers")
def get_providers():
    return [{"id": pid, "name": p["name"], "models": p["models"], "env_key": p["env_key"]} for pid, p in PROVIDERS.items()]

@app.get("/api/config")
def get_config():
    return load_config()

@app.post("/api/config")
async def save_config_api(cfg: dict):
    save_config(cfg)
    return {"status": "ok"}

@app.get("/api/conversations")
def get_conversations():
    return load_convs()

@app.post("/api/conversations")
async def create_conversation(conv: dict):
    conv["id"] = conv.get("id", str(uuid.uuid4()))
    conv["created_at"] = conv.get("created_at", datetime.now().isoformat())
    conv["updated_at"] = datetime.now().isoformat()
    conv["messages"] = conv.get("messages", [])
    save_conv(conv)
    return conv

@app.delete("/api/conversations/{cid}")
def remove_conversation(cid: str):
    del_conv(cid)
    return {"status": "ok"}

@app.get("/api/conversations/{cid}")
def get_conversation(cid: str):
    p = CONV_DIR / f"{cid}.json"
    if not p.exists(): raise HTTPException(404, "Not found")
    return json.loads(p.read_text("utf-8"))

@app.websocket("/ws/chat")
async def ws_chat(ws: WebSocket):
    await ws.accept()
    try:
        data = await ws.receive_json()
        pid = data.get("provider_id", "openai")
        model = data.get("model", "gpt-4o")
        msgs = data.get("messages", [])
        temp = data.get("temperature", 0.3)
        mt = data.get("max_tokens", 4096)
        sp = data.get("system_prompt", "")
        cid = data.get("conversation_id", "")

        cfg = load_config()
        provider = PROVIDERS.get(pid)
        if not provider:
            await ws.send_json({"type": "error", "content": f"Unknown provider: {pid}"})
            await ws.close(); return

        api_key = cfg.get("api_keys", {}).get(pid) or os.getenv(provider["env_key"])
        if not api_key:
            await ws.send_json({"type": "error", "content": f"API key not configured for {provider['name']}"})
            await ws.close(); return

        full = ""
        chat_msgs = [{"role": "system", "content": sp}] + msgs if sp else msgs
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

        if provider["api_type"] == "anthropic":
            am = [m for m in chat_msgs if m["role"] != "system"]
            sc = next((m["content"] for m in chat_msgs if m["role"] == "system"), "")
            body = {"model": model, "messages": am, "max_tokens": mt, "temperature": temp, "stream": True}
            if sc: body["system"] = sc
            headers = {"x-api-key": api_key, "anthropic-version": "2023-06-01", "Content-Type": "application/json"}
            url = provider["base_url"].rstrip("/") + "/messages"
        else:
            body = {"model": model, "messages": chat_msgs, "temperature": temp, "max_tokens": mt, "stream": True}
            url = provider["base_url"].rstrip("/") + "/chat/completions"

        try:
            async with httpx.AsyncClient(timeout=300) as client:
                async with client.stream("POST", url, json=body, headers=headers) as resp:
                    if resp.status_code != 200:
                        err = (await resp.aread()).decode("utf-8", errors="replace")[:500]
                        await ws.send_json({"type": "error", "content": f"API error ({resp.status_code}): {err}"})
                        await ws.close(); return

                    if provider["api_type"] == "anthropic":
                        async for line in resp.aiter_lines():
                            if not line.startswith("data: "): continue
                            ds = line[6:].strip()
                            if ds == "[DONE]": continue
                            try:
                                ck = json.loads(ds)
                                if ck.get("type") == "content_block_delta":
                                    d = ck.get("delta", {}).get("text", "")
                                    if d: full += d; await ws.send_json({"type": "chunk", "content": d})
                            except: pass
                    else:
                        async for line in resp.aiter_lines():
                            if not line.startswith("data: "): continue
                            ds = line[6:].strip()
                            if ds == "[DONE]": continue
                            try:
                                ck = json.loads(ds)
                                d = ck.get("choices", [{}])[0].get("delta", {}).get("content", "")
                                if d: full += d; await ws.send_json({"type": "chunk", "content": d})
                            except: pass

            await ws.send_json({"type": "done", "content": full})
            if cid:
                cp = CONV_DIR / f"{cid}.json"
                if cp.exists():
                    conv = json.loads(cp.read_text("utf-8"))
                    if msgs: conv["messages"].append(msgs[-1])
                    conv["messages"].append({"role": "assistant", "content": full})
                    conv["updated_at"] = datetime.now().isoformat()
                    if not conv.get("title"): conv["title"] = full[:48].replace("\n", " ")
                    cp.write_text(json.dumps(conv, indent=2, ensure_ascii=False), "utf-8")
        except Exception as e:
            await ws.send_json({"type": "error", "content": str(e)})
        await ws.close()
    except WebSocketDisconnect: pass

static_dir = Path(__file__).parent / "static"
app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")



# === Tools & Skills API ===

@app.get("/api/tools")
def get_tools():
    """List available built-in tools."""
    return [
        {"id": "web_search", "name": "\u7f51\u9875\u641c\u7d22", "description": "\u641c\u7d22\u4e92\u8054\u7f51\u83b7\u53d6\u5b9e\u65f6\u4fe1\u606f", "category": "search"},
        {"id": "shell", "name": "Shell\u547d\u4ee4", "description": "\u6267\u884c\u7cfb\u7edf\u547d\u4ee4", "category": "system"},
        {"id": "read_file", "name": "\u8bfb\u53d6\u6587\u4ef6", "description": "\u8bfb\u53d6\u6587\u4ef6\u5185\u5bb9", "category": "file"},
        {"id": "write_file", "name": "\u5199\u5165\u6587\u4ef6", "description": "\u5199\u5165\u6587\u4ef6\u5185\u5bb9", "category": "file"},
    ]

@app.post("/api/web/search")
async def api_web_search(req: dict):
    query = req.get("query", "")
    num = min(req.get("num_results", 5), 10)
    results = await web_search(query, num)
    return {"results": results}

@app.get("/api/skills/curated")
def get_curated_skills():
    """List curated skills available for installation."""
    return [{"id": k, **v} for k, v in CURATED_SKILLS.items()]

@app.get("/api/skills")
def get_skills():
    """List installed skills."""
    return get_installed_skills()

@app.post("/api/skills/install")
async def install_skill(req: dict):
    """Install a skill from the curated list."""
    skill_id = req.get("skill_id", "")
    if skill_id not in CURATED_SKILLS:
        raise HTTPException(400, f"Unknown skill: {skill_id}")
    skill = CURATED_SKILLS[skill_id]
    installed = {
        "id": skill_id,
        "name": skill["name"],
        "description": skill["description"],
        "instructions": skill["instructions"],
        "requires": skill.get("requires", []),
        "category": skill.get("category", ""),
        "installed_at": datetime.now().isoformat(),
    }
    save_installed_skill(installed)
    return {"status": "ok", "skill": installed}

@app.post("/api/skills/uninstall/{skill_id}")
def uninstall_skill(skill_id: str):
    """Uninstall a skill."""
    remove_installed_skill(skill_id)
    return {"status": "ok"}

@app.post("/api/skills/execute")
async def execute_skill(req: dict):
    """Execute a skill - returns instructions for the LLM."""
    skill_id = req.get("skill_id", "")
    params = req.get("params", {})
    skills = get_installed_skills()
    skill = None
    for s in skills:
        if s["id"] == skill_id:
            skill = s
            break
    if not skill:
        raise HTTPException(404, f"Skill '{skill_id}' not installed")

    query = req.get("query", "")
    instructions = skill.get("instructions", "")

    # Replace placeholders
    for k, v in params.items():
        instructions = instructions.replace("{{" + k + "}}", str(v))
        instructions = instructions.replace("${" + k + "}", str(v))

    return {
        "type": "skill_execute",
        "skill_id": skill_id,
        "skill_name": skill["name"],
        "instructions": instructions,
        "user_query": query,
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8080, log_level="info")
