"""
规划Agent测试用例

测试Planning Agent的各项功能：
1. 任务分解
2. 依赖关系分析
3. 子任务执行
4. 结果综合
"""

import pytest
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from common.llm_client import MockLLMClient, create_llm_client
from agents.planning_agent import (
    PlanningAgent,
    HierarchicalPlannerAgent,
    SubTask,
    create_planning_agent,
    create_hierarchical_planner_agent
)


class TestSubTask:
    """SubTask测试类"""

    def test_init(self):
        """测试SubTask初始化"""
        task = SubTask(id="1", description="测试任务", dependent_on=[])

        assert task.id == "1"
        assert task.description == "测试任务"
        assert task.status == "pending"
        assert task.result is None
        assert task.dependent_on == []

    def test_init_with_dependencies(self):
        """测试带依赖的SubTask初始化"""
        task = SubTask(
            id="3",
            description="任务3",
            dependent_on=["1", "2"]
        )

        assert task.id == "3"
        assert task.dependent_on == ["1", "2"]


class TestPlanningAgent:
    """PlanningAgent测试类"""

    def test_init(self):
        """测试Agent初始化"""
        llm = MockLLMClient(responses=["测试响应"])
        agent = PlanningAgent(name="测试规划者", llm_client=llm, max_subtasks=5)

        assert agent.name == "测试规划者"
        assert agent.max_subtasks == 5
        assert len(agent.history) >= 1  # 系统提示词

    def test_init_default(self):
        """测试默认初始化"""
        llm = MockLLMClient(responses=["测试响应"])
        agent = PlanningAgent(llm_client=llm)

        assert agent.name == "规划Agent"
        assert agent.max_subtasks == 10

    def test_plan_summary_empty(self):
        """测试空计划摘要"""
        llm = MockLLMClient(responses=["测试响应"])
        agent = PlanningAgent(name="测试", llm_client=llm)

        summary = agent.get_plan_summary()
        assert "尚未制定任务计划" in summary

    def test_single_response(self):
        """测试单次响应（无需分解）"""
        responses = [
            '[{"id": "1", "description": "分析任务", "dependent_on": []}]',
            "综合结果"
        ]
        llm = MockLLMClient(responses=responses)
        agent = PlanningAgent(name="测试", llm_client=llm, max_subtasks=1)

        result = agent.run("测试任务")

        assert "response" in result
        assert "task_plan" in result
        assert "subtask_results" in result
        assert result["num_subtasks"] >= 0

    def test_multiple_subtasks(self):
        """测试多子任务分解"""
        responses = [
            '''[
                {"id": "1", "description": "研究背景", "dependent_on": []},
                {"id": "2", "description": "分析现状", "dependent_on": ["1"]},
                {"id": "3", "description": "提出建议", "dependent_on": ["1", "2"]}
            ]''',
            "子任务1结果",
            "子任务2结果",
            "子任务3结果",
            "综合结果"
        ]
        llm = MockLLMClient(responses=responses)
        agent = PlanningAgent(name="测试", llm_client=llm, max_subtasks=5)

        result = agent.run("复杂任务")

        assert result["num_subtasks"] == 3
        assert len(result["task_plan"]) == 3
        assert len(result["subtask_results"]) == 3

    def test_execution_order(self):
        """测试执行顺序（依赖关系）"""
        # 任务2依赖任务1，任务3依赖任务1和任务2
        responses = [
            '''[
                {"id": "1", "description": "第一步", "dependent_on": []},
                {"id": "2", "description": "第二步", "dependent_on": ["1"]},
                {"id": "3", "description": "第三步", "dependent_on": ["1", "2"]}
            ]''',
            "第一步结果",
            "第二步结果",
            "第三步结果",
            "综合结果"
        ]
        llm = MockLLMClient(responses=responses)
        agent = PlanningAgent(name="测试", llm_client=llm)

        result = agent.run("测试任务")

        # 验证执行顺序：1 -> 2 -> 3
        task_ids = [t["id"] for t in result["task_plan"]]
        assert task_ids == ["1", "2", "3"]


class TestHierarchicalPlannerAgent:
    """HierarchicalPlannerAgent测试类"""

    def test_init(self):
        """测试初始化"""
        llm = MockLLMClient(responses=["测试响应"])
        agent = HierarchicalPlannerAgent(
            name="层级规划",
            llm_client=llm,
            max_levels=3,
            max_subtasks_per_level=5
        )

        assert agent.name == "层级规划"
        assert agent.max_levels == 3
        assert agent.max_subtasks_per_level == 5

    def test_empty_history(self):
        """测试初始历史为空"""
        llm = MockLLMClient(responses=["测试响应"])
        agent = HierarchicalPlannerAgent(name="测试", llm_client=llm)

        assert len(agent.task_hierarchy) == 0
        assert len(agent.execution_log) == 0


class TestCreateFunctions:
    """便捷创建函数测试"""

    def test_create_planning_agent(self):
        """测试创建Planning Agent"""
        agent = create_planning_agent(
            name="便捷创建",
            provider="mock",
            responses=["测试"]
        )

        assert agent.name == "便捷创建"
        assert isinstance(agent, PlanningAgent)

    def test_create_hierarchical_planner(self):
        """测试创建HierarchicalPlanner Agent"""
        agent = create_hierarchical_planner_agent(
            name="层级规划",
            provider="mock",
            responses=["测试"]
        )

        assert agent.name == "层级规划"
        assert isinstance(agent, HierarchicalPlannerAgent)


class TestIntegration:
    """集成测试"""

    def test_plan_and_execute(self):
        """测试完整规划和执行流程"""
        responses = [
            '[{"id": "1", "description": "收集信息", "dependent_on": []}]',
            "收集到的信息",
            "综合报告"
        ]
        llm = MockLLMClient(responses=responses)
        agent = PlanningAgent(name="研究助手", llm_client=llm)

        result = agent.run("研究AI的发展")

        # 验证结果结构
        assert "response" in result
        assert result["response"] == "综合报告"
        assert result["num_subtasks"] == 1

        # 验证计划摘要
        summary = agent.get_plan_summary()
        assert "研究助手" in summary
        assert "总子任务数: 1" in summary


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
