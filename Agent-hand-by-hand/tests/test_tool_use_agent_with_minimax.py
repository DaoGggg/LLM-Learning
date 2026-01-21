"""
工具使用Agent测试用例 - 使用 MiniMax API

测试Tool Use Agent的各项功能：
1. 工具注册
2. 工具调用
3. 工具结果处理
4. ReAct模式

前置要求：
1. 设置环境变量 MINIMAX_API_KEY 或在项目根目录创建 .env 文件
2. 安装必要依赖: pip install openai python-dotenv requests
"""

import pytest
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 尝试加载 .env 文件
try:
    from dotenv import load_dotenv
    env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
    if os.path.exists(env_path):
        load_dotenv(env_path)
except ImportError:
    pass  # 如果没有安装 python-dotenv，跳过

from common.llm_client import create_llm_client
from common.tool import (
    CalculatorTool,
    DateTimeTool,
    ToolResult,
    create_tool
)
from agents.tool_use_agent import ToolUseAgent, ReActAgent


def check_api_key():
    """检查API Key是否设置"""
    api_key = os.environ.get("MINIMAX_API_KEY")
    if not api_key:
        return False
    if api_key == "your-api-key-here":
        return False
    return True


class TestToolUseAgentWithMiniMax:
    """ToolUseAgent测试类 - 使用MiniMax真实API"""

    @pytest.fixture(autouse=True)
    def setup_api_key(self):
        """检查API Key是否设置"""
        if not check_api_key():
            pytest.skip("需要设置环境变量 MINIMAX_API_KEY 才能运行此测试")

    def test_basic_conversation(self):
        """测试基本对话功能"""
        llm = create_llm_client(provider="minimax")
        agent = ToolUseAgent(name="对话测试", llm_client=llm)

        result = agent.run("请介绍一下你自己")

        assert "response" in result
        assert result["response"] is not None
        assert len(result["response"]) > 0
        print(f"响应: {result['response'][:100]}...")

    def test_with_datetime_tool(self):
        """测试日期时间工具"""
        llm = create_llm_client(provider="minimax")
        agent = ToolUseAgent(name="时间测试", llm_client=llm)
        agent.register_tool(DateTimeTool())

        result = agent.run("现在是什么时间？")

        assert "response" in result
        print(f"响应: {result['response'][:100]}...")


class TestReActAgentWithMiniMax:
    """ReActAgent测试类 - 使用MiniMax真实API"""

    @pytest.fixture(autouse=True)
    def setup_api_key(self):
        """检查API Key是否设置"""
        if not check_api_key():
            pytest.skip("需要设置环境变量 MINIMAX_API_KEY 才能运行此测试")

    def test_react_basic_conversation(self):
        """测试ReAct基本对话"""
        llm = create_llm_client(provider="minimax")
        agent = ReActAgent(name="ReAct对话测试", llm_client=llm)

        result = agent.run("请解释什么是人工智能？")

        assert "response" in result
        assert result["response"] is not None
        print(f"响应: {result['response'][:100]}...")
        print(f"执行轮数: {result['num_cycles']}")


class TestToolsWithMiniMax:
    """工具类测试 - 使用MiniMax验证工具定义"""

    @pytest.fixture(autouse=True)
    def setup_api_key(self):
        """检查API Key是否设置"""
        if not check_api_key():
            pytest.skip("需要设置环境变量 MINIMAX_API_KEY 才能运行此测试")

    def test_tool_schema_generation(self):
        """测试工具Schema生成"""
        calculator = CalculatorTool()
        schema = calculator.to_schema()

        assert schema["type"] == "function"
        assert "function" in schema
        assert schema["function"]["name"] == "calculator"
        print(f"工具Schema: {schema}")

    def test_create_tool_factory(self):
        """测试工具工厂函数"""
        tool = create_tool("calculator")
        assert isinstance(tool, CalculatorTool)

        tool = create_tool("datetime")
        assert isinstance(tool, DateTimeTool)


class TestMiniMaxClient:
    """MiniMax客户端直接测试"""

    @pytest.fixture(autouse=True)
    def setup_api_key(self):
        """检查API Key是否设置"""
        if not check_api_key():
            pytest.skip("需要设置环境变量 MINIMAX_API_KEY 才能运行此测试")

    def test_minimax_basic_chat(self):
        """测试MiniMax基本聊天"""
        from common.llm_client import ChatCompletionRequest, Message

        llm = create_llm_client(provider="minimax")

        request = ChatCompletionRequest(
            messages=[
                Message(role="user", content="你好，请简单介绍一下自己")
            ],
            temperature=0.7
        )

        response = llm.chat(request)

        assert response.choices[0].message.content is not None
        assert len(response.choices[0].message.content) > 0
        print(f"回复: {response.choices[0].message.content[:100]}...")

    def test_minimax_with_system_prompt(self):
        """测试带系统提示的聊天"""
        from common.llm_client import ChatCompletionRequest, Message

        llm = create_llm_client(provider="minimax")

        request = ChatCompletionRequest(
            messages=[
                Message(role="system", content="你是一个诗人，用优美的语言回答问题"),
                Message(role="user", content="描写一下春天")
            ],
            temperature=0.8
        )

        response = llm.chat(request)

        assert response.choices[0].message.content is not None
        print(f"诗歌回复: {response.choices[0].message.content[:100]}...")


if __name__ == "__main__":
    # 运行前检查API Key
    if not check_api_key():
        print("请先设置环境变量: set MINIMAX_API_KEY=your-api-key")
        print("示例: set MINIMAX_API_KEY=sk-xxxxxx")
    else:
        pytest.main([__file__, "-v"])
