# OpenAgent

![Python](https://img.shields.io/badge/python-3.10+-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![FastAPI](https://img.shields.io/badge/FastAPI-0.104-009688)

**OpenAgent** is a modular AI Agent framework with an intuitive Web UI, supporting 10+ LLM providers. It features built-in tools, a skill management system, web search, and a desktop-grade user interface — all in a single Python application.

---

## Features

| Feature | Description |
|---------|-------------|
| **Multi-Provider** | OpenAI, DeepSeek, Qwen, Zhipu GLM, Moonshot Kimi, Anthropic Claude, Google Gemini, ByteDance Doubao |
| **Streaming Chat** | Real-time streaming responses via WebSocket |
| **Web Search** | Built-in DuckDuckGo search, no API key required |
| **Skill System** | Curated skills marketplace — install, uninstall, and execute skills |
| **Conversation Management** | Save, browse, and restore chat history |
| **Tools & Agents** | File read/write, shell execution, web search |
| **Dark Theme UI** | Codex-like desktop interface |
| **Docker Sandbox** | Isolated command execution via Docker containers |
| **Workflow Engine** | Sequence, condition, loop, and parallel workflows |
| **Memory System** | TF-IDF semantic retrieval + LLM-based summarization |

---

## Quick Start (3 minutes)

### 1. Prerequisites

- Python 3.10+
- pip

### 2. Install

```bash
git clone https://github.com/your-username/your-repo.git
cd your-repo

# Install dependencies
pip install httpx fastapi uvicorn websockets
```

### 3. Set API Key

Choose at least one provider:

```bash
# OpenAI
export OPENAI_API_KEY="sk-xxx"

# DeepSeek
export DEEPSEEK_API_KEY="sk-xxx"

# Qwen (Tongyi Qianwen)
export QWEN_API_KEY="sk-xxx"

# Anthropic Claude
export ANTHROPIC_API_KEY="sk-xxx"
```

**Windows PowerShell:**
```powershell
$env:OPENAI_API_KEY = "sk-xxx"
$env:DEEPSEEK_API_KEY = "sk-xxx"
```

### 4. Start Web UI

```bash
cd your-repo
python web_ui/main.py
```

Open **http://127.0.0.1:8080** in your browser.

---

## Screenshots

![OpenAgent Web UI](docs/screenshot.png)

*Coming soon. The UI features a dark theme with a sidebar for conversations, a chat area with streaming responses, and a settings panel for API key configuration.*

---

## Usage Guide

### Chat Interface

1. Select a **provider** (e.g., OpenAI, DeepSeek) from the dropdown.
2. Select a **model** (e.g., gpt-4o, deepseek-chat).
3. Type your message in the input box and press **Enter**.
4. Responses stream in real-time.

### Tools & Skills Panel

Click **Tools/Skills** in the sidebar:

- **Tools tab**: View built-in tools and use the **web search** bar.
- **Skills tab**: View installed skills.
- **Install tab**: Browse curated skills and click **Install** to add them.

To use a skill in chat, describe your task — the LLM will automatically invoke the relevant tools.

### Settings

Click **Settings** in the sidebar to configure:

| Setting | Description |
|---------|-------------|
| API Keys | Store provider API keys (saved locally, never uploaded) |
| Temperature | Response randomness (0.0 - 2.0) |
| Max Tokens | Maximum response length |
| System Prompt | Custom system prompt for the LLM |

### CLI Mode

For command-line interaction:

```bash
python examples/run_agent.py
```

For a full feature demo:

```bash
python examples/basic_agent.py
```

---

## Supported Providers

| Provider | Env Variable | Default Model |
|----------|-------------|---------------|
| OpenAI | `OPENAI_API_KEY` | gpt-4o |
| DeepSeek | `DEEPSEEK_API_KEY` | deepseek-chat |
| Qwen (Tongyi) | `QWEN_API_KEY` | qwen-plus |
| Zhipu GLM | `ZHIPU_API_KEY` | glm-4-flash |
| Moonshot Kimi | `MOONSHOT_API_KEY` | moonshot-v1-8k |
| Anthropic Claude | `ANTHROPIC_API_KEY` | claude-3-5-sonnet |
| Google Gemini | `GOOGLE_API_KEY` | gemini-2.0-flash |
| Doubao | `DOUBAO_API_KEY` | doubao-pro-32k |

---

## Project Structure

```
agent-framework/
├── web_ui/                    # Web UI (FastAPI + Static files)
│   ├── main.py                # Backend server
│   └── static/                # Frontend assets
│       ├── index.html         # Main page
│       ├── styles.css         # Dark theme styles
│       └── app.js             # UI logic
├── agent_framework/           # Core Python library
│   ├── agent.py               # Agent orchestrator
│   ├── config.py              # Configuration
│   ├── core/                  # Base interfaces & types
│   ├── llm/                   # Multi-provider LLM client
│   ├── tools/                 # Built-in tools (file, shell)
│   ├── memory/                # Memory & retrieval
│   ├── planner/               # Task planning & decomposition
│   ├── workflow/              # Workflow engine
│   ├── sandbox/               # Docker sandbox & security
│   └── skills/                # Skill loader & manager
├── examples/                  # Usage examples
│   ├── run_agent.py           # Interactive CLI agent
│   ├── run_webui.py           # Web UI launcher
│   └── basic_agent.py         # Full feature demo
├── tests/                     # Test suite
├── docker/                    # Docker sandbox image
└── pyproject.toml             # Python package config
```

---

## Troubleshooting

**Q: Port 8080 is already in use.**
```bash
# Use a different port
python web_ui/main.py  # Edit the port in main.py or kill the existing process
```

**Q: API returns 401 Unauthorized.**
Check that your API key is correctly set. You can also configure keys via the **Settings** panel in the UI.

**Q: Web search returns no results.**
DuckDuckGo may block requests from certain IPs. Try a different query or run the app in a different network environment.

**Q: Module not found errors.**
Ensure all dependencies are installed:
```bash
pip install httpx fastapi uvicorn websockets
```

---

## Roadmap

- [ ] Plugin system
- [ ] File upload & preview in chat
- [ ] Code interpreter sandbox
- [ ] Custom skill authoring
- [ ] Multi-user support
- [ ] Mobile-responsive UI

---

## License

MIT
