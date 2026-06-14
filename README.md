# OpenAgent

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104-009688)](https://fastapi.tiangolo.com/)

**OpenAgent** is a production-ready AI Agent framework with an intuitive Web UI and CLI, supporting 10+ LLM providers. It features built-in web search, a skill marketplace with auto-install, conversation management, and more — all in a single Python application.

---

## ✨ Features

| Feature | Description |
|---------|-------------|
| **🌐 Internet Search** | Built-in DuckDuckGo/Bing search + wttr.in weather API, no API key needed |
| **📦 Skill Marketplace** | Auto-search skills from GitHub, install with one click, use immediately |
| **🤖 Multi-LLM** | OpenAI, DeepSeek, Qwen, Zhipu GLM, Kimi, Claude, Gemini, Doubao |
| **💬 Streaming Chat** | WebSocket real-time streaming, typewriter effect |
| **💻 Web UI + CLI** | Desktop-grade dark theme web UI, plus full-featured CLI |
| **🧠 Context Enhancement** | Auto-summarization for long conversations, memory injection |
| **🔧 Tool System** | File read/write, shell execute, web search, HTTP requests |
| **📋 Conversation History** | Auto-save, browse, and restore |
| **🛡️ Security** | Built-in guardrails, sandbox, safe eval, injection protection |

---

## 🚀 Quick Start (3 minutes)

### Prerequisites

- Python 3.10+
- pip

### 1. Install

```bash
git clone https://github.com/cheche089/agent-framework.git
cd agent-framework

# Install dependencies
pip install httpx fastapi uvicorn websockets
```

### 2. Set API Key

Choose at least one LLM provider:

**Linux / macOS:**
```bash
# DeepSeek (recommended, best value)
export DEEPSEEK_API_KEY="sk-your-key"

# OpenAI
export OPENAI_API_KEY="sk-your-key"

# Alibaba Qwen (free tier available)
export QWEN_API_KEY="sk-your-key"

# Anthropic Claude
export ANTHROPIC_API_KEY="sk-your-key"
```

**Windows PowerShell:**
```powershell
$env:DEEPSEEK_API_KEY = "sk-your-key"
$env:OPENAI_API_KEY = "sk-your-key"
```

> 💡 You can also input API keys directly in the Web UI settings panel — they will be saved locally to `.openagent/config.json`.

### 3. Launch

**Web UI (recommended):**
```bash
cd agent-framework
python web_ui/main.py
# Open http://127.0.0.1:8080
```

**CLI mode:**
```bash
cd agent-framework
python examples/run_agent.py
```

**Windows users:** Double-click `start_webui.bat` to launch instantly.

---

## 🎯 How It Works

### Smart Tool Dispatch

When you ask a question, OpenAgent intelligently decides what to do:

```
You: What's the weather in Shanghai today?
      ↓
Agent: Uses wttr.in weather API → no API key needed
      ↓
Agent: "Shanghai today is 28°C, partly cloudy, humidity 65%..."

---
You: Review my Python code
      ↓
Agent: I don't have code review skills built-in
      ↓
Agent: Searches GitHub for "code_review" skill → finds it
      ↓
Agent: "I found a code review skill, want to install it?"
      ↓
You: Install it
      ↓
Agent: Downloads + registers instantly
      ↓
Agent: Reviews your code using the installed skill!
```

### Key Capabilities

| Action | What Agent Does |
|--------|----------------|
| **🌤️ Weather** | Auto-detects → uses wttr.in (free, no key) |
| **🔍 News / Search** | Uses DuckDuckGo + Bing fallback |
| **📄 GitHub links** | Auto-converts to raw content, CDN mirror fallback |
| **❓ Can't do X** | Searches skill marketplace → asks to install |
| **📦 Needs new skill** | Auto-downloads from GitHub, registers instantly |

---

## 🖥️ Web UI Guide

```
┌──────────────────────────────────────────────────┐
│  ┌─────────────┐  ┌────────────────────────────┐ │
│  │  provider ▼ │  │  model ▼                   │ │
│  └─────────────┘  └────────────────────────────┘ │
│  ┌─────────────┐  ┌────────────────────────────┐ │
│  │  Conversations │  │ Chat Area (streaming)      │ │
│  │  ├─ Weather     │  │                            │ │
│  │  ├─ Code Review │  │                            │ │
│  │  └─ New Chat    │  │                            │ │
│  │                 │  │                            │ │
│  │  [Settings]     │  └────────────────────────────┘ │
│  └─────────────┘     ┌────────────────────────────┐ │
│                      │ >>> Type your message...    │ │
│                      └────────────────────────────┘ │
└──────────────────────────────────────────────────┘
```

- **Left sidebar**: Conversation list, settings
- **Center**: Chat with real-time streaming responses
- **Top**: Provider/model selector

### Settings

Click the **Settings** button to configure:

| Setting | Description |
|---------|-------------|
| API Keys | Store provider credentials (local only, never uploaded) |
| Temperature | Response creativity (0.0–2.0) |
| Max Tokens | Maximum response length |
| System Prompt | Custom system prompt for your agent |

---

## 📁 Project Structure

```
agent-framework/
├── web_ui/                    # Web UI (FastAPI + Static files)
│   ├── main.py                # FastAPI backend + WebSocket handler
│   └── static/                # Frontend (HTML, CSS, JS)
├── agent_framework/           # Core Python library
│   ├── agent.py               # Agent orchestrator
│   ├── llm/                   # Multi-provider LLM client (10+ providers)
│   ├── tools/                 # Tools: file, shell, web search, HTTP
│   ├── skills/                # Skill loader, installer, registry
│   ├── web/                   # Web search engine (DDG + Bing + wttr.in)
│   ├── memory/                # Memory system with TF-IDF retrieval
│   ├── context/               # Context manager + enhancer
│   ├── workflow/              # Workflow engine (DAG-based)
│   ├── sandbox/               # Docker sandbox + security policies
│   ├── planner/               # Task planning & decomposition
│   └── harness/               # Safety guardrails & metrics
├── examples/                  # Usage examples
│   ├── run_agent.py           # Interactive CLI agent
│   └── run_webui.py           # Web UI launcher
├── .openagent/                # Local config (gitignored)
├── .gitignore
├── pyproject.toml
└── README.md
```

---

## 🤖 Supported LLM Providers

| Provider | Env Variable | Default Model |
|----------|-------------|---------------|
| OpenAI | `OPENAI_API_KEY` | gpt-4o |
| DeepSeek | `DEEPSEEK_API_KEY` | deepseek-chat |
| Qwen (Tongyi) | `QWEN_API_KEY` | qwen-plus |
| Zhipu GLM | `ZHIPU_API_KEY` | glm-4-flash |
| Moonshot Kimi | `MOONSHOT_API_KEY` | moonshot-v1-8k |
| Anthropic Claude | `ANTHROPIC_API_KEY` | claude-3-5-sonnet |
| Google Gemini | `GOOGLE_API_KEY` | gemini-2.0-flash |
| ByteDance Doubao | `DOUBAO_API_KEY` | doubao-pro-32k |

---

## 🔧 CLI Commands

```
>>> /help      - Show help
>>> /skills    - List installed skills
>>> /search <q> - Search skill marketplace
>>> install <n> - Install skill #n from last search
>>> exit        - Quit
```

---

## 🧪 Running Tests

```bash
pip install pytest pytest-asyncio
pytest tests/
```

---

## 🛡️ Security

- **No API keys in code** — loaded from environment variables or local config
- **Command injection protection** — `shlex` + `create_subprocess_exec` not shell
- **Path traversal protection** — normalized path validation
- **Safer eval** — restricted to basic comparisons, no builtins
- **Docker sandbox** — isolated execution with resource limits

---

## ❓ Troubleshooting

**Q: Web search returns no results?**
> DuckDuckGo may rate-limit some IPs. Try a different query or network.

**Q: Port 8080 is in use?**
> Change the port in `web_ui/main.py` (last line).

**Q: API returns 401?**
> Check your API key. You can also set it via the Web UI settings panel.

**Q: Module not found?**
> Run: `pip install httpx fastapi uvicorn websockets`

---

## 📜 License

MIT — see [LICENSE](LICENSE).

---

## 📬 Contact

Project Link: [https://github.com/cheche089/agent-framework](https://github.com/cheche089/agent-framework)
