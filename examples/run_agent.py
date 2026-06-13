"""交互式 Agent CLI — 像 Codex/Claude Code 一样对话"""

import asyncio, os, sys
sys.path.insert(0, os.path.dirname(__file__))

from agent_framework.llm import LLMMessage, create_client, LLMConfig, list_providers
from agent_framework.tools.registry import DefaultToolRegistry
from agent_framework.tools.builtin import FileReadTool, FileWriteTool, ShellTool
from agent_framework.core.types import ToolSpec

SYSTEM_PROMPT = """你是一个 AI 编程助手，可以帮助用户完成各种任务。

你有以下工具可用：
{}

请按以下格式调用工具：
工具名称(参数1=值1, 参数2=值2)

调用后我会返回执行结果，然后你再继续分析。

如果不需要调用工具，直接回复用户即可。
请用中文回答。"""

class InteractiveAgent:
    def __init__(self):
        self.llm = create_client("deepseek")
        self.tools = DefaultToolRegistry()
        self.tools.register(FileReadTool())
        self.tools.register(FileWriteTool())
        self.tools.register(ShellTool())
        self.messages = []

    def _create_client(self):
        providers_list = list_providers()
        provider_id = os.getenv('LLM_PROVIDER', 'openai')
        for p in providers_list:
            env_key = p.get('env_key', p['id'].upper() + '_API_KEY')
            if os.getenv(env_key):
                provider_id = p['id']
                break
        print(f'  [Using provider: {provider_id}]')
        return create_client(provider_id)

    def get_tools_desc(self) -> str:
        lines = []
        for s in self.tools.list_specs():
            lines.append(f"- {s.name}: {s.description}")
            if s.parameters.get("properties"):
                for pn, pv in s.parameters["properties"].items():
                    req = "必填" if pn in s.parameters.get("required", []) else "可选"
                    lines.append(f"    {pn} ({req}): {pv.get('description', '')}")
        return "\n".join(lines)

    async def chat(self, user_input: str) -> str:
        if not self.messages:
            self.messages.append(LLMMessage(role="system", content=SYSTEM_PROMPT.format(self.get_tools_desc())))
        self.messages.append(LLMMessage(role="user", content=user_input))

        for _ in range(5):
            response = await self.llm.chat(self.messages)
            self.messages.append(LLMMessage(role="assistant", content=response))

            # 检查是否要调用工具
            tool_name = None
            for s in self.tools.list_specs():
                if f"{s.name}(" in response:
                    tool_name = s.name
                    break

            if not tool_name:
                return response  # 不需要工具，直接返回

            # 解析工具调用
            for line in response.split("\n"):
                for s in self.tools.list_specs():
                    if s.name in line and "(" in line:
                        try:
                            parts = line.strip().split("(", 1)
                            if len(parts) < 2: continue
                            args_str = parts[1].rstrip(")")
                            kwargs = {}
                            for pair in args_str.split(","):
                                if "=" in pair:
                                    k, v = pair.split("=", 1)
                                    kwargs[k.strip()] = v.strip().strip("'\"")
                            result = await self.tools.execute(tool_name, None, **kwargs)
                            result_msg = f"工具 [{tool_name}] 执行结果:\n"
                            if result.success:
                                result_msg += result.output[:2000]
                            else:
                                result_msg += f"错误: {result.error}"
                            self.messages.append(LLMMessage(role="user", content=result_msg))
                            break
                        except Exception as e:
                            self.messages.append(LLMMessage(role="user", content=f"工具调用失败: {e}"))
                    if tool_name:
                        break
                if tool_name:
                    break
        else:
            return "超过最大执行轮数"

    async def run(self):
        print("=" * 60)
        print("OpenAgent — 交互式 AI 助手 (输入 exit 退出)")
        print("=" * 60)
        print()

        while True:
            user_input = input(">>> ").strip()
            if not user_input:
                continue
            if user_input.lower() in ("exit", "quit", "q"):
                print("再见！")
                break

            print()
            response = await self.chat(user_input)
            print(response)
            print()

if __name__ == "__main__":
    agent = InteractiveAgent()
    asyncio.run(agent.run())
