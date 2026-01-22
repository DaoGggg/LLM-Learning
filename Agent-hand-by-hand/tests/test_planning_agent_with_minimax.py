"""
规划Agent测试用例 - 使用 MiniMax API

测试Planning Agent的各项功能：
1. 任务分解
2. 依赖关系分析
3. 子任务执行
4. 结果综合

前置要求：
1. 设置环境变量 MINIMAX_API_KEY 或在项目根目录创建 .env 文件
2. 安装必要依赖: pip install python-dotenv requests
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
    pass

from common.llm_client import create_llm_client
from agents.planning_agent import (
    PlanningAgent,
    HierarchicalPlannerAgent,
    create_planning_agent,
    create_hierarchical_planner_agent
)


def check_api_key():
    """检查API Key是否设置"""
    api_key = os.environ.get("MINIMAX_API_KEY")
    if not api_key:
        return False
    if api_key == "your-api-key-here":
        return False
    return True


class TestPlanningAgentWithMiniMax:
    """PlanningAgent测试类 - 使用MiniMax真实API"""

    @pytest.fixture(autouse=True)
    def setup_api_key(self):
        """检查API Key是否设置"""
        if not check_api_key():
            pytest.skip("需要设置环境变量 MINIMAX_API_KEY 才能运行此测试")

    def test_task_decomposition(self):
        """测试任务分解功能"""
        llm = create_llm_client(provider="minimax")
        agent = PlanningAgent(name="规划测试", llm_client=llm)

        result = agent.run("请分析人工智能的发展现状")

        assert "response" in result
        assert "task_plan" in result
        assert "subtask_results" in result
        print(f"分解任务数: {result['num_subtasks']}")
        print(f"计划摘要: {agent.get_plan_summary()}")

    def test_multi_level_task(self):
        """测试多层级任务"""
        llm = create_llm_client(provider="minimax")
        agent = PlanningAgent(name="复杂规划", llm_client=llm, max_subtasks=5)

        result = agent.run("如何开发一个完整的移动应用？")

        assert "response" in result
        assert result["num_subtasks"] >= 0
        print(f"子任务数: {result['num_subtasks']}")


class TestHierarchicalPlannerAgentWithMiniMax:
    """HierarchicalPlannerAgent测试类 - 使用MiniMax真实API"""

    @pytest.fixture(autouse=True)
    def setup_api_key(self):
        """检查API Key是否设置"""
        if not check_api_key():
            pytest.skip("需要设置环境变量 MINIMAX_API_KEY 才能运行此测试")

    def test_hierarchical_decomposition(self):
        """测试层级分解"""
        llm = create_llm_client(provider="minimax")
        agent = HierarchicalPlannerAgent(name="层级规划", llm_client=llm)

        result = agent.run("请规划一个软件项目的开发流程")

        assert "response" in result
        assert "task_hierarchy" in result
        assert "execution_log" in result
        print(f"任务层级数: {len(result['task_hierarchy'])}")
        print(f"执行日志数: {len(result['execution_log'])}")


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
                Message(role="user", content="请用一句话介绍规划的意义")
            ],
            temperature=0.7
        )

        response = llm.chat(request)

        assert response.choices[0].message.content is not None
        print(f"回复: {response.choices[0].message.content}")


if __name__ == "__main__":
    if not check_api_key():
        print("请先设置环境变量: set MINIMAX_API_KEY=your-api-key")
    else:
        pytest.main([__file__, "-v"])
