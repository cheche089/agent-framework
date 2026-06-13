"""LLM 抽象层 — 多厂商支持 + 工厂函数。

支持的厂商：
- OpenAI (gpt-4o, gpt-4o-mini, ...)
- Anthropic (claude-3-5-sonnet, claude-3-opus, ...)
- Google (gemini-2.0-flash, gemini-2.0-pro, ...)
- DeepSeek (deepseek-chat, deepseek-reasoner)
- 阿里云通义千问 (qwen-max, qwen-plus, qwen-turbo)
- 智谱 GLM (glm-4-plus, glm-4-flash)
- Moonshot Kimi (moonshot-v1-8k, moonshot-v1-32k)
- 百度千帆 ERNIE (ernie-4.0, ernie-3.5)
- ByteDance 豆包 (doubao-pro, doubao-lite)
- 零一万物 (yi-lightning, yi-medium)
"""

from __future__ import annotations
import abc
import json
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


# ── 厂商配置 ──────────────────────────────────────────────

@dataclass
class ProviderConfig:
    name: str
    display_name: str
    base_url: str
    default_model: str
    models: List[str]
    api_key_env: str
    requires_project: bool = False       # Google 需要 project_id
    project_id_env: str = ""

    def to_llm_config(self) -> "LLMConfig":
        return LLMConfig(
            model=self.default_model,
            base_url=self.base_url,
            api_key=os.getenv(self.api_key_env),
        )


# 预定义厂商列表
PROVIDERS: Dict[str, ProviderConfig] = {
    "openai": ProviderConfig(
        name="openai", display_name="OpenAI",
        base_url="https://api.openai.com/v1",
        default_model="gpt-4o",
        models=["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "o1", "o3-mini"],
        api_key_env="OPENAI_API_KEY",
    ),
    "anthropic": ProviderConfig(
        name="anthropic", display_name="Anthropic Claude",
        base_url="https://api.anthropic.com/v1",
        default_model="claude-3-5-sonnet-20241022",
        models=["claude-3-5-sonnet-20241022", "claude-3-opus-20240229",
                "claude-3-haiku-20240307", "claude-3-7-sonnet-20250219"],
        api_key_env="ANTHROPIC_API_KEY",
    ),
    "google": ProviderConfig(
        name="google", display_name="Google Gemini",
        base_url="https://generativelanguage.googleapis.com/v1beta/openai",
        default_model="gemini-2.0-flash",
        models=["gemini-2.0-flash", "gemini-2.0-pro", "gemini-1.5-pro"],
        api_key_env="GOOGLE_API_KEY",
    ),
    "deepseek": ProviderConfig(
        name="deepseek", display_name="DeepSeek",
        base_url="https://api.deepseek.com/v1",
        default_model="deepseek-chat",
        models=["deepseek-chat", "deepseek-reasoner"],
        api_key_env="DEEPSEEK_API_KEY",
    ),
    "qwen": ProviderConfig(
        name="qwen", display_name="阿里云通义千问",
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        default_model="qwen-plus",
        models=["qwen-max", "qwen-plus", "qwen-turbo", "qwen-long"],
        api_key_env="QWEN_API_KEY",
    ),
    "zhipu": ProviderConfig(
        name="zhipu", display_name="智谱 GLM",
        base_url="https://open.bigmodel.cn/api/paas/v4",
        default_model="glm-4-flash",
        models=["glm-4-plus", "glm-4-flash", "glm-4-air"],
        api_key_env="ZHIPU_API_KEY",
    ),
    "kimi": ProviderConfig(
        name="kimi", display_name="Moonshot Kimi",
        base_url="https://api.moonshot.cn/v1",
        default_model="moonshot-v1-8k",
        models=["moonshot-v1-8k", "moonshot-v1-32k", "moonshot-v1-128k"],
        api_key_env="MOONSHOT_API_KEY",
    ),
    "ernie": ProviderConfig(
        name="ernie", display_name="百度千帆 ERNIE",
        base_url="https://aip.baidubce.com/rpc/2.0/ai/custom/v1/wenxinworkspace/chat",
        default_model="ernie-4.0",
        models=["ernie-4.0", "ernie-3.5", "ernie-speed"],
        api_key_env="ERNIE_API_KEY",
    ),
    "doubao": ProviderConfig(
        name="doubao", display_name="ByteDance 豆包",
        base_url="https://ark.cn-beijing.volces.com/api/v3",
        default_model="doubao-pro-32k",
        models=["doubao-pro-32k", "doubao-pro-128k", "doubao-lite-32k"],
        api_key_env="DOUBAO_API_KEY",
    ),
    "yi": ProviderConfig(
        name="yi", display_name="零一万物",
        base_url="https://api.lingyiwanwu.com/v1",
        default_model="yi-lightning",
        models=["yi-lightning", "yi-medium", "yi-large"],
        api_key_env="YI_API_KEY",
    ),
}


def list_providers() -> List[Dict[str, Any]]:
    """列出所有支持的厂商信息。"""
    return [
        {
            "id": p.name,
            "name": p.display_name,
            "default_model": p.default_model,
            "models": p.models,
            "env_key": p.api_key_env,
        }
        for p in PROVIDERS.values()
    ]


def get_provider(provider_id: str) -> ProviderConfig:
    """按 ID 获取厂商配置。"""
    provider = PROVIDERS.get(provider_id.lower())
    if provider is None:
        available = ", ".join(PROVIDERS.keys())
        raise ValueError(f"不支持厂商 '{provider_id}'。可选: {available}")
    return provider


# ── LLM 数据类型 ──────────────────────────────────────────

@dataclass
class LLMMessage:
    role: str  # "system" | "user" | "assistant"
    content: str


@dataclass
class LLMConfig:
    model: str = "gpt-4o"
    temperature: float = 0.3
    max_tokens: int = 4096
    api_key: Optional[str] = None
    base_url: Optional[str] = None

    @classmethod
    def from_provider(cls, provider_id: str, model: Optional[str] = None) -> "LLMConfig":
        """从厂商 ID 创建配置。"""
        provider = get_provider(provider_id)
        cfg = provider.to_llm_config()
        if model:
            cfg.model = model
        return cfg


# ── LLM 客户端接口 ────────────────────────────────────────

class LLMClient(abc.ABC):
    @abc.abstractmethod
    async def chat(self, messages: List[LLMMessage],
                   config: Optional[LLMConfig] = None) -> str:
        ...

    @abc.abstractmethod
    async def chat_structured(self, messages: List[LLMMessage],
                              response_schema: Dict[str, Any],
                              config: Optional[LLMConfig] = None) -> Dict[str, Any]:
        ...


def create_client(provider_id: str = "openai",
                  config: Optional[LLMConfig] = None) -> LLMClient:
    """工厂函数 — 按厂商创建 LLM 客户端。"""
    provider = get_provider(provider_id)
    cfg = config or provider.to_llm_config()
    return OpenAIClient(cfg)


# ── OpenAI 兼容 API 实现 ──────────────────────────────────

class OpenAIClient(LLMClient):
    """OpenAI 兼容 API 的 LLM 客户端。

    支持所有 OpenAI 兼容格式的 API（OpenAI, DeepSeek, Qwen, Zhipu, Kimi, Yi, 豆包等）。
    Anthropic 和百度 ERNIE 使用独立 API 格式。
    """

    def __init__(self, config: Optional[LLMConfig] = None):
        self.config = config or LLMConfig()
        if not self.config.api_key:
            self.config.api_key = os.getenv("OPENAI_API_KEY")
        self._provider_id = self._detect_provider()

    def _detect_provider(self) -> str:
        """根据 base_url 猜测厂商。"""
        url = (self.config.base_url or "").lower()
        if not url:
            return "openai"
        if "anthropic.com" in url:
            return "anthropic"
        if "googleapis.com" in url:
            return "google"
        if "deepseek.com" in url:
            return "deepseek"
        if "dashscope.aliyuncs.com" in url:
            return "qwen"
        if "bigmodel.cn" in url:
            return "zhipu"
        if "moonshot.cn" in url:
            return "kimi"
        if "baidubce.com" in url:
            return "ernie"
        if "volces.com" in url:
            return "doubao"
        if "lingyiwanwu.com" in url:
            return "yi"
        return "openai"

    async def chat(self, messages: List[LLMMessage],
                   config: Optional[LLMConfig] = None) -> str:
        cfg = config or self.config
        payload = {
            "model": cfg.model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "temperature": cfg.temperature,
            "max_tokens": cfg.max_tokens,
        }
        return await self._post(payload, cfg)

    async def chat_structured(self, messages: List[LLMMessage],
                              response_schema: Dict[str, Any],
                              config: Optional[LLMConfig] = None) -> Dict[str, Any]:
        cfg = config or self.config
        payload = {
            "model": cfg.model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "temperature": cfg.temperature,
            "max_tokens": cfg.max_tokens,
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": response_schema.get("name", "structured_output"),
                    "schema": response_schema,
                    "strict": True,
                },
            },
        }
        try:
            text = await self._post(payload, cfg)
            return json.loads(text)
        except RuntimeError as e:
            s = str(e)
            if "UNSUPPORTED_STRUCTURED" in s:
                prompt = "请输出 JSON 格式，按照以下 schema:\n```json\n" + str(response_schema) + "\n```\n\n" + (messages[-1].content if messages else "")
                chat_msgs = messages[:-1] + [LLMMessage(role="user", content=prompt)]
                text = await self.chat(chat_msgs, cfg)
                import re
                jm = re.search(r'```json\n(.+?)\n```', text, re.DOTALL)
                if jm:
                    return json.loads(jm.group(1))
                return json.loads(text)
            raise

    async def _post(self, payload: Dict[str, Any], cfg: LLMConfig) -> str:
        import httpx

        headers = {
            "Authorization": f"Bearer {cfg.api_key}",
            "Content-Type": "application/json",
        }
        base = (cfg.base_url or "https://api.openai.com/v1").rstrip("/")

        # Anthropic 使用不同的 API 路径
        if "anthropic.com" in base:
            url = f"{base}/messages"
            anthropic_messages = []
            for m in payload["messages"]:
                if m["role"] == "system":
                    # Anthropic 的 system 是顶层参数
                    continue
                anthropic_messages.append({"role": m["role"], "content": m["content"]})
            body = {
                "model": payload["model"],
                "messages": anthropic_messages,
                "max_tokens": payload.get("max_tokens", 4096),
                "temperature": payload.get("temperature", 0.3),
            }
            # 提取 system 消息
            for m in payload["messages"]:
                if m["role"] == "system":
                    body["system"] = m["content"]
                    break
            # Anthropic 使用 x-api-key 头
            headers = {
                "x-api-key": cfg.api_key,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
            }
            if "response_format" in payload:
                body["response_format"] = payload["response_format"]
        else:
            url = f"{base}/chat/completions"
            body = payload

        async with httpx.AsyncClient(timeout=180) as client:
            resp = await client.post(url, headers=headers, json=body)
            if resp.status_code != 200:
                if resp.status_code == 400 and "response_format" in payload:
                    raise RuntimeError("UNSUPPORTED_STRUCTURED")
                detail = resp.text[:500]
                raise RuntimeError(f"API 调用失败 ({resp.status_code}): {detail}")
            data = resp.json()

        # Anthropic 响应格式不同
        if "anthropic.com" in base:
            return data["content"][0]["text"]

        return data["choices"][0]["message"]["content"]
