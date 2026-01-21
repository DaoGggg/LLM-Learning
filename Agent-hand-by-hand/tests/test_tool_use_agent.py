"""
工具使用Agent测试用例

测试Tool Use Agent的各项功能：
1. 工具注册
2. 工具调用
3. 工具结果处理
4. ReAct模式
"""

import pytest
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from common.llm_client import MockLLMClient
from common.tool import (
    CalculatorTool,
    SearchTool,
    FileReaderTool,
    FileWriterTool,
    DateTimeTool,
    ToolResult,
    create_tool
)
from agents.tool_use_agent import ToolUseAgent, ReActAgent


class TestToolUseAgent:
    """ToolUseAgent测试类"""

    def test_init(self):
        """测试初始化"""
        llm = MockLLMClient(responses=["不需要工具"])
        agent = ToolUseAgent(name="工具Agent", llm_client=llm)

        assert agent.name == "工具Agent"
        assert len(agent.tools) == 0
        assert agent.max_tool_calls == 5

    def test_register_single_tool(self):
        """测试注册单个工具"""
        llm = MockLLMClient(responses=["回答"])
        agent = ToolUseAgent(name="测试", llm_client=llm)

        calculator = CalculatorTool()
        agent.register_tool(calculator)

        assert "calculator" in agent.tools
        assert agent.tools["calculator"].name == "calculator"

    def test_register_multiple_tools(self):
        """测试批量注册工具"""
        llm = MockLLMClient(responses=["回答"])
        agent = ToolUseAgent(name="测试", llm_client=llm)

        tools = [CalculatorTool(), SearchTool(), DateTimeTool()]
        agent.register_tools(tools)

        assert len(agent.tools) == 3

    def test_remove_tool(self):
        """测试移除工具"""
        llm = MockLLMClient(responses=["回答"])
        agent = ToolUseAgent(name="测试", llm_client=llm)

        agent.register_tool(CalculatorTool())
        assert "calculator" in agent.tools

        result = agent.remove_tool("calculator")
        assert result is True
        assert "calculator" not in agent.tools

    def test_remove_nonexistent_tool(self):
        """测试移除不存在的工具"""
        llm = MockLLMClient(responses=["回答"])
        agent = ToolUseAgent(name="测试", llm_client=llm)

        result = agent.remove_tool("unknown_tool")
        assert result is False

    def test_no_tool_call(self):
        """测试无需工具的场景"""
        llm = MockLLMClient(responses=["这是一个普通回答，不需要工具"])
        agent = ToolUseAgent(name="测试", llm_client=llm)

        result = agent.run("你好，请介绍一下你自己")

        assert "response" in result
        assert len(result["tool_calls"]) == 0
        assert len(result["tool_results"]) == 0

    def test_tool_call_with_calculator(self):
        """测试使用计算器工具"""
        # 设置模拟响应：需要计算 -> 收到结果 -> 最终回答
        llm = MockLLMClient(responses=[
            """[TOOL_CALL]
工具名称: calculator
参数: {"expression": "2 + 3 * 4"}
[/TOOL_CALL]""",
            "根据计算结果，2 + 3 * 4 = 14"
        ])
        agent = ToolUseAgent(name="测试", llm_client=llm)
        agent.register_tool(CalculatorTool())

        result = agent.run("计算 2 + 3 * 4")

        assert "response" in result
        assert len(result["tool_calls"]) == 1
        assert result["tool_calls"][0]["tool"] == "calculator"
        assert len(result["tool_results"]) == 1

    def test_multiple_tool_calls(self):
        """测试多次工具调用"""
        responses = [
            """[TOOL_CALL]
工具名称: datetime
参数: {}
[/TOOL_CALL]""",
            """[TOOL_CALL]
工具名称: calculator
参数: {"expression": "10 / 2"}
[/TOOL_CALL]""",
            "根据日期和计算结果给出回答"
        ]
        llm = MockLLMClient(responses=responses)
        agent = ToolUseAgent(name="测试", llm_client=llm)
        agent.register_tool(DateTimeTool())
        agent.register_tool(CalculatorTool())

        result = agent.run("获取时间并计算")

        assert len(result["tool_calls"]) == 2

    def test_failed_tool_call(self):
        """测试工具调用失败"""
        responses = [
            """[TOOL_CALL]
工具名称: calculator
参数: {"expression": "2 + 2"}
[/TOOL_CALL]""",
            "计算失败，给出备用回答"
        ]
        llm = MockLLMClient(responses=[
            """[TOOL_CALL]
工具名称: unknown_tool
参数: {"param": "value"}
[/TOOL_CALL]""",
            "未知工具，给出直接回答"
        ])
        agent = ToolUseAgent(name="测试", llm_client=llm)
        # 不注册任何工具

        result = agent.run("使用某个工具")

        assert len(result["tool_calls"]) == 1
        assert result["error"] is not None

    def test_get_available_tools(self):
        """测试获取可用工具列表"""
        llm = MockLLMClient(responses=["回答"])
        agent = ToolUseAgent(name="测试", llm_client=llm)

        agent.register_tool(CalculatorTool())
        agent.register_tool(SearchTool())

        tools = agent.get_available_tools()

        assert "calculator" in tools
        assert "search" in tools
        assert len(tools) == 2


class TestReActAgent:
    """ReActAgent测试类"""

    def test_init(self):
        """测试初始化"""
        llm = MockLLMClient(responses=["回答"])
        agent = ReActAgent(name="ReAct测试", llm_client=llm)

        assert agent.name == "ReAct测试"
        assert agent.max_cycles == 10

    def test_register_tool(self):
        """测试工具注册"""
        llm = MockLLMClient(responses=["回答"])
        agent = ReActAgent(name="测试", llm_client=llm)

        agent.register_tool(CalculatorTool())

        assert "calculator" in agent.tools

    def test_no_action_finish(self):
        """测试无需行动直接结束"""
        llm = MockLLMClient(responses=[
            """Thought: 这是一个简单问题，我可以直接回答
Action: None"""
        ])
        agent = ReActAgent(name="测试", llm_client=llm)

        result = agent.run("你好")

        assert "response" in result
        assert result["num_cycles"] == 1

    def test_react_cycle(self):
        """测试ReAct循环"""
        responses = [
            """Thought: 需要计算
Action: [TOOL_CALL]calculator:{"expression":"5*5"}[/TOOL_CALL]""",
            """Thought: 收到计算结果，25
Action: None"""
        ]
        llm = MockLLMClient(responses=responses)
        agent = ReActAgent(name="测试", llm_client=llm)
        agent.register_tool(CalculatorTool())

        result = agent.run("5乘5等于多少")

        assert result["num_cycles"] == 2
        assert len(result["execution_history"]) == 2

    def test_execution_history(self):
        """测试执行历史记录"""
        responses = [
            """[TOOL_CALL]
工具名称: search
参数: {"query": "Python"}
[/TOOL_CALL]""",
            """根据搜索结果，Python是一种广泛使用的高级编程语言。"""
        ]
        llm = MockLLMClient(responses=responses)
        agent = ReActAgent(name="测试", llm_client=llm)
        agent.register_tool(SearchTool())

        result = agent.run("搜索Python相关信息")

        assert len(result["execution_history"]) == 2

        # 检查第一条记录
        first_cycle = result["execution_history"][0]
        assert "thought" in first_cycle
        assert "action" in first_cycle
        assert first_cycle["action"]["tool"] == "search"
        assert first_cycle["action"]["params"]["query"] == "Python"


class TestTools:
    """工具类测试"""

    def test_calculator_success(self):
        """测试计算器成功计算"""
        calculator = CalculatorTool()
        result = calculator.execute(expression="2 + 3")

        assert result.success is True
        assert result.content == "5"

    def test_calculator_invalid_expression(self):
        """测试计算器非法表达式"""
        calculator = CalculatorTool()
        result = calculator.execute(expression="__import__('os').system('ls')")

        assert result.success is False
        assert result.error is not None

    def test_calculator_error(self):
        """测试计算器错误处理"""
        calculator = CalculatorTool()
        result = calculator.execute(expression="1/0")

        assert result.success is False

    def test_search_tool(self):
        """测试搜索工具"""
        search = SearchTool()
        result = search.execute(query="测试查询")

        assert result.success is True
        assert len(result.content) > 0

    def test_datetime_tool(self):
        """测试日期时间工具"""
        dt = DateTimeTool()
        result = dt.execute()

        assert result.success is True
        assert "-" in result.content  # 格式: YYYY-MM-DD

    def test_file_reader_tool(self):
        """测试文件读取工具"""
        # 先创建测试文件
        test_file = "test_read.txt"
        with open(test_file, 'w', encoding='utf-8') as f:
            f.write("测试内容")

        reader = FileReaderTool()
        result = reader.execute(filepath=test_file)

        assert result.success is True
        assert result.content == "测试内容"

        # 清理
        os.remove(test_file)

    def test_file_writer_tool(self):
        """测试文件写入工具"""
        writer = FileWriterTool()
        result = writer.execute(
            filepath="test_write.txt",
            content="写入的内容"
        )

        assert result.success is True

        # 验证写入
        with open("test_write.txt", 'r', encoding='utf-8') as f:
            content = f.read()
        assert content == "写入的内容"

        # 清理
        os.remove("test_write.txt")

    def test_file_reader_not_found(self):
        """测试文件不存在"""
        reader = FileReaderTool()
        result = reader.execute(filepath="不存在的文件.txt")

        assert result.success is False
        assert "不存在" in result.error

    def test_create_tool(self):
        """测试工具工厂函数"""
        tool = create_tool("calculator")
        assert isinstance(tool, CalculatorTool)

    def test_tool_schema(self):
        """测试工具Schema生成"""
        calculator = CalculatorTool()
        schema = calculator.to_schema()

        assert schema["type"] == "function"
        assert "function" in schema
        assert schema["function"]["name"] == "calculator"


class TestToolUseAgentIntegration:
    """ToolUseAgent集成测试"""

    def test_complete_workflow_with_calculator(self):
        """测试完整工作流程（使用计算器）"""
        responses = [
            """[TOOL_CALL]
工具名称: calculator
参数: {"expression": "(10 + 5) * 2"}
[/TOOL_CALL]""",
            "根据计算，(10 + 5) × 2 = 30，这是一个简单的算术运算。"
        ]
        llm = MockLLMClient(responses=responses)
        agent = ToolUseAgent(name="计算助手", llm_client=llm)
        agent.register_tool(CalculatorTool())

        result = agent.run("计算 (10 + 5) 乘以 2 等于多少")

        # 验证结果
        assert result["response"] is not None
        assert len(result["tool_calls"]) == 1
        assert result["tool_calls"][0]["tool"] == "calculator"
        assert result["tool_calls"][0]["params"]["expression"] == "(10 + 5) * 2"

    def test_multiple_tools_choice(self):
        """测试多工具选择"""
        responses = [
            """[TOOL_CALL]
工具名称: datetime
参数: {}
[/TOOL_CALL]""",
            f"当前时间是{DateTimeTool().execute().content}。"
        ]
        llm = MockLLMClient(responses=responses)
        agent = ToolUseAgent(name="助手", llm_client=llm)
        agent.register_tool(CalculatorTool())
        agent.register_tool(DateTimeTool())

        result = agent.run("现在几点了？")

        assert result["tool_calls"][0]["tool"] == "datetime"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
