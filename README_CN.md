# OpenAgent

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104-009688)](https://fastapi.tiangolo.com/)

**OpenAgent** 是一个开箱即用的 AI Agent 框架，配备 Web 图形界面和 CLI 命令行。

支持联网搜索、Skill 自动发现与安装、10+ 家 LLM 厂商，所有功能打包在一个 Python 应用中。

---

## ✨ 功能特性

| 功能 | 说明 |
|------|------|
| **🌐 联网搜索** | 内置 DuckDuckGo/Bing 搜索 + wttr.in 天气 API，无需额外 Key |
| **📦 Skill 自动发现** | 从 GitHub 搜索功能包 → 推荐给用户 → 用户确认后自动安装 → 立即使用 |
| **🤖 多厂商 LLM** | OpenAI、DeepSeek、通义千问、智谱 GLM、Kimi、Claude、Gemini、豆包 |
| **💬 流式对话** | WebSocket 实时流式响应，打字机效果输出 |
| **💻 Web UI + CLI** | 暗色主题桌面级网页 UI + 功能完整的命令行 |
| **🧠 上下文增强** | 长对话自动摘要、记忆注入、用户画像感知 |
| **🔧 内置工具** | 文件读写、Shell 命令、联网搜索、HTTP 请求 |
| **📋 对话管理** | 自动保存、历史浏览、恢复 |
| **🛡️ 安全机制** | 注入防护、路径遍历防护、安全沙箱、受限 eval |

> 🌟 **核心亮点**：当 Agent 遇到不会做的事情时，会自动去 GitHub 和网络上搜索相关的 Skill 功能包，推荐给用户，用户确认后一键安装，装完立即使用。

---

## 🚀 3 分钟快速开始

### 环境要求

- Python 3.10+
- pip

### 1. 安装

```bash
git clone https://github.com/cheche089/agent-framework.git
cd agent-framework

# 安装依赖
pip install httpx fastapi uvicorn websockets
```


### 2. 启动

**Web UI（推荐新手）：**
```bash
cd agent-framework
python web_ui/main.py
# 浏览器打开 http://127.0.0.1:8080
```


### 3.配置 API Key（至少配置一个）

在如下的启动后web界面设置里面配置即可
<img width="1143" height="767" alt="image" src="https://github.com/user-attachments/assets/9ca1d101-9856-4d70-a601-cca2e716784a" />

---

## 🎯 使用效果演示

### 智能问答

```
你 > 今天上海天气怎么样？

🌤️  正在查询上海天气...

━━━ 上海 天气 ━━━
🌡️  当前温度：28°C
🤗 体感温度：26°C
🌤️  天气状况：多云
💧 湿度：65%
💨 风速：12 km/h

📅 2026-06-14: 22°C ~ 28°C
   06:00 22°C ☀️ 晴
   12:00 28°C ⛅ 多云
   18:00 25°C 🌙 晴
```

### Skill 自动安装

```
你 > 帮我审查一下这个 Python 项目

🔎 正在搜索可用的功能包...
我找到了 2 个和「代码审查」相关的功能包：

1️⃣  code_review
    用途：审查 Python 代码质量

2️⃣  security_check
    用途：检查代码安全漏洞

想装哪个？告诉我编号就行

你 > 装第1个

📥 正在安装... 
✅ 安装成功！「code_review」已经可以使用了。
现在我来审查你的代码...
```

### 联网搜索

```
你 > 帮我查一下最近有什么科技新闻

🔍 搜索: 2026年6月 科技新闻
以下是搜索到的结果：

1. OpenAI 发布 GPT-5
   人工智能领域再次迎来重大突破...

2. 国内大模型厂商竞相发布新版本
   ...
```

---

## 🖥️ Web UI 界面

```
┌──────────────────────────────────────────────────┐
│  ┌─────────────┐  ┌────────────────────────────┐ │
│  │  厂商 ▼     │  │  模型 ▼                   │ │
│  └─────────────┘  └────────────────────────────┘ │
│  ┌─────────────┐  ┌────────────────────────────┐ │
│  │  对话列表    │  │ 对话区域（流式输出）         │ │
│  │  ├─ 天气查询  │  │                            │ │
│  │  ├─ 代码审查  │  │                            │ │
│  │  └─ 新对话    │  │                            │ │
│  │              │  │                            │ │
│  │  [设置]      │  └────────────────────────────┘ │
│  └─────────────┘  ┌────────────────────────────┐ │
│                   │ >>> 输入消息...             │ │
│                   └────────────────────────────┘ │
└──────────────────────────────────────────────────┘
```

### 设置说明

| 配置项 | 说明 |
|--------|------|
| API 密钥 | 各厂商密钥，仅本地保存 |
| 温度 | 控制回复随机性（0.0–2.0），越低越确定 |
| 最大 Token | 回复最大长度 |
| 系统提示词 | 自定义提示词，让 AI 扮演特定角色 |

---

## 📁 项目结构

```
agent-framework/
├── web_ui/                    # Web 图形界面
│   ├── main.py                # FastAPI 后端 + WebSocket 处理器
│   └── static/                # 前端资源（HTML、CSS、JS）
├── agent_framework/           # 核心 Python 库
│   ├── agent.py               # Agent 主编排器
│   ├── llm/                   # 多厂商 LLM 客户端（10+ 家）
│   ├── tools/                 # 工具系统：文件、Shell、搜索、HTTP
│   ├── skills/                # Skill 管理器、安装器、注册表
│   ├── web/                   # 搜索引擎（DuckDuckGo + Bing + wttr.in）
│   ├── memory/                # 记忆系统（TF-IDF 检索）
│   ├── context/               # 上下文管理 + 增强
│   ├── workflow/              # 工作流引擎
│   ├── sandbox/               # Docker 沙箱 + 安全策略
│   ├── planner/               # 任务规划与分解
│   └── harness/               # 安全护栏与指标收集
├── examples/                  # 使用示例
│   ├── run_agent.py           # 交互式 CLI Agent
│   └── run_webui.py           # Web UI 启动脚本
├── .openagent/                # 本地配置（已 gitignore）
├── .gitignore
├── pyproject.toml
└── README.md
```

---

## 🤖 支持的 LLM 厂商

| 厂商 | 环境变量 | 默认模型 |
|------|---------|---------|
| OpenAI | `OPENAI_API_KEY` | gpt-4o |
| DeepSeek | `DEEPSEEK_API_KEY` | deepseek-chat |
| 通义千问 | `QWEN_API_KEY` | qwen-plus |
| 智谱 GLM | `ZHIPU_API_KEY` | glm-4-flash |
| Moonshot Kimi | `MOONSHOT_API_KEY` | moonshot-v1-8k |
| Anthropic Claude | `ANTHROPIC_API_KEY` | claude-3-5-sonnet |
| Google Gemini | `GOOGLE_API_KEY` | gemini-2.0-flash |
| 豆包 | `DOUBAO_API_KEY` | doubao-pro-32k |

---

## 🔧 CLI 命令

```
>>> /help      - 显示帮助
>>> /skills    - 列出已安装的 Skill
>>> /search <关键词> - 搜索 Skill 市场
>>> install <编号> - 安装编号对应的 Skill
>>> exit        - 退出
```

---

## 🧪 运行测试

```bash
pip install pytest pytest-asyncio
pytest tests/
```

---

## 🛡️ 安全说明

- **API Key 零泄露** — 只从环境变量或本地配置文件读取，不上传
- **命令注入防护** — 使用 `shlex` 安全解析，不使用 shell
- **路径穿越防护** — 规范化路径后校验
- **安全 eval** — 严格限制只允许基础比较操作
- **Docker 沙箱** — 资源限制 + 无网络隔离执行

---

## ❓ 常见问题

**问：联网搜索没有结果？**
> DuckDuckGo 可能限制了部分 IP。换个搜索词或网络环境试试。

**问：端口 8080 被占用了？**
> 修改 `web_ui/main.py` 最后一行的端口号。

**问：API 返回 401？**
> 检查 API Key 是否正确，也可以在 Web UI 设置面板重新输入。

**问：提示找不到模块？**
> 运行 `pip install httpx fastapi uvicorn websockets`

**问：配置文件在哪里？**
> `.openagent/` 文件夹下，已加入 `.gitignore`，不会提交到 Git。

---

## 📜 许可证

MIT — 详见 [LICENSE](LICENSE)。

---

## 📬 项目地址

[https://github.com/cheche089/agent-framework](https://github.com/cheche089/agent-framework)
