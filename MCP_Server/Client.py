import asyncio
import os
import sys
import signal
import json
from typing import Optional, List
from contextlib import AsyncExitStack
from datetime import datetime
import re
from openai import OpenAI
from dotenv import load_dotenv
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
load_dotenv()


class MCPClient:

    def __init__(self):
        # 创建 AsyncExitStack，用于托管所有异步资源释放，这是为了后续连接MCP Server时使用`async with` 语法自动管理上下文。
        self.exit_stack = AsyncExitStack()

        # 从环境中读取配置项
        self.openai_api_key = os.getenv("DASHSCOPE_API_KEY")
        self.base_url = os.getenv("BASE_URL")
        self.model = os.getenv("MODEL")

        # 对 LLM 相关配置进行初始化
        if not self.openai_api_key:
            raise ValueError("❌ 未找到 OpenAI API Key，请在 .env 文件中设置 DASHSCOPE_API_KEY")

        # 初始化 OpenAI 客户端对象
        self.client = OpenAI(api_key=self.openai_api_key, base_url=self.base_url)

        # 初始化 MCP Session（用于延迟赋值），等待连接 MCP Server 后再初始化它
        self.session: Optional[ClientSession] = None

    async def connect_to_server(self, server_script_path: str):
        # 对服务器脚本进行判断，只允许是 .py 或 .js
        is_python = server_script_path.endswith('.py')
        is_js = server_script_path.endswith('.js')
        if not (is_python or is_js):
            raise ValueError("服务器脚本必须是 .py 或 .js 文件")

        # 确定启动命令，.py 用 python，.js 用 node
        command = "python" if is_python else "node"

        # 构造 MCP 所需的服务器参数，包含启动命令、脚本路径参数、环境变量（为 None 表示默认）
        server_params = StdioServerParameters(command=command, args=[server_script_path], env=None)

        # 启动 MCP 工具服务进程（并建立 stdio 通信）
        stdio_transport = await self.exit_stack.enter_async_context(stdio_client(server_params))

        # 拆包通信通道，读取服务端返回的数据，并向服务端发送请求
        self.stdio, self.write = stdio_transport

        # 创建 MCP 客户端会话对象
        self.session = await self.exit_stack.enter_async_context(ClientSession(self.stdio, self.write))

        # 初始化会话
        await self.session.initialize()

        # 获取工具列表并打印
        response = await self.session.list_tools()
        tools = response.tools
        print("\n已连接到服务器，支持以下工具:", [tool.name for tool in tools])

    async def process_query(self, query: str) -> str:
        # 获取可用工具
        response = await self.session.list_tools()
        available_tools = [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "input_schema": tool.inputSchema
                }
            } for tool in response.tools
        ]

        # 生成文件名
        keyword_match = re.search(r'(关于|分析|查询|搜索|查看)([^的\s，。、？\n]+)', query)
        keyword = keyword_match.group(2) if keyword_match else "分析对象"
        safe_keyword = re.sub(r'[\\/:*?"<>|]', '', keyword)[:20]
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        md_filename = f"sentiment_{safe_keyword}_{timestamp}.md"
        md_path = os.path.join("./sentiment_reports", md_filename)

        os.makedirs("./sentiment_reports", exist_ok=True)
        os.makedirs("./llm_outputs", exist_ok=True)

        # 初始消息
        messages = [{"role": "user", "content": query}]

        # 多轮工具调用循环
        max_iterations = 5  # 防止无限循环
        for iteration in range(max_iterations):
            # 调用模型
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=available_tools,
                tool_choice="auto"
            )

            message = response.choices[0].message
            messages.append(message)

            # 如果没有工具调用，结束循环
            if not message.tool_calls:
                break

            print(f"\n🔧 第 {iteration + 1} 轮工具调用:")

            # 执行所有工具调用
            for tool_call in message.tool_calls:
                tool_name = tool_call.function.name
                tool_args = json.loads(tool_call.function.arguments)

                print(f"  📞 调用: {tool_name}")
                print(f"  📝 参数: {tool_args}")

                # 注入文件名和路径
                if tool_name == "analyze_sentiment" and "filename" not in tool_args:
                    tool_args["filename"] = md_filename
                if tool_name == "send_email_with_attachment":
                    if "attachment_path" not in tool_args:
                        tool_args["attachment_path"] = md_path
                    if "filename" not in tool_args:
                        tool_args["filename"] = md_filename
                if tool_name == "search_google_news" and "keyword" not in tool_args:
                    # 从查询中提取关键词
                    tool_args["keyword"] = "deepseek-v4"

                # 调用 MCP 工具
                try:
                    result = await self.session.call_tool(tool_name, tool_args)
                    tool_result = result.content[0].text
                    print(f"  ✅ 返回: {tool_result[:100]}...")

                    # 添加工具结果
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": tool_result
                    })
                except Exception as e:
                    print(f"  ❌ 错误: {e}")
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": f"工具调用失败: {str(e)}"
                    })

        # 获取最终回复
        final_output = messages[-1].content if messages[-1].role == "assistant" else "任务完成"

        # 保存对话记录
        safe_filename = re.sub(r'[\\/:*?"<>|]', '', query)[:50]
        file_path = os.path.join("./llm_outputs", f"{safe_filename}_{timestamp}.txt")

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(f"🗣 用户提问：{query}\n\n")
            f.write(f"🤖 模型回复：\n{final_output}\n")

        print(f"📄 对话记录已保存为：{file_path}")

        return final_output
    async def chat_loop(self):
        # # 初始化提示信息
        # print("\n🤖 MCP 客户端已启动！输入 'quit' 退出")
        #
        # # 进入主循环中等待用户输入
        # while True:
        #     try:
        #         query = input("\n你: ").strip()
        #         if query.lower() == 'quit':
        #             break
        #
        #         # 处理用户的提问，并返回结果
        #         response = await self.process_query(query)
        #         print(f"\n🤖 AI: {response}")
        #
        #     except Exception as e:
        #         print(f"\n⚠️ 发生错误: {str(e)}")
        """交互式对话循环"""
        print("\n🤖 MCP 客户端已启动！输入 'quit' 退出")

        while True:
            try:
                query = input("\n你: ").strip()
                if query.lower() == 'quit':
                    print("👋 正在退出...")
                    break

                response = await self.process_query(query)
                print(f"\n🤖 AI: {response}")

            except KeyboardInterrupt:
                print("\n👋 检测到中断信号，正在退出...")
                break
            except Exception as e:
                print(f"\n⚠️ 发生错误: {str(e)}")



    # async def plan_tool_usage(self, query: str, tools: List[dict]) -> List[dict]:
    #     # 构造系统提示词 system_prompt。
    #     # 将所有可用工具组织为文本列表插入提示中，并明确指出工具名，
    #     # 限定返回格式是 JSON，防止其输出错误格式的数据。
    #     print("\n📤 提交给大模型的工具定义:")
    #     print(json.dumps(tools, ensure_ascii=False, indent=2))
    #     tool_list_text = "\n".join([
    #         f"- {tool['function']['name']}: {tool['function']['description']}"
    #         for tool in tools
    #     ])
    #     system_prompt = {
    #         "role": "system",
    #         "content": (
    #             "你是一个智能任务规划助手，用户会给出一句自然语言请求。\n"
    #             "你只能从以下工具中选择（严格使用工具名称）：\n"
    #             f"{tool_list_text}\n"
    #             "如果多个工具需要串联，后续步骤中可以使用 {{上一步工具名}} 占位。\n"
    #             "返回格式：JSON 数组，每个对象包含 name 和 arguments 字段。\n"
    #             "不要返回自然语言，不要使用未列出的工具名。"
    #         )
    #     }
    #
    #     # 构造对话上下文并调用模型。
    #     # 将系统提示和用户的自然语言一起作为消息输入，并选用当前的模型。
    #     planning_messages = [
    #         system_prompt,
    #         {"role": "user", "content": query}
    #     ]
    #
    #     response = self.client.chat.completions.create(
    #         model=self.model,
    #         messages=planning_messages,
    #         tools=tools,
    #         tool_choice="none"
    #     )
    #
    #     # 提取出模型返回的 JSON 内容
    #     content = response.choices[0].message.content.strip()
    #     match = re.search(r"```(?:json)?\\s*([\s\S]+?)\\s*```", content)
    #     if match:
    #         json_text = match.group(1)
    #     else:
    #         json_text = content
    #
    #     # 在解析 JSON 之后返回调用计划
    #     try:
    #         plan = json.loads(json_text)
    #         return plan if isinstance(plan, list) else []
    #     except Exception as e:
    #         print(f"❌ 工具调用链规划失败: {e}\n原始返回: {content}")
    #         return []
    async def plan_tool_usage(self, query: str, tools: List[dict]) -> List[dict]:
        # 构造系统提示词
        tool_list_text = "\n".join([
            f"- {tool['function']['name']}: {tool['function']['description']}"
            for tool in tools
        ])

        system_prompt = {
            "role": "system",
            "content": (
                "你是一个任务规划助手。你必须只返回JSON数组，不要返回任何其他文本，不要使用markdown代码块。\n"
                "可用工具：\n"
                f"{tool_list_text}\n\n"
                "根据用户请求，返回一个工具调用计划。\n"
                "格式示例：\n"
                '[\n'
                '  {"name": "search_google_news", "arguments": {"keyword": "deepseek-v4"}},\n'
                '  {"name": "analyze_sentiment", "arguments": {"text": "{{search_google_news}}", "filename": "sentiment_report.md"}},\n'
                '  {"name": "send_email_with_attachment", "arguments": {"to": "user@example.com", "subject": "分析报告", "body": "见附件", "filename": "sentiment_report.md"}}\n'
                ']\n\n'
                "重要：只返回纯JSON数组，不要用```json```包裹，不要添加任何解释。"
            )
        }

        planning_messages = [
            system_prompt,
            {"role": "user", "content": query}
        ]

        response = self.client.chat.completions.create(
            model=self.model,
            messages=planning_messages,
            temperature=0.1
        )

        content = response.choices[0].message.content.strip()
        print(f"\n📥 模型返回原始内容:\n{content}\n")

        # 改进的JSON提取逻辑
        plan = []

        # 方法1: 移除markdown代码块标记
        content = re.sub(r'^```json\s*', '', content)
        content = re.sub(r'^```\s*', '', content)
        content = re.sub(r'\s*```$', '', content)

        # 方法2: 尝试提取JSON数组
        json_match = re.search(r'\[[\s\S]*\]', content)
        if json_match:
            json_str = json_match.group()
            try:
                plan = json.loads(json_str)
                print("✅ 成功解析JSON")
            except json.JSONDecodeError as e:
                print(f"❌ JSON解析失败: {e}")
                # 尝试修复常见的JSON问题
                try:
                    # 替换单引号为双引号
                    json_str_fixed = json_str.replace("'", '"')
                    plan = json.loads(json_str_fixed)
                    print("✅ 使用修复后的JSON解析成功")
                except:
                    plan = []
        else:
            print("❌ 未找到JSON数组")

        # 确保plan是列表格式
        if not isinstance(plan, list):
            plan = [plan] if isinstance(plan, dict) else []

        # 验证并清理plan
        validated_plan = []
        for step in plan:
            if isinstance(step, dict) and "name" in step:
                if "arguments" not in step:
                    step["arguments"] = {}
                validated_plan.append(step)
                print(f"✅ 添加工具调用: {step['name']}")
            else:
                print(f"⚠️ 跳过无效步骤: {step}")

        if not validated_plan:
            print("⚠️ 未生成有效工具计划，将尝试直接处理")
            # 返回一个默认计划让主流程继续
            return []

        return validated_plan

    async def cleanup(self):#主动清理
        """清理资源，忽略清理过程中的错误"""
        try:
            await self.exit_stack.aclose()
        except Exception as e:
            print(f"⚠️ 清理资源时出现非致命错误: {e}")

async def main():
    """主函数"""
    server_script_path = "D:\\Git_PR_Practice\\MCP_Server\\server.py"  # 请修改为您的实际路径

    # 检查服务器文件是否存在
    if not os.path.exists(server_script_path):
        print(f"❌ 找不到服务器脚本: {server_script_path}")
        return

    client = MCPClient()
    try:
        await client.connect_to_server(server_script_path)
        await client.chat_loop()
    except KeyboardInterrupt:
        print("\n👋 程序被用户中断")
    except Exception as e:
        print(f"\n❌ 程序错误: {e}")
    finally:
        # 确保清理
        await client.cleanup()
        print("✅ 资源已清理完毕")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 程序已退出")



#
# async def main():
#     server_script_path = "D:\\Git_PR_Practice\\MCP_Server\\server.py"
#     client = MCPClient()
#     try:
#         await client.connect_to_server(server_script_path)
#         await client.chat_loop()
#     finally:
#         await client.cleanup()
#
#
# if __name__ == "__main__":
#     asyncio.run(main())

