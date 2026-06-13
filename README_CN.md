# OpenAgent

![Python](https://img.shields.io/badge/python-3.10+-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![FastAPI](https://img.shields.io/badge/FastAPI-0.104-009688)

**OpenAgent** 是一个模块化的 AI Agent 框架，配备直观的 Web 图形界面，支持 10+ 家 LLM 厂商。内置工具系统、Skill 管理、联网搜索，以及桌面级的操作界面 —— 全部在一个 Python 应用中。

支持命令行和web交互,下面有两种不同的打开方式
这是一个基本没有skill的agent,可用自行下载配置自己的skill喵
本地部署agent

---

## 功能特性

| 功能 | 说明 |
|------|------|
| **多厂商支持** | OpenAI、DeepSeek、通义千问、智谱 GLM、Kimi、Claude、Gemini、豆包 |
| **流式对话** | 基于 WebSocket 的实时流式响应，打字机效果输出 |
| **联网搜索** | 内置 DuckDuckGo 搜索，无需额外 API Key |
| **Skill 系统** | 精选 Skill 市场，一键安装/卸载/执行 |
| **对话管理** | 多轮对话自动保存、历史浏览、恢复 |
| **内置工具** | 文件读写、Shell 命令执行、联网搜索 |
| **暗色主题** | Codex 风格的桌面级界面 |
| **Docker 沙箱** | 基于 Docker 容器的隔离命令执行 |
| **工作流引擎** | 顺序、条件、循环、并行工作流 |
| **记忆系统** | TF-IDF 语义检索 + LLM 摘要压缩 |

---

## 快速开始（3 分钟）

### 1. 环境要求

- Python 3.10+
- pip

### 2. 安装

```bash
git clone https://github.com/cheche089/agent-framework.git
cd agent-framework

# 安装依赖
pip install httpx fastapi uvicorn websockets
```

### 3. 配置 API Key

至少配置一个厂商（推荐 DeepSeek 或 OpenAI，价格实惠）：

**Linux / macOS:**
```bash
# DeepSeek（推荐，性价比高）
export DEEPSEEK_API_KEY="sk-你的key"

# OpenAI
export OPENAI_API_KEY="sk-你的key"

# 通义千问（阿里云）
export QWEN_API_KEY="sk-你的key"

# Anthropic Claude
export ANTHROPIC_API_KEY="sk-你的key"
```

**Windows PowerShell:**
```powershell
$env:DEEPSEEK_API_KEY = "sk-你的key"
$env:OPENAI_API_KEY = "sk-你的key"
```

> 也可以在 Web UI 的设置面板中直接输入 API Key，会自动保存到本地配置文件。

### 4. 启动 Web UI

```bash
cd agent-framework
python web_ui/main.py
```

打开浏览器访问 **http://127.0.0.1:8080**

**Windows 用户也可以双击 `start_webui.bat` 一键启动。**

---

## 使用指南

### 界面布局

OpenAgent 的界面分为三个区域：

```
┌───────────────┬──────────────────────────────────┐
│               │  顶部: 模型选择器                  │
│   左侧栏       │                                  │
│               │  中间: 对话区域（流式输出）          │
│  对话列表      │                                  │
│  新建对话      │                                  │
│               │  底部: 输入框                      │
│  工具/Skill   │                                  │
│  设置         │                                  │
└───────────────┴──────────────────────────────────┘
```

### 基础对话

1. 在顶部下拉框中选择 **厂商**（如 DeepSeek、OpenAI）
2. 选择 **模型**（如 deepseek-chat、gpt-4o）
3. 在输入框中输入消息，按 **Enter** 发送
4. 回复会实时流式输出，像打字机一样逐字出现

### 联网搜索

1. 点击左侧栏底部的 **工具/Skill** 按钮
2. 切换到 **工具** 页签
3. 在搜索框中输入关键词，点击"搜索"
4. 搜索结果会以卡片形式展示
5. 你也可以在对话中让 AI 直接帮你搜索

### 安装和使用 Skill

1. 点击 **工具/Skill** → 切换到 **安装** 页签
2. 浏览精选 Skill 列表：
   - **联网搜索** — 搜索互联网获取实时信息
   - **代码审查** — 审查 Python 代码质量
   - **内容总结** — 智能总结文本内容
   - **文件整理** — 自动分类和组织文件
3. 点击 **安装** 按钮
4. 安装完成后，切换到 **Skills** 页签查看已安装的 Skill
5. 在对话中描述你的任务，AI 会自动调用已安装的 Skill

### 配置设置

点击左侧栏底部的 **设置** 按钮：

| 配置项 | 说明 |
|--------|------|
| API 密钥 | 配置各厂商的 API Key，输入后自动保存 |
| 温度 | 控制回复的随机性（0.0 - 2.0），数字越小越确定 |
| 最大 Token | 控制回复的最大长度 |
| 系统提示词 | 自定义系统提示词，让 AI 扮演特定角色 |

> API Key 仅保存在本地 `.openagent/config.json` 文件中，不会被上传或泄漏。

### 命令行模式

除了 Web UI，也支持命令行交互：

```bash
python examples/run_agent.py
```

查看完整功能演示：

```bash
python examples/basic_agent.py
```

---

## 支持的厂商

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

## 项目结构

```
agent-framework/
├── web_ui/                    # Web 图形界面
│   ├── main.py                # FastAPI 后端服务
│   └── static/                # 前端资源
│       ├── index.html         # 主页面
│       ├── styles.css         # 暗色主题样式
│       └── app.js             # 前端交互逻辑
├── agent_framework/           # 核心 Python 库
│   ├── agent.py               # Agent 编排器
│   ├── config.py              # 配置管理
│   ├── core/                  # 基础接口和类型定义
│   ├── llm/                   # 多厂商 LLM 客户端
│   ├── tools/                 # 内置工具（文件、Shell）
│   ├── memory/                # 记忆系统与检索
│   ├── planner/               # 任务规划与分解
│   ├── workflow/              # 工作流引擎
│   ├── sandbox/               # Docker 沙箱与安全策略
│   └── skills/                # Skill 加载与管理
├── examples/                  # 使用示例
│   ├── run_agent.py           # 命令行交互式 Agent
│   ├── run_webui.py           # Web UI 启动脚本
│   └── basic_agent.py         # 完整功能演示
├── tests/                     # 测试用例
├── docker/                    # Docker 沙箱镜像
└── pyproject.toml             # Python 包配置
```

---

## 常见问题

**问：端口 8080 被占用了怎么办？**
```bash
# 修改 web_ui/main.py 最后一行的端口号，或杀掉占用进程
# 也可以指定其他端口启动
```

**问：API 返回 401 未授权？**
检查 API Key 是否正确配置。也可以在 Web UI 的**设置**面板中直接输入密钥。

**问：联网搜索没有结果？**
DuckDuckGo 可能限制了部分 IP 的请求。可以换一个搜索词，或者换一个网络环境尝试。

**问：提示找不到模块？**
确保所有依赖已安装：
```bash
pip install httpx fastapi uvicorn websockets
```

**问：配置文件在哪里？**
配置文件在项目根目录的 `.openagent/` 文件夹下，已加入 `.gitignore`，不会提交到 Git。

---

## 开发路线

- [ ] 插件系统
- [ ] 文件上传与预览
- [ ] 代码解释器沙箱
- [ ] 自定义 Skill 编辑器
- [ ] 多用户支持
- [ ] 移动端适配

---

## 许可证

MIT
