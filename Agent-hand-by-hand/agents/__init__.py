"""
Agent实现包 - 提供各种Agent范式的实现

包含:
- reflection_agent: 反思Agent
- tool_use_agent: 工具使用Agent
- planning_agent: 规划Agent
- multi_agent: 多智能体协作Agent
"""

from .reflection_agent import (
    ReflectionAgent,
    SelfImprovingAgent,
    create_reflection_agent
)

from .tool_use_agent import (
    ToolUseAgent,
    ReActAgent,
    create_tool_use_agent,
    create_react_agent
)

from .planning_agent import (
    PlanningAgent,
    HierarchicalPlannerAgent,
    SubTask,
    create_planning_agent,
    create_hierarchical_planner_agent
)

from .multi_agent import (
    MultiAgentCoordinator,
    RoleAgent,
    AgentRole,
    create_multi_agent_coordinator,
    create_software_dev_coordinator,
    create_software_dev_roles,
    create_discussion_roles
)

__all__ = [
    # 反思Agent
    "ReflectionAgent",
    "SelfImprovingAgent",
    "create_reflection_agent",
    # 工具使用Agent
    "ToolUseAgent",
    "ReActAgent",
    "create_tool_use_agent",
    "create_react_agent",
    # 规划Agent
    "PlanningAgent",
    "HierarchicalPlannerAgent",
    "SubTask",
    "create_planning_agent",
    "create_hierarchical_planner_agent",
    # 多智能体协作
    "MultiAgentCoordinator",
    "RoleAgent",
    "AgentRole",
    "create_multi_agent_coordinator",
    "create_software_dev_coordinator",
    "create_software_dev_roles",
    "create_discussion_roles"
]
