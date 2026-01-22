"""
多智能体协作Agent测试用例 - 使用 MiniMax API

测试Multi-agent协作的各项功能：
1. 角色定义和注册
2. 任务分配
3. 顺序执行
4. 结果汇总

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
from agents.multi_agent import (
    MultiAgentCoordinator,
    RoleAgent,
    AgentRole,
    create_multi_agent_coordinator,
    create_software_dev_coordinator,
    create_discussion_roles
)


def check_api_key():
    """检查API Key是否设置"""
    api_key = os.environ.get("MINIMAX_API_KEY")
    if not api_key:
        return False
    if api_key == "your-api-key-here":
        return False
    return True


class TestMultiAgentCoordinatorWithMiniMax:
    """MultiAgentCoordinator测试类 - 使用MiniMax真实API"""

    @pytest.fixture(autouse=True)
    def setup_api_key(self):
        """检查API Key是否设置"""
        if not check_api_key():
            pytest.skip("需要设置环境变量 MINIMAX_API_KEY 才能运行此测试")

    def test_team_discussion(self):
        """测试团队讨论场景"""
        roles = create_discussion_roles()
        coordinator = create_multi_agent_coordinator(
            name="会议讨论",
            roles=roles,
            provider="minimax"
        )

        result = coordinator.run("请讨论人工智能对未来工作的影响")

        assert "response" in result
        assert "role_results" in result
        assert "task_distribution" in result
        print(f"参与角色: {result['roles_executed']}")
        print(f"执行摘要: {coordinator.get_execution_summary()}")

    def test_software_project(self):
        """测试软件开发项目场景"""
        coordinator = create_software_dev_coordinator(
            name="软件开发团队",
            provider="minimax"
        )

        result = coordinator.run("请设计一个电商网站的技术方案")

        assert "response" in result
        assert len(result["roles_executed"]) == 4  # 产品经理、架构师、程序员、测试工程师
        print(f"参与角色: {result['roles_executed']}")


class TestRoleAgentWithMiniMax:
    """RoleAgent测试类 - 使用MiniMax真实API"""

    @pytest.fixture(autouse=True)
    def setup_api_key(self):
        """检查API Key是否设置"""
        if not check_api_key():
            pytest.skip("需要设置环境变量 MINIMAX_API_KEY 才能运行此测试")

    def test_specialized_role(self):
        """测试专业角色"""
        role = AgentRole(
            name="财务顾问",
            description="提供财务建议",
            system_prompt="你是专业的财务顾问，擅长分析成本、收益和风险。",
            expertise=["成本分析", "投资回报", "风险管理"]
        )
        llm = create_llm_client(provider="minimax")
        agent = RoleAgent(role, llm_client=llm)

        result = agent.execute("请分析创业项目的财务可行性")

        assert result is not None
        assert len(result) > 0
        print(f"财务顾问回复: {result[:100]}...")


class TestPresetRolesWithMiniMax:
    """预设角色测试 - 使用MiniMax真实API"""

    @pytest.fixture(autouse=True)
    def setup_api_key(self):
        """检查API Key是否设置"""
        if not check_api_key():
            pytest.skip("需要设置环境变量 MINIMAX_API_KEY 才能运行此测试")

    def test_discussion_roles_available(self):
        """测试会议角色定义"""
        roles = create_discussion_roles()
        assert len(roles) == 4

        role_names = [r.name for r in roles]
        assert "主持人" in role_names
        assert "技术专家" in role_names
        assert "业务专家" in role_names
        assert "记录员" in role_names

        for role in roles:
            print(f"角色: {role.name}, 专业领域: {role.expertise}")


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
                Message(role="user", content="请简单介绍一下多智能体系统")
            ],
            temperature=0.7
        )

        response = llm.chat(request)

        assert response.choices[0].message.content is not None
        print(f"回复: {response.choices[0].message.content[:100]}...")


if __name__ == "__main__":
    if not check_api_key():
        print("请先设置环境变量: set MINIMAX_API_KEY=your-api-key")
    else:
        pytest.main([__file__, "-v"])
