# OpenAgent — 模块化 AI Agent 框架

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)]()
[![License: MIT](https://img.shields.io/badge/license-MIT-green)]()

**OpenAgent** 是一个模块化、生产可用的 AI Agent 框架。提供完整的工具包，让你可以快速搭建、扩展和运行本地智能 Agent —— 支持联网搜索、Skill 自动发现安装、多厂商 LLM 接入和漂亮的 Web UI。

## 功能特性

- **模块化架构** — 工具、规划器、记忆、上下文、工作流、技能、沙箱 —— 全部可插拔接口
- **联网搜索** — 内置网页搜索，自动识别天气查询和 GitHub 原始内容转换
- **多厂商 LLM** — 支持 OpenAI、DeepSeek、Anthropic Claude、Google Gemini、阿里通义千问、智谱 GLM、Moonshot Kimi、百度千帆 ERNIE、字节豆包、零一万物
- **Skill 系统** — 自动发现、搜索、一键安装社区技能扩展包
- **Web UI** — Codex 风格的聊天界面，支持流式输出、对话管理、多模型切换
- **Agent 循环引擎** — 思考 → 行动 → 观察 循环，支持自动重试、重新规划和人工介入
- **安全引擎 (Harness)** — 安全护栏、反馈回路、工具调用管理和执行指标
- **Docker 沙箱** — 隔离的命令执行环境
- **长时间运行任务** — 支持检查点断点续传
- **工作流引擎** — 基于图的工作流编排

## 快速开始

### 1. 环境要求

- Python 3.10 或更高版本
- 任一支持的 LLM 厂商 API Key

### 2. 安装

`ash
# 克隆仓库
git clone https://github.com/cheche089/agent-framework.git
cd agent-framework

# (可选) 创建虚拟环境
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate

# 安装依赖
pip install httpx>=0.27
`

### 3. 配置 API Key

设置环境变量。系统会自动检测可用的 API Key 并选择对应的厂商：

| 厂商        | 环境变量              | 默认模型              |
|-------------|-----------------------|-----------------------|
| OpenAI      | OPENAI_API_KEY      | gpt-4o                |
| DeepSeek    | DEEPSEEK_API_KEY    | deepseek-chat         |
| Anthropic   | ANTHROPIC_API_KEY   | claude-3-5-sonnet     |
| Google      | GOOGLE_API_KEY      | gemini-2.0-flash      |
| 通义千问    | QWEN_API_KEY        | qwen-plus             |
| 智谱 GLM    | ZHIPU_API_KEY       | glm-4-flash           |
| Moonshot Kimi | MOONSHOT_API_KEY  | moonshot-v1-8k        |
| 百度千帆    | ERNIE_API_KEY       | ernie-4.0             |
| 豆包        | DOUBAO_API_KEY      | doubao-pro-32k        |
| 零一万物    | YI_API_KEY          | yi-lightning          |

**Windows (CMD):**
`cmd
set OPENAI_API_KEY=sk-你的Key
`

**Windows (PowerShell):**
`powershell
="sk-你的Key"
`

**macOS / Linux:**
`ash
export OPENAI_API_KEY="sk-你的Key"
`

### 4. 运行

#### 交互式 CLI

`ash
python examples/run_agent.py
`

#### Web UI（类似 Codex 的图形界面）

`ash
# 方式 A: 双击 start_webui.bat（Windows）
# 方式 B:
python examples/run_webui.py
`

启动后浏览器打开 **http://127.0.0.1:8080**

## 使用指南

### 交互式对话

运行 python examples/run_agent.py 进入交互模式：

`
>>> 今天北京的天气怎么样？
  🌤️ 正在查询 北京 天气...

➜ 帮我搜索一下最新的 AI 新闻
  🔳 搜索: 最新 AI 新闻
`

#### 内置命令

| 命令 | 说明 |
|------|------|
| /search <关键词> | 搜索 Skill 市场 |
| /skills | 查看已安装的 Skill |
| install <编号> | 安装指定编号的 Skill |
| exit or quit | 退出 |

#### Skill 自动发现安装

当 Agent 遇到不会做的事情时，会自动搜索 Skill 市场并推荐安装：

`
>>> 帮我把这张图片变成黑白

🔍 找到了一个图片处理的 Skill：
1. 🧩 image_processor
   简介：图片滤镜、黑白转换、尺寸调整等

想安装哪一个？直接回复编号就行
>>> 装第1个
✅ 安装成功！现在我来帮你处理图片...
`

### Web UI 使用

访问 http://127.0.0.1:8080 后：

1. 点击左上角设置图标，选择 LLM 厂商和模型
2. 输入 API Key（或通过环境变量配置）
3. 在聊天框输入问题
4. Agent 会自动联网搜索、安装 Skill 来帮你解决问题

## 项目结构

`
agent-framework/
├── agent_framework/        # 核心框架
│   ├── core/               # 接口定义和类型
│   ├── llm/                # 多厂商 LLM 抽象层
│   ├── tools/              # 工具系统（内置 + 联网工具）
│   ├── skills/             # Skill 自动发现与安装
│   ├── planner/            # 规划引擎
│   ├── memory/             # 记忆后端
│   ├── context/            # 上下文管理
│   ├── workflow/           # 工作流引擎
│   ├── sandbox/            # 沙箱执行环境
│   └── web/                # 联网搜索工具
├── web_ui/                 # Web 用户界面
├── docker/                 # Docker 沙箱配置
├── examples/               # 使用示例
├── tests/                  # 测试用例
└── docs/                   # 文档
`

## 开发指南

`ash
# 安装开发依赖
pip install "agent-framework[dev]"

# 运行测试
pytest

# 运行测试（含异步测试）
pytest --asyncio-mode=auto
`

## 扩展框架

### 添加自定义工具

`python
from agent_framework.core.interfaces import BaseTool
from agent_framework.core.types import ExecutionContext, ToolResult

class MyTool(BaseTool):
    name = "my_tool"
    description = "描述你的工具"
    parameters = {
        "type": "object",
        "properties": {
            "input": {"type": "string", "description": "输入参数"},
        },
        "required": ["input"],
    }

    async def execute(self, ctx: ExecutionContext, **kwargs) -> ToolResult:
        input_val = kwargs.get("input", "")
        # 你的工具逻辑
        return ToolResult.ok(f"处理结果: {input_val}")

# 注册到工具注册表
tool_registry.register(MyTool())
`

## License

MIT
