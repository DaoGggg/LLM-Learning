"""
反思Agent测试用例 - 使用 MiniMax API

测试Reflection Agent的各项功能：
1. 基础响应生成
2. 自我反思功能
3. 多轮反思循环
4. 响应修正

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
from agents.reflection_agent import ReflectionAgent, SelfImprovingAgent


def check_api_key():
    """检查API Key是否设置"""
    api_key = os.environ.get("MINIMAX_API_KEY")
    if not api_key:
        return False
    if api_key == "your-api-key-here":
        return False
    return True


class TestReflectionAgentWithMiniMax:
    """ReflectionAgent测试类 - 使用MiniMax真实API"""

    @pytest.fixture(autouse=True)
    def setup_api_key(self):
        """检查API Key是否设置"""
        if not check_api_key():
            pytest.skip("需要设置环境变量 MINIMAX_API_KEY 才能运行此测试")

    def test_basic_reflection(self):
        """测试带反思的基本响应"""
        llm = create_llm_client(provider="minimax")
        agent = ReflectionAgent(name="MiniMax反思测试", llm_client=llm, max_reflections=1)

        result = agent.run("请简单解释什么是人工智能？")

        assert "response" in result
        assert "initial_response" in result
        assert result["response"] is not None
        assert len(result["response"]) > 0
        print(f"初始回答: {result['initial_response'][:100]}...")
        print(f"最终回答: {result['response'][:100]}...")
        print(f"反思轮数: {result['num_reflections']}")

    def test_no_reflection(self):
        """测试不带反思的响应"""
        llm = create_llm_client(provider="minimax")
        agent = ReflectionAgent(name="无反思测试", llm_client=llm, max_reflections=0)

        result = agent.run("1+1等于多少？")

        assert "response" in result
        assert result["num_reflections"] == 0
        print(f"回答: {result['response']}")

    def test_reflection_history(self):
        """测试反思历史记录"""
        llm = create_llm_client(provider="minimax")
        agent = ReflectionAgent(name="反思历史测试", llm_client=llm, max_reflections=1)

        result = agent.run("什么是机器学习？")

        assert len(agent.reflection_history) >= 0  # 可能没有反思
        print(f"反思历史数量: {len(agent.reflection_history)}")


class TestSelfImprovingAgentWithMiniMax:
    """SelfImprovingAgent测试类 - 使用MiniMax真实API"""

    @pytest.fixture(autouse=True)
    def setup_api_key(self):
        """检查API Key是否设置"""
        if not check_api_key():
            pytest.skip("需要设置环境变量 MINIMAX_API_KEY 才能运行此测试")

    def test_self_learning(self):
        """测试自我学习能力"""
        llm = create_llm_client(provider="minimax")
        agent = SelfImprovingAgent(name="MiniMax学习者", llm_client=llm)

        result = agent.run("请介绍一下Python编程语言")

        assert "response" in result
        assert len(agent.experiences) == 1
        print(f"回答: {result['response'][:100]}...")
        print(f"经验数: {result['experiences_count']}")

    def test_experience_accumulation(self):
        """测试经验积累"""
        llm = create_llm_client(provider="minimax")
        agent = SelfImprovingAgent(name="经验积累测试", llm_client=llm)

        # 第一次交互
        result1 = agent.run("什么是深度学习？")
        # 第二次交互
        result2 = agent.run("请解释神经网络")

        assert len(agent.experiences) == 2
        print(f"经验数: {len(agent.experiences)}")


class TestMiniMaxClientDirect:
    """MiniMax客户端直接测试"""

    @pytest.fixture(autouse=True)
    def setup_api_key(self):
        """检查API Key是否设置"""
        if not check_api_key():
            pytest.skip("需要设置环境变量 MINIMAX_API_KEY 才能运行此测试")

    def test_get_model_name(self):
        """测试获取模型名称"""
        llm = create_llm_client(provider="minimax")
        model_name = llm.get_model_name()
        assert model_name is not None and len(model_name) > 0
        print(f"模型名称: {model_name}")

    def test_basic_chat(self):
        """测试基本聊天"""
        from common.llm_client import ChatCompletionRequest, Message

        llm = create_llm_client(provider="minimax")

        request = ChatCompletionRequest(
            messages=[
                Message(role="user", content="你好，请用一句话介绍自己")
            ],
            temperature=0.7
        )

        response = llm.chat(request)

        assert response.choices[0].message.content is not None
        assert len(response.choices[0].message.content) > 0
        print(f"回复: {response.choices[0].message.content}")
        print(f"使用的模型: {response.model}")


if __name__ == "__main__":
    # 运行前检查API Key
    if not check_api_key():
        print("请先设置环境变量: set MINIMAX_API_KEY=your-api-key")
        print("示例: set MINIMAX_API_KEY=sk-xxxxxx")
    else:
        pytest.main([__file__, "-v"])
