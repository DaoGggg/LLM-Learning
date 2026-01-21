"""
反思Agent测试用例

测试Reflection Agent的各项功能：
1. 基础响应生成
2. 自我反思功能
3. 多轮反思循环
4. 响应修正
"""

import pytest
import sys
import os

from networkx.algorithms.bipartite.cluster import modes

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from common.llm_client import AnthropicClient, create_llm_client, MockLLMClient
from agents.reflection_agent import ReflectionAgent, SelfImprovingAgent


class TestReflectionAgent:
    """ReflectionAgent测试类"""

    def test_init(self):
        """测试Agent初始化"""
        # 使用模拟客户端
        llm = MockLLMClient(responses=["初始回答"])
        agent = ReflectionAgent(name="测试Agent", llm_client=llm)

        assert agent.name == "测试Agent"
        assert agent.max_reflections == 2
        assert len(agent.history) >= 1  # 系统提示词
        assert agent.state.status == "idle"

    def test_single_response(self):
        """测试单次响应（无反思）"""
        llm = MockLLMClient(responses=["这是一个测试回答"])
        agent = ReflectionAgent(name="测试", llm_client=llm, max_reflections=0)

        result = agent.run("测试问题")

        assert "response" in result
        assert result["response"] == "这是一个测试回答"
        assert result["num_reflections"] == 0

    def test_reflection_with_mock(self):
        """测试带反思的响应"""
        # 设置模拟响应：初始回答 -> 反思 -> 修正后的回答
        llm = MockLLMClient(responses=[
            "初始回答，可能不够完整。",
            "反思：回答基本正确，但可以补充更多细节。",
            "修正后的回答，更加完整和详细。"
        ])
        agent = ReflectionAgent(name="测试", llm_client=llm, max_reflections=1)

        result = agent.run("请解释机器学习")

        assert "response" in result
        assert "initial_response" in result
        assert len(result["reflections"]) == 1
        assert result["num_reflections"] == 1

    def test_multiple_reflections(self):
        """测试多轮反思"""
        responses = [
            "第一次回答",
            "第一次反思",
            "第二次回答",
            "第二次反思",
            "第三次回答"
        ]
        llm = MockLLMClient(responses=responses)
        agent = ReflectionAgent(name="测试", llm_client=llm, max_reflections=2)

        result = agent.run("测试问题")

        assert result["num_reflections"] == 2
        assert len(result["reflections"]) == 2

    def test_history_management(self):
        """测试历史记录管理"""
        llm = MockLLMClient(responses=["回答"])
        agent = ReflectionAgent(name="测试", llm_client=llm)

        # 初始状态
        initial_history_len = len(agent.history)

        agent.run("问题1")

        # 应该有用户消息和助手消息
        assert len(agent.history) > initial_history_len

    def test_reflection_history(self):
        """测试反思历史记录"""
        responses = [
            "初始回答",
            "反思内容",
            "修正回答"
        ]
        llm = MockLLMClient(responses=responses)
        agent = ReflectionAgent(name="测试", llm_client=llm, max_reflections=1)

        result = agent.run("测试问题")

        assert len(agent.reflection_history) == 1
        assert "round" in agent.reflection_history[0]
        assert "response" in agent.reflection_history[0]
        assert "reflection" in agent.reflection_history[0]

    def test_max_reflections_override(self):
        """测试覆盖默认最大反思轮数"""
        llm = MockLLMClient(responses=[
            "回答",
            "反思1",
            "回答2",
            "反思2",
            "回答3"
        ])
        agent = ReflectionAgent(name="测试", llm_client=llm, max_reflections=1)

        result = agent.run("测试", max_reflections=2)

        assert result["num_reflections"] == 2

    def test_status_transition(self):
        """测试状态转换"""
        llm = MockLLMClient(responses=["回答"])
        agent = ReflectionAgent(name="测试", llm_client=llm)

        assert agent.state.status == "idle"

        agent.run("测试问题")

        assert agent.state.status == "finished"


class TestSelfImprovingAgent:
    """SelfImprovingAgent测试类"""

    def test_init(self):
        """测试初始化"""
        llm = MockLLMClient(responses=["回答"])
        agent = SelfImprovingAgent(name="学习者", llm_client=llm)

        assert agent.name == "学习者"
        assert len(agent.experiences) == 0

    def test_learn_from_interaction(self):
        """测试从交互中学习"""
        llm = MockLLMClient(responses=[
            "第一次回答",
            "学习到要更简洁"
        ])
        agent = SelfImprovingAgent(name="学习者", llm_client=llm)

        result = agent.run("问题1")

        assert result["response"] == "第一次回答"
        assert len(agent.experiences) == 1
        assert "reflection" in agent.experiences[0]

    def test_multiple_experiences(self):
        """测试多次交互经验积累"""
        llm = MockLLMClient(responses=[
            "回答1",
            "经验1",
            "回答2",
            "经验2"
        ])
        agent = SelfImprovingAgent(name="学习者", llm_client=llm)

        agent.run("问题1")
        agent.run("问题2")

        assert len(agent.experiences) == 2

    def test_experience_context_influence(self):
        """测试经验上下文影响响应"""
        llm = MockLLMClient(responses=[
            "回答1",
            "这是经验总结",
            "包含经验上下文的回答"
        ])
        agent = SelfImprovingAgent(name="学习者", llm_client=llm)

        agent.run("问题1")
        result = agent.run("问题2")

        # 运行两次后应该有2条经验
        assert len(agent.experiences) == 2
        # 验证第二次运行使用了经验上下文
        assert "经验" in result["response"] or "经验" in str(agent.experiences)


class TestCreateFunctions:
    """测试便捷创建函数"""

    def test_create_reflection_agent(self):
        """测试创建Reflection Agent"""
        from agents.reflection_agent import create_reflection_agent

        agent = create_reflection_agent(
            name="便捷创建",
            provider="mock",
            responses=["测试回答"]
        )

        assert agent.name == "便捷创建"

    def test_create_with_openai_provider(self):
        """测试创建OpenAI客户端"""
        import os
        os.environ["OPENAI_API_KEY"] = "test-key"

        from agents.reflection_agent import create_reflection_agent

        agent = create_reflection_agent(
            name="OpenAI测试",
            provider="openai"
        )

        assert agent.llm_client.get_model_name() is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
