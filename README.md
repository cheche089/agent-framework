# OpenAgent — Modular AI Agent Framework

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)]()
[![License: MIT](https://img.shields.io/badge/license-MIT-green)]()

**OpenAgent** is a modular, production-ready AI Agent framework. It provides a full toolkit to build, extend, and run intelligent agents locally — with internet search, skill auto-discovery, multi-provider LLM support, and a beautiful Web UI.

## Features

- **Modular Architecture** — Tools, Planner, Memory, Context, Workflow, Skills, Sandbox — all pluggable interfaces
- **Internet Search** — Built-in web search with automatic weather detection and GitHub raw content conversion
- **Multi-Provider LLM** — Supports OpenAI, DeepSeek, Anthropic Claude, Google Gemini, Alibaba Qwen, Zhipu GLM, Moonshot Kimi, Baidu ERNIE, ByteDance Doubao, Lingyi Wanwu (Yi)
- **Skill System** — Auto-discover, search, and install one-click skill packs from the community marketplace
- **Web UI** — Codex-style chat interface with streaming output, conversation management, and multi-model switching
- **Agent Loop Engine** — Thought → Action → Observation loop with auto-retry, replanning, and human intervention
- **Harness Engine** — Safety guardrails, feedback loops, tool call management, and execution metrics
- **Docker Sandbox** — Isolated command execution environment
- **Long-Running Tasks** — Checkpoint support for resumable long-running tasks
- **Workflow Engine** — Graph-based workflow orchestration

## Quick Start

### 1. Prerequisites

- Python 3.10+
- An API key from any supported LLM provider

### 2. Setup

`ash
# Clone the repo
git clone https://github.com/cheche089/agent-framework.git
cd agent-framework

# (Optional) Create virtual environment
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate

# Install dependencies
pip install httpx>=0.27
`

### 3. Configure API Key

Set your LLM provider's API key as an environment variable:

| Provider   | Env Variable        | Default Model        |
|------------|---------------------|----------------------|
| OpenAI     | OPENAI_API_KEY    | gpt-4o               |
| DeepSeek   | DEEPSEEK_API_KEY  | deepseek-chat        |
| Anthropic  | ANTHROPIC_API_KEY | claude-3-5-sonnet    |
| Google     | GOOGLE_API_KEY    | gemini-2.0-flash     |
| Alibaba Qwen | QWEN_API_KEY    | qwen-plus            |
| Zhipu GLM  | ZHIPU_API_KEY     | glm-4-flash          |
| Moonshot Kimi | MOONSHOT_API_KEY | moonshot-v1-8k    |
| Baidu ERNIE | ERNIE_API_KEY    | ernie-4.0            |
| Doubao     | DOUBAO_API_KEY    | doubao-pro-32k       |
| Yi (01.AI) | YI_API_KEY        | yi-lightning         |

**Windows (CMD):**
`cmd
set OPENAI_API_KEY=sk-your-key-here
`

**Windows (PowerShell):**
`powershell
="sk-your-key-here"
`

**macOS / Linux:**
`ash
export OPENAI_API_KEY="sk-your-key-here"
`

### 4. Run

#### Interactive CLI

`ash
python examples/run_agent.py
`

#### Web UI (Codex-style interface)

`ash
# Option A: Double-click start_webui.bat (Windows)
# Option B:
python examples/run_webui.py
`

Then open your browser at **http://127.0.0.1:8080**

## Usage Examples

### Basic Agent

`python
import asyncio
from agent_framework import Agent, AgentConfig

async def main():
    agent = Agent(
        tool_registry=...,
        planner=...,
        memory=...,
        context_mgr=...,
        workflow_engine=...,
        skill_mgr=...,
        sandbox=...,
        config=AgentConfig.default(),
    )
    result = await agent.run("Search the latest AI news")
    print(result)

asyncio.run(main())
`

### Interactive Chat

`ash
python examples/run_agent.py
`

In the interactive mode:
- Type any question — the agent will search the web if needed
- /search <keyword> — Search the skill marketplace
- /skills — List installed skills
- install <number> — Install a skill by number
- exit — Quit

## Project Structure

`
agent-framework/
├── agent_framework/        # Core framework
│   ├── core/               # Interfaces & types
│   ├── llm/                # Multi-provider LLM abstraction
│   ├── tools/              # Tool system (built-in + web tools)
│   ├── skills/             # Skill auto-discovery & installer
│   ├── planner/            # Planning engine
│   ├── memory/             # Memory backends
│   ├── context/            # Context management
│   ├── workflow/           # Workflow engine
│   ├── sandbox/            # Sandbox execution
│   └── web/                # Web search utilities
├── web_ui/                 # Web UI (FastAPI + static files)
├── docker/                 # Docker sandbox config
├── examples/               # Example scripts
├── tests/                  # Test suite
└── docs/                   # Documentation
`

## Development

`ash
# Install dev dependencies
pip install "agent-framework[dev]"

# Run tests
pytest
`

## License

MIT
