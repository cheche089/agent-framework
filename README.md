# OpenAgent Framework

A modular AI Agent framework. Supports 10+ LLM providers with interactive CLI.

---

## Quick Start

### 1. Install

```
pip install httpx
```

### 2. Set API Key (pick one)

```
# Linux / macOS
export OPENAI_API_KEY="sk-your-key"
export DEEPSEEK_API_KEY="sk-your-key"

# Windows PowerShell
`$env:OPENAI_API_KEY = "sk-your-key"
`$env:DEEPSEEK_API_KEY = "sk-your-key"
```

### 3. Run

```
python examples/run_agent.py
```

Type commands like:
- List all py files
- Create hello.py
- Read README.md and summarize

---

## Supported LLM Providers

| Provider       | Env Variable           | Default Model      |
|----------------|------------------------|--------------------|
| OpenAI         | OPENAI_API_KEY         | gpt-4o             |
| DeepSeek       | DEEPSEEK_API_KEY       | deepseek-chat      |
| Alibaba Qwen   | QWEN_API_KEY           | qwen-plus          |
| Zhipu GLM      | ZHIPU_API_KEY          | glm-4-flash        |
| Moonshot Kimi  | MOONSHOT_API_KEY       | moonshot-v1-8k     |
| Baidu ERNIE    | ERNIE_API_KEY          | ernie-4.0          |
| ByteDance Doubao | DOUBAO_API_KEY       | doubao-pro-32k     |
| 01.AI Yi       | YI_API_KEY             | yi-lightning       |
| Anthropic      | ANTHROPIC_API_KEY      | claude-3-5-sonnet  |
| Google Gemini  | GOOGLE_API_KEY         | gemini-2.0-flash   |

---

## Run Examples

```
python examples/basic_agent.py
python examples/run_agent.py
```

---

## License

MIT
