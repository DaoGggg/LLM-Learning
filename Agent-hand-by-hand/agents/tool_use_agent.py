"""
工具使用Agent（Tool Use Agent）实现

Tool Use是指Agent利用外部工具来帮助完成任务的能力。
就像人类使用工具来帮助完成任务一样，Agent也可以使用工具来提升自己的决策和执行能力。

核心思路：
1. 理解用户意图，判断是否需要使用工具
2. 识别需要使用的工具
3. 调用工具执行
4. 解析工具结果
5. 基于工具结果生成最终响应
"""

from typing import List, Dict, Optional, Any, Tuple
from common.llm_client import LLMClientBase, Message, create_llm_client
from common.agent_base import AgentBase
from common.tool import ToolBase, ToolResult, DEFAULT_TOOLS, create_tool


class ToolUseAgent(AgentBase):
    """
    工具使用Agent - 能够调用外部工具的智能代理

    Tool Use Agent的工作流程：
    1. 接收用户输入
    2. 分析是否需要使用工具
    3. 选择合适的工具
    4. 调用工具并获取结果
    5. 解析工具结果
    6. 生成最终响应

    使用示例:
        llm = create_llm_client("mock")
        agent = ToolUseAgent(name="工具Agent", llm_client=llm)
        agent.register_tool(CalculatorTool())
        response = agent.run("计算 2 + 3 * 4")
    """

    def __init__(
        self,
        name: str = "工具Agent",
        llm_client: LLMClientBase = None,
        max_tool_calls: int = 5
    ):
        """
        初始化工具使用Agent

        参数:
            name: Agent名称
            llm_client: LLM客户端实例
            max_tool_calls: 单次交互中最大工具调用次数
        """
        if llm_client is None:
            llm_client = create_llm_client("mock")

        super().__init__(name, llm_client)

        self.max_tool_calls = max_tool_calls
        self.tools: Dict[str, ToolBase] = {}
        self.tool_call_history: List[dict] = []

        self._setup_system_prompt()

    def _setup_system_prompt(self) -> None:
        """设置系统提示词（清除旧的并添加新的）"""
        # 先清除已有的系统消息
        self.history = [msg for msg in self.history if msg.role != "system"]

        tool_descriptions = self._get_tool_descriptions()

        system_prompt = f"""你是一个能够使用工具的智能助手。

你可以使用以下工具来帮助你完成任务：
{tool_descriptions}

使用工具的规则：
1. 只有在确实需要时才使用工具
2. 每次只调用一个工具
3. 仔细解析工具返回的结果
4. 基于工具结果给出最终回答

当你需要使用工具时，请按照以下格式回复：
[TOOL_CALL]
工具名称: <工具名称>
参数: <JSON格式的参数>
[/TOOL_CALL]

当你不需要使用工具时，直接给出回答。"""

        self.add_system_prompt(system_prompt)

    def _get_tool_descriptions(self) -> str:
        """
        获取所有已注册工具的描述

        返回:
            工具描述字符串
        """
        if not self.tools:
            return "（暂无工具可用）"

        descriptions = []
        for name, tool in self.tools.items():
            param_desc = []
            for param_name, param in tool.parameters.items():
                required_str = "（必需）" if param.required else ""
                param_desc.append(f"  - {param_name}: {param.type.__name__} {required_str}")

            tool_desc = f"- {name}: {tool.description}"
            if param_desc:
                tool_desc += "\n" + "\n".join(param_desc)

            descriptions.append(tool_desc)

        return "\n".join(descriptions)

    def register_tool(self, tool: ToolBase) -> None:
        """
        注册工具

        参数:
            tool: 工具实例
        """
        self.tools[tool.name] = tool

        # 更新系统提示词
        self._setup_system_prompt()

    def register_tools(self, tools: List[ToolBase]) -> None:
        """
        批量注册工具

        参数:
            tools: 工具实例列表
        """
        for tool in tools:
            self.register_tool(tool)

    def remove_tool(self, tool_name: str) -> bool:
        """
        移除工具

        参数:
            tool_name: 工具名称

        返回:
            是否成功移除
        """
        if tool_name in self.tools:
            del self.tools[tool_name]
            self._setup_system_prompt()
            return True
        return False

    def _parse_tool_call(self, text: str) -> Optional[Tuple[str, Dict[str, Any]]]:
        """
        解析工具调用指令

        参数:
            text: 包含工具调用的文本

        返回:
            (工具名称, 参数字典) 或 None
        """
        import re
        import json

        # 匹配 [TOOL_CALL]...[/TOOL_CALL] 块
        pattern = r'\[TOOL_CALL\]\s*工具名称:\s*(\w+)\s*参数:\s*(\{.*?\})\s*\[/TOOL_CALL\]'
        match = re.search(pattern, text, re.DOTALL)

        if match:
            tool_name = match.group(1)
            params_str = match.group(2)

            try:
                params = json.loads(params_str)
                return tool_name, params
            except json.JSONDecodeError:
                return None

        return None

    def _execute_tool(self, tool_name: str, params: Dict[str, Any]) -> ToolResult:
        """
        执行工具调用

        参数:
            tool_name: 工具名称
            params: 参数字典

        返回:
            工具执行结果
        """
        if tool_name not in self.tools:
            return ToolResult(
                success=False,
                content=None,
                error=f"未知工具: {tool_name}"
            )

        tool = self.tools[tool_name]
        result = tool.execute(**params)

        # 记录工具调用历史
        self.tool_call_history.append({
            "tool": tool_name,
            "params": params,
            "result": result
        })

        return result

    def run(self, user_input: str) -> dict:
        """
        执行工具使用Agent的核心逻辑

        参数:
            user_input: 用户输入

        返回:
            包含以下字段的字典：
            - response: 最终响应
            - tool_calls: 工具调用列表
            - tool_results: 工具执行结果列表
        """
        self.tool_call_history = []
        self.add_user_message(user_input)

        # 初始LLM调用
        self.set_status("thinking")
        response = self.call_llm(self.history)

        tool_calls = []
        tool_results = []

        # 尝试解析和执行工具调用
        for _ in range(self.max_tool_calls):
            tool_call = self._parse_tool_call(response)

            if tool_call is None:
                # 没有工具调用，结束
                break

            tool_name, params = tool_call
            tool_calls.append({"tool": tool_name, "params": params})

            # 执行工具
            result = self._execute_tool(tool_name, params)
            tool_results.append(result)

            if not result.success:
                # 工具执行失败，直接给出最终响应
                self.add_assistant_message(response)
                self.set_status("finished")
                return {
                    "response": response,
                    "tool_calls": tool_calls,
                    "tool_results": tool_results,
                    "error": result.error
                }

            # 将工具结果反馈给LLM
            tool_feedback = f"""
[TOOL_RESULT]
工具名称: {tool_name}
执行结果: {result.content}
[/TOOL_RESULT]

请基于工具结果给出最终回答。
"""

            self.add_assistant_message(response)
            self.add_user_message(tool_feedback)

            # 再次调用LLM
            response = self.call_llm(self.history)

        self.add_assistant_message(response)
        self.set_status("finished")

        return {
            "response": response,
            "tool_calls": tool_calls,
            "tool_results": tool_results
        }

    def get_available_tools(self) -> List[str]:
        """
        获取可用工具列表

        返回:
            工具名称列表
        """
        return list(self.tools.keys())


class ReActAgent(AgentBase):
    """
    ReAct Agent - 推理与行动结合的Agent

    ReAct（Reasoning and Acting）是一种结合推理和行动的方法论。
    核心思想是：在执行行动的同时进行推理，通过推理指导行动。

    工作模式：
    Thought -> Action -> Observation -> Thought -> Action -> ...

    这是Tool Use Agent的更高级实现，强调显式的推理过程。
    """

    def __init__(
        self,
        name: str = "ReActAgent",
        llm_client: LLMClientBase = None,
        max_cycles: int = 10
    ):
        """
        初始化ReAct Agent

        参数:
            name: Agent名称
            llm_client: LLM客户端实例
            max_cycles: 最大思考-行动循环次数
        """
        if llm_client is None:
            llm_client = create_llm_client("mock")

        super().__init__(name, llm_client)

        self.max_cycles = max_cycles
        self.tools: Dict[str, ToolBase] = {}
        self.execution_history: List[dict] = []

        self._setup_system_prompt()

    def _setup_system_prompt(self) -> None:
        """设置系统提示词（清除旧的并添加新的）"""
        # 先清除已有的系统消息
        self.history = [msg for msg in self.history if msg.role != "system"]

        tool_info = []
        for name, tool in self.tools.items():
            param_info = ", ".join(f"{p}" for p in tool.parameters.keys())
            tool_info.append(f"- {name}({param_info})")

        tools_str = "\n".join(tool_info) if tool_info else "（无可用工具）"

        system_prompt = f"""你是一个采用ReAct（推理-行动）模式的智能助手。

工作流程：
1. 先给出思考（Thought），说明你的推理过程
2. 然后决定行动（Action），如需使用工具请按格式调用
3. 观察结果（Observation），根据反馈继续推理
4. 重复直到任务完成

可用工具：
{tools_str}

回复格式：
Thought: <你的思考>
Action: <行动内容，如需使用工具则为 [TOOL_CALL]工具名:参数[/TOOL_CALL]，否则为 None>
"""

        self.add_system_prompt(system_prompt)

    def register_tool(self, tool: ToolBase) -> None:
        """注册工具"""
        self.tools[tool.name] = tool
        self._setup_system_prompt()

    def register_tools(self, tools: List[ToolBase]) -> None:
        """批量注册工具"""
        for tool in tools:
            self.register_tool(tool)

    def _parse_action(self, text: str) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
        """
        解析行动指令

        参数:
            text: 响应文本

        返回:
            (行动类型, 行动内容)
        """
        import re
        import json

        # 匹配工具调用 - 支持多种格式
        # 格式1: [TOOL_CALL]tool_name: {...}[/TOOL_CALL]
        # 格式2: [TOOL_CALL]\n工具名称: tool_name\n参数: {...}\n[/TOOL_CALL]
        patterns = [
            r'\[TOOL_CALL\]\s*(\w+):\s*(\{.*?\})\s*\[/TOOL_CALL\]',
            r'工具名称:\s*(\w+)\s*参数:\s*(\{.*?\})',
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.DOTALL)
            if match:
                tool_name = match.group(1)
                params_str = match.group(2)
                try:
                    params = json.loads(params_str)
                    return "tool_call", (tool_name, params)
                except json.JSONDecodeError:
                    pass

        # 检查是否没有行动
        if "Action: None" in text or "Action: 无" in text or "行动: 无" in text:
            return "none", None

        return "unknown", None

    def run(self, user_input: str) -> dict:
        """
        执行ReAct Agent

        参数:
            user_input: 用户输入

        返回:
            执行结果字典
        """
        self.execution_history = []
        self.add_user_message(user_input)

        observation = ""
        final_response = ""

        for cycle in range(self.max_cycles):
            # 构建包含观察的上下文
            if observation:
                context = f"{user_input}\n\n之前的行动结果: {observation}"
            else:
                context = user_input

            self.add_user_message(context)

            # 调用LLM
            self.set_status(f"thinking_cycle_{cycle + 1}")
            response = self.call_llm(self.history, temperature=0.7)

            # 记录思考
            self.execution_history.append({
                "cycle": cycle + 1,
                "thought": response,
                "action": None,
                "observation": None
            })

            # 解析行动
            action_type, action_content = self._parse_action(response)

            if action_type == "none":
                # 无需更多行动，结束
                final_response = response
                break

            if action_type == "tool_call":
                tool_name, params = action_content

                # 执行工具
                result = self._execute_tool(tool_name, params)

                # 更新观察
                observation = f"工具 {tool_name} 执行结果: {result.content}"

                if result.success:
                    observation += "（成功）"
                else:
                    observation += f"（失败: {result.error}）"

                # 更新历史
                self.execution_history[-1]["action"] = {
                    "tool": tool_name,
                    "params": params
                }
                self.execution_history[-1]["observation"] = observation

                # 继续循环
                self.add_assistant_message(response)
                continue

            # 未知行动类型，假设是最终回答
            final_response = response
            break

        self.add_assistant_message(final_response)
        self.set_status("finished")

        return {
            "response": final_response,
            "execution_history": self.execution_history,
            "num_cycles": len(self.execution_history)
        }

    def _execute_tool(self, tool_name: str, params: Dict[str, Any]) -> ToolResult:
        """
        执行工具

        参数:
            tool_name: 工具名称
            params: 参数

        返回:
            执行结果
        """
        if tool_name not in self.tools:
            return ToolResult(
                success=False,
                content=None,
                error=f"未知工具: {tool_name}"
            )

        tool = self.tools[tool_name]
        return tool.execute(**params)


# 便捷函数
def create_tool_use_agent(
    name: str = "工具Agent",
    provider: str = "mock",
    **kwargs
) -> ToolUseAgent:
    """
    创建Tool Use Agent的便捷函数

    参数:
        name: Agent名称
        provider: LLM提供商
        **kwargs: 其他参数

    返回:
        ToolUseAgent实例
    """
    llm_client = create_llm_client(provider, **kwargs)
    return ToolUseAgent(name=name, llm_client=llm_client)


def create_react_agent(
    name: str = "ReActAgent",
    provider: str = "mock",
    **kwargs
) -> ReActAgent:
    """
    创建ReAct Agent的便捷函数

    参数:
        name: Agent名称
        provider: LLM提供商
        **kwargs: 其他参数

    返回:
        ReActAgent实例
    """
    llm_client = create_llm_client(provider, **kwargs)
    return ReActAgent(name=name, llm_client=llm_client)
