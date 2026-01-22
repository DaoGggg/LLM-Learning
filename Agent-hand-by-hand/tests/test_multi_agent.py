"""
多智能体协作Agent测试用例

测试Multi-agent协作的各项功能：
1. 角色定义和注册
2. 任务分配
3. 顺序/并行执行
4. 结果汇总
"""

import pytest
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from common.llm_client import MockLLMClient, create_llm_client
from agents.multi_agent import (
    MultiAgentCoordinator,
    RoleAgent,
    AgentRole,
    create_multi_agent_coordinator,
    create_software_dev_coordinator,
    create_software_dev_roles,
    create_discussion_roles
)


class TestAgentRole:
    """AgentRole测试类"""

    def test_init(self):
        """测试角色初始化"""
        role = AgentRole(
            name="测试角色",
            description="测试描述",
            system_prompt="你是测试角色",
            expertise=["测试1", "测试2"]
        )

        assert role.name == "测试角色"
        assert role.description == "测试描述"
        assert role.system_prompt == "你是测试角色"
        assert role.expertise == ["测试1", "测试2"]

    def test_init_defaults(self):
        """测试默认参数"""
        role = AgentRole(
            name="简单角色",
            description="描述",
            system_prompt="提示词"
        )

        assert role.expertise == []


class TestRoleAgent:
    """RoleAgent测试类"""

    def test_execute(self):
        """测试角色执行"""
        llm = MockLLMClient(responses=["角色响应"])
        role = AgentRole(
            name="测试",
            description="测试",
            system_prompt="你是测试助手"
        )
        agent = RoleAgent(role, llm_client=llm)

        result = agent.execute("执行任务")

        assert result == "角色响应"
        assert len(agent.response_history) == 1

    def test_add_context(self):
        """测试添加上下文"""
        llm = MockLLMClient(responses=["响应"])
        role = AgentRole(name="测试", description="", system_prompt="")
        agent = RoleAgent(role, llm_client=llm)

        agent.add_context("上下文信息")

        # 验证上下文被添加
        history = agent.get_history()
        assert len(history) == 1  # 只有上下文
        assert "上下文信息" in history[0].content

    def test_get_history(self):
        """测试获取历史"""
        llm = MockLLMClient(responses=["响应"])
        role = AgentRole(name="测试", description="", system_prompt="系统提示")
        agent = RoleAgent(role, llm_client=llm)

        history = agent.get_history()

        # 注意：RoleAgent 不在 __init__ 时添加系统提示，角色信息在 execute 时传入
        assert len(history) == 0
        # 执行任务后会添加 user 和 assistant 消息


class TestMultiAgentCoordinator:
    """MultiAgentCoordinator测试类"""

    def test_init_empty_roles(self):
        """测试无角色初始化"""
        llm = MockLLMClient(responses=["响应"])
        coordinator = MultiAgentCoordinator(
            name="测试协调",
            llm_client=llm
        )

        assert coordinator.name == "测试协调"
        assert len(coordinator.roles) == 0
        assert coordinator.execution_mode == "sequential"

    def test_init_with_roles(self):
        """测试带角色初始化"""
        llm = MockLLMClient(responses=["响应"])
        roles = [
            AgentRole(name="角色1", description="描述1", system_prompt="提示1"),
            AgentRole(name="角色2", description="描述2", system_prompt="提示2")
        ]
        coordinator = MultiAgentCoordinator(
            name="测试协调",
            roles=roles,
            llm_client=llm,
            execution_mode="parallel"
        )

        assert len(coordinator.roles) == 2
        assert coordinator.execution_mode == "parallel"

    def test_register_role(self):
        """测试注册角色"""
        llm = MockLLMClient(responses=["响应"])
        coordinator = MultiAgentCoordinator(name="测试", llm_client=llm)

        role = AgentRole(name="新角色", description="描述", system_prompt="提示")
        coordinator.register_role(role)

        assert len(coordinator.roles) == 1
        assert "新角色" in coordinator.role_agents

    def test_unregister_role(self):
        """测试注销角色"""
        llm = MockLLMClient(responses=["响应"])
        roles = [
            AgentRole(name="角色1", description="", system_prompt=""),
            AgentRole(name="角色2", description="", system_prompt="")
        ]
        coordinator = MultiAgentCoordinator(name="测试", roles=roles, llm_client=llm)

        result = coordinator.unregister_role("角色1")

        assert result is True
        assert len(coordinator.roles) == 1
        assert "角色1" not in coordinator.role_agents

    def test_unregister_nonexistent(self):
        """测试注销不存在的角色"""
        llm = MockLLMClient(responses=["响应"])
        coordinator = MultiAgentCoordinator(name="测试", llm_client=llm)

        result = coordinator.unregister_role("不存在的角色")

        assert result is False

    def test_shared_context(self):
        """测试共享上下文"""
        llm = MockLLMClient(responses=["响应"])
        coordinator = MultiAgentCoordinator(name="测试", llm_client=llm)

        coordinator.set_shared_context("key1", "value1")
        coordinator.set_shared_context("key2", {"nested": "value"})

        assert coordinator.get_shared_context("key1") == "value1"
        assert coordinator.get_shared_context("key2") == {"nested": "value"}
        assert coordinator.get_shared_context("nonexistent", "default") == "default"

    def test_single_role_execution(self):
        """测试单角色执行"""
        responses = [
            '{"角色1": "任务1"}',  # 任务分配
            "角色1结果"  # 综合结果
        ]
        llm = MockLLMClient(responses=responses)
        roles = [
            AgentRole(name="角色1", description="描述", system_prompt="提示")
        ]
        coordinator = MultiAgentCoordinator(
            name="测试",
            roles=roles,
            llm_client=llm
        )

        # 注册一个角色Agent（使用模拟）
        coordinator.role_agents["角色1"] = RoleAgent(
            roles[0],
            MockLLMClient(responses=["角色1执行结果"])
        )

        result = coordinator.run("测试任务")

        assert "response" in result
        assert "role_results" in result
        assert "task_distribution" in result

    def test_sequential_execution(self):
        """测试顺序执行"""
        # 任务分配 + 3个角色的结果 + 综合结果
        responses = [
            '{"角色1": "任务1", "角色2": "任务2", "角色3": "任务3"}',
            "角色1结果",
            "角色2结果",
            "角色3结果",
            "综合结果"
        ]
        llm = MockLLMClient(responses=responses)
        roles = [
            AgentRole(name=f"角色{i}", description="", system_prompt="")
            for i in range(1, 4)
        ]
        coordinator = MultiAgentCoordinator(
            name="测试",
            roles=roles,
            llm_client=llm,
            execution_mode="sequential"
        )

        # 注册角色Agent
        for role in roles:
            coordinator.role_agents[role.name] = RoleAgent(
                role,
                MockLLMClient(responses=[f"{role.name}结果"])
            )

        result = coordinator.run("复杂任务")

        assert result["execution_mode"] == "sequential"
        assert len(result["roles_executed"]) == 3

    def test_get_execution_summary(self):
        """测试获取执行摘要"""
        llm = MockLLMClient(responses=["分配", "结果1", "结果2", "综合"])
        roles = [
            AgentRole(name="角色1", description="", system_prompt=""),
            AgentRole(name="角色2", description="", system_prompt="")
        ]
        coordinator = MultiAgentCoordinator(
            name="测试协调",
            roles=roles,
            llm_client=llm,
            execution_mode="parallel"
        )

        # 注册角色
        for role in roles:
            coordinator.role_agents[role.name] = RoleAgent(
                role,
                MockLLMClient(responses=["结果"])
            )

        # 先执行一次
        coordinator.run("测试任务")

        summary = coordinator.get_execution_summary()

        assert "测试协调" in summary
        assert "parallel" in summary
        assert "参与角色" in summary


class TestPresetRoles:
    """预设角色测试"""

    def test_software_dev_roles(self):
        """测试软件开发角色"""
        roles = create_software_dev_roles()

        assert len(roles) == 4

        role_names = [r.name for r in roles]
        assert "产品经理" in role_names
        assert "架构师" in role_names
        assert "程序员" in role_names
        assert "测试工程师" in role_names

        # 验证每个角色都有专业领域
        for role in roles:
            assert len(role.expertise) > 0

    def test_discussion_roles(self):
        """测试会议讨论角色"""
        roles = create_discussion_roles()

        assert len(roles) == 4

        role_names = [r.name for r in roles]
        assert "主持人" in role_names
        assert "技术专家" in role_names
        assert "业务专家" in role_names
        assert "记录员" in role_names


class TestCreateFunctions:
    """便捷创建函数测试"""

    def test_create_coordinator(self):
        """测试创建协调器"""
        coordinator = create_multi_agent_coordinator(
            name="便捷协调",
            provider="mock",
            responses=["响应"]
        )

        assert coordinator.name == "便捷协调"
        assert isinstance(coordinator, MultiAgentCoordinator)

    def test_create_software_dev_coordinator(self):
        """测试创建软件开发团队"""
        coordinator = create_software_dev_coordinator(
            name="开发团队",
            provider="mock",
            responses=["响应"]
        )

        assert coordinator.name == "开发团队"
        assert len(coordinator.roles) == 4


class TestIntegration:
    """集成测试"""

    def test_complete_workflow(self):
        """测试完整工作流程"""
        responses = [
            '{"产品经理": "任务1", "架构师": "任务2"}',
            "产品经理结果",
            "架构师结果",
            "综合报告"
        ]
        llm = MockLLMClient(responses=responses)
        roles = [
            AgentRole(name="产品经理", description="", system_prompt=""),
            AgentRole(name="架构师", description="", system_prompt="")
        ]
        coordinator = MultiAgentCoordinator(
            name="项目团队",
            roles=roles,
            llm_client=llm
        )

        # 注册角色
        for role in roles:
            coordinator.role_agents[role.name] = RoleAgent(
                role,
                MockLLMClient(responses=[f"{role.name}结果"])
            )

        result = coordinator.run("开发一个电商系统")

        # 验证完整结果
        assert "response" in result
        assert "role_results" in result
        assert "task_distribution" in result
        assert "roles_executed" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
