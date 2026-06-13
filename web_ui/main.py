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

CONFIG_DIR = Path(os.environ.get("APPDATA", Path.home() / ".openagent")) / "OpenAgent"
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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8080, log_level="info")
