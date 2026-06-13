# OpenAgent Framework

模块化 AI Agent 框架，支持 10+ LLM 厂商，提供交互式 CLI。

---

## 快速开始

### 1. 安装

```
pip install httpx
```

### 2. 设置 API Key（任选一个）

```
# Linux / macOS
export DEEPSEEK_API_KEY="sk-你的key"
export OPENAI_API_KEY="sk-你的key"

# Windows PowerShell
`$env:DEEPSEEK_API_KEY = "sk-你的key"
`$env:OPENAI_API_KEY = "sk-你的key"
```

### 3. 启动交互对话

```
python examples/run_agent.py
```

然后输入指令：
- 列出当前目录所有 py 文件
- 创建一个 hello.py
- 读取 README 总结一下

---

## 支持的 LLM 厂商

| 厂商    | 环境变量             | 默认模型          |
|----------------|----------------------|-------------------|
| DeepSeek       | DEEPSEEK_API_KEY     | deepseek-chat     |
| OpenAI         | OPENAI_API_KEY       | gpt-4o            |
| 通义千问       | QWEN_API_KEY         | qwen-plus         |
| 智谱 GLM       | ZHIPU_API_KEY        | glm-4-flash       |
| Kimi           | MOONSHOT_API_KEY     | moonshot-v1-8k    |
| 百度 ERNIE     | ERNIE_API_KEY        | ernie-4.0         |
| 豆包           | DOUBAO_API_KEY       | doubao-pro-32k    |
| 零一万物       | YI_API_KEY           | yi-lightning      |
| Anthropic      | ANTHROPIC_API_KEY    | claude-3-5-sonnet |
| Google Gemini  | GOOGLE_API_KEY       | gemini-2.0-flash  |

---

## 运行示例

```
python examples/basic_agent.py
python examples/run_agent.py
```

---

## License

MIT
