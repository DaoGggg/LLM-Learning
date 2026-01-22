"""
多智能体协作Agent（Multi-agent Collaboration）实现

Multi-agent collaboration是指多个Agent协作完成复杂任务的设计模式。
每个Agent扮演不同角色，各自负责特定子任务，通过协作完成整体目标。

核心思路：
1. 定义不同角色的Agent
2. 根据任务分配子任务给不同Agent
3. 各Agent并行或顺序执行子任务
4. 汇总各Agent的结果生成最终响应

应用场景：
- 软件开发（产品经理 + 架构师 + 程序员 + QA）
- 会议讨论（主持人 + 记录员 + 各专家）
- 项目评审（评审员 + 提出者 + 记录员）
"""

from typing import List, Optional, Dict, Any, Callable
from dataclasses import dataclass, field
from common.llm_client import LLMClientBase, Message, create_llm_client
from common.agent_base import AgentBase


@dataclass
class AgentRole:
    """
    Agent角色定义

    属性:
        name: 角色名称
        description: 角色描述
        system_prompt: 系统提示词
        expertise: 专业领域
    """
    name: str
    description: str
    system_prompt: str
    expertise: List[str] = field(default_factory=list)


class RoleAgent:
    """
    角色Agent - 代表特定角色的轻量级Agent

    不继承AgentBase，是独立的角色执行单元
    """

    def __init__(
        self,
        role: AgentRole,
        llm_client: LLMClientBase
    ):
        self.role = role
        self.llm_client = llm_client
        self.history: List[Message] = []
        self.response_history: List[str] = []

        # 注意：MiniMax API 对 system role 有特殊限制，角色信息会在 execute 时传入 user message

    def execute(self, task: str) -> str:
        """
        执行角色任务

        参数:
            task: 任务描述

        返回:
            角色执行结果
        """
        # MiniMax API 可能不支持 system role，将角色信息加入 user message
        user_message = f"""你是{self.role.name}。

角色描述：{self.role.description}

你的专业领域：{', '.join(self.role.expertise)}

请按照以下角色设定执行任务：

{task}"""
        self.history.append(Message(role="user", content=user_message))

        response = self._call_llm(self.history)

        self.history.append(Message(role="assistant", content=response))
        self.response_history.append(response)

        return response

    def _call_llm(self, messages: List[Message]) -> str:
        """调用LLM"""
        from common.llm_client import ChatCompletionRequest

        request = ChatCompletionRequest(
            messages=messages,
            model=self.llm_client.get_model_name()
        )

        response = self.llm_client.chat(request)
        return response.choices[0].message.content

    def add_context(self, context: str) -> None:
        """
        添加上下文信息

        参数:
            context: 上下文内容
        """
        self.history.append(
            Message(role="system", content=f"补充上下文：{context}")
        )

    def get_history(self) -> List[Message]:
        """获取对话历史"""
        return self.history.copy()


class MultiAgentCoordinator(AgentBase):
    """
    多智能体协调器 - 管理多个角色Agent的协调工作

    工作流程：
    1. 根据任务定义角色和分配任务
    2. 创建各角色的执行Agent
    3. 按顺序或并行执行各角色任务
    4. 汇总各角色结果生成最终响应

    使用示例:
        # 定义角色
        roles = [
            AgentRole(
                name="产品经理",
                description="分析需求，制定产品方案",
                system_prompt="你是专业的产品经理...",
                expertise=["需求分析", "产品规划"]
            ),
            AgentRole(
                name="技术专家",
                description="提供技术方案和实现建议",
                system_prompt="你是资深技术专家...",
                expertise=["技术架构", "代码审查"]
            )
        ]

        coordinator = MultiAgentCoordinator(name="项目协调", roles=roles)
        result = coordinator.run("开发一个电商网站")
    """

    def __init__(
        self,
        name: str = "多智能体协调器",
        roles: List[AgentRole] = None,
        llm_client: LLMClientBase = None,
        execution_mode: str = "sequential"  # "sequential" 或 "parallel"
    ):
        """
        初始化多智能体协调器

        参数:
            name: 协调器名称
            roles: 角色定义列表
            llm_client: LLM客户端实例
            execution_mode: 执行模式（sequential顺序/parallel并行）
        """
        if llm_client is None:
            llm_client = create_llm_client("mock")

        super().__init__(name, llm_client)

        self.roles = roles or []
        self.execution_mode = execution_mode
        self.role_agents: Dict[str, RoleAgent] = {}
        self.execution_results: Dict[str, str] = {}
        self.shared_context: Dict[str, Any] = {}  # 共享上下文

        # 为初始角色创建RoleAgent
        for role in self.roles:
            self.role_agents[role.name] = RoleAgent(role, llm_client)

        self._setup_system_prompt()

    def _setup_system_prompt(self) -> None:
        """设置系统提示词"""
        role_descriptions = "\n".join([
            f"- {role.name}: {role.description}"
            for role in self.roles
        ])

        system_prompt = f"""你是一个多智能体协作系统的协调器。

你的工作方式：
1. 分析用户需求，确定需要哪些角色参与
2. 将任务分配给合适的角色Agent
3. 协调各角色的执行顺序和交互
4. 汇总各角色的结果生成最终响应

可用的角色：
{role_descriptions}

请始终：
- 合理分配任务给最合适的角色
- 确保各角色的输出能够有效衔接
- 生成结构化的最终报告"""
        self.add_system_prompt(system_prompt)

    def register_role(self, role: AgentRole, llm_client: LLMClientBase = None) -> None:
        """
        注册角色

        参数:
            role: 角色定义
            llm_client: 该角色专用的LLM客户端（可选，默认使用协调器的客户端）
        """
        client = llm_client or self.llm_client
        self.role_agents[role.name] = RoleAgent(role, client)
        self.roles.append(role)

    def unregister_role(self, role_name: str) -> bool:
        """
        注销角色

        参数:
            role_name: 角色名称

        返回:
            是否成功注销
        """
        if role_name in self.role_agents:
            del self.role_agents[role_name]
            self.roles = [r for r in self.roles if r.name != role_name]
            return True
        return False

    def set_shared_context(self, key: str, value: Any) -> None:
        """
        设置共享上下文

        参数:
            key: 上下文键
            value: 上下文值
        """
        self.shared_context[key] = value

    def get_shared_context(self, key: str, default: Any = None) -> Any:
        """
        获取共享上下文

        参数:
            key: 上下文键
            default: 默认值

        返回:
            上下文值
        """
        return self.shared_context.get(key, default)

    def _distribute_tasks(self, user_input: str) -> Dict[str, str]:
        """
        使用LLM分配任务给各角色

        参数:
            user_input: 用户输入

        返回:
            角色名称到任务的映射
        """
        if not self.role_agents:
            return {}

        task_distribution_prompt = f"""请分析以下用户需求，并将任务分配给合适的角色。

用户需求：{user_input}

可用角色：
{chr(10).join([f'- {name}: {agent.role.description}' for name, agent in self.role_agents.items()])}

请为每个角色生成具体的任务指令。
请用JSON格式返回：
{{
    "角色名称": "具体的任务描述",
    ...
}}

只返回JSON，不要有其他内容。"""

        messages = self.history + [
            Message(role="user", content=task_distribution_prompt)
        ]

        response = self.call_llm(messages, temperature=0.3)

        # 解析JSON
        import json
        import re

        json_match = re.search(r'\{.*\}', response, re.DOTALL)
        if json_match:
            try:
                tasks = json.loads(json_match.group())
                return tasks
            except json.JSONDecodeError:
                pass

        return {}

    def _execute_sequential(self, task_distribution: Dict[str, str]) -> Dict[str, str]:
        """
        顺序执行各角色任务

        参数:
            task_distribution: 角色到任务的映射

        返回:
            角色到结果的映射
        """
        results = {}

        for role_name, task in task_distribution.items():
            if role_name in self.role_agents:
                # 获取之前角色的结果作为上下文
                context_parts = []
                for prev_role, prev_result in results.items():
                    context_parts.append(f"【{prev_role}】的结果：\n{prev_result}")

                if context_parts:
                    context = "\n\n" + "="*50 + "\n".join(context_parts) + "\n" + "="*50
                    self.role_agents[role_name].add_context(context)

                # 执行任务
                result = self.role_agents[role_name].execute(task)
                results[role_name] = result

        return results

    def _execute_parallel(self, task_distribution: Dict[str, str]) -> Dict[str, str]:
        """
        并行执行各角色任务

        参数:
            task_distribution: 角色到任务的映射

        返回:
            角色到结果的映射
        """
        import concurrent.futures

        def execute_role(role_name: str, task: str) -> tuple:
            if role_name in self.role_agents:
                result = self.role_agents[role_name].execute(task)
                return (role_name, result)
            return (role_name, None)

        results = {}
        with concurrent.futures.ThreadPoolExecutor() as executor:
            futures = [
                executor.submit(execute_role, name, task)
                for name, task in task_distribution.items()
            ]
            for future in concurrent.futures.as_completed(futures):
                role_name, result = future.result()
                if result:
                    results[role_name] = result

        return results

    def _synthesize_results(self, user_input: str, task_distribution: Dict[str, str]) -> str:
        """
        综合各角色结果生成最终响应

        参数:
            user_input: 用户原始输入
            task_distribution: 任务分配情况

        返回:
            最终综合响应
        """
        results_parts = []
        for role_name, result in self.execution_results.items():
            task = task_distribution.get(role_name, "")
            results_parts.append(
                f"## {role_name}（任务：{task}）\n\n{result}"
            )

        synthesis_prompt = f"""请根据以下多角色协作的结果，生成一份综合报告。

用户原始需求：{user_input}

各角色执行结果：
{'='*60}
{chr(10).join(results_parts)}
{'='*60}

请生成一份结构清晰、内容完整的综合报告，包含：
1. 执行摘要
2. 各角色的贡献和观点
3. 整体结论和建议

请使用中文撰写，使用适当的标题和列表。"""

        messages = self.history + [
            Message(role="user", content=synthesis_prompt)
        ]

        return self.call_llm(messages, temperature=0.7)

    def run(self, user_input: str) -> dict:
        """
        执行多智能体协作

        参数:
            user_input: 用户输入（通常是复杂任务）

        返回:
            包含以下字段的字典：
            - response: 最终响应
            - role_results: 各角色的执行结果
            - task_distribution: 任务分配情况
            - roles_executed: 执行的角色列表
        """
        self.set_status("analyzing")
        self.add_user_message(user_input)

        # Step 1: 分析任务并分配给各角色
        self.set_status("distributing")
        task_distribution = self._distribute_tasks(user_input)

        # Step 2: 执行各角色任务
        self.set_status("executing")

        if self.execution_mode == "parallel":
            self.execution_results = self._execute_parallel(task_distribution)
        else:
            self.execution_results = self._execute_sequential(task_distribution)

        # Step 3: 综合结果
        self.set_status("synthesizing")
        final_response = self._synthesize_results(user_input, task_distribution)

        self.set_status("finished")
        self.add_assistant_message(final_response)

        return {
            "response": final_response,
            "role_results": self.execution_results,
            "task_distribution": task_distribution,
            "roles_executed": list(self.execution_results.keys()),
            "execution_mode": self.execution_mode
        }

    def get_execution_summary(self) -> str:
        """
        获取执行摘要

        返回:
            摘要字符串
        """
        summary_parts = [f"多智能体协作: {self.name}"]
        summary_parts.append(f"执行模式: {self.execution_mode}")
        summary_parts.append(f"参与角色: {len(self.role_agents)}")
        summary_parts.append(f"完成角色: {len(self.execution_results)}\n")

        for role_name, result in self.execution_results.items():
            preview = result[:100] + "..." if len(result) > 100 else result
            summary_parts.append(f"【{role_name}】{preview}")

        return "\n".join(summary_parts)


# 预设角色定义
def create_software_dev_roles() -> List[AgentRole]:
    """
    创建软件开发团队角色

    返回:
        角色列表
    """
    return [
        AgentRole(
            name="产品经理",
            description="分析需求，制定产品方案",
            system_prompt="""你是资深产品经理，擅长：
1. 深入理解用户需求
2. 将需求转化为具体的产品功能
3. 制定清晰的产品规划和路线图
4. 平衡用户价值和技术可行性

请以产品经理的视角分析问题，输出产品需求分析报告。""",
            expertise=["需求分析", "产品规划", "用户研究"]
        ),
        AgentRole(
            name="架构师",
            description="设计系统架构和技术方案",
            system_prompt="""你是资深系统架构师，擅长：
1. 设计高可用、可扩展的系统架构
2. 选择合适的技术栈和工具
3. 制定技术规范和标准
4. 评估技术风险和解决方案

请以架构师的视角设计系统，输出技术架构文档。""",
            expertise=["系统设计", "技术选型", "性能优化"]
        ),
        AgentRole(
            name="程序员",
            description="编写高质量代码",
            system_prompt="""你是资深程序员，擅长：
1. 编写清晰、可维护的代码
2. 遵循最佳实践和编码规范
3. 编写单元测试和文档
4. 理解和实现设计文档

请以程序员的视角实现功能，输出代码和实现说明。""",
            expertise=["代码编写", "测试", "调试"]
        ),
        AgentRole(
            name="测试工程师",
            description="确保产品质量",
            system_prompt="""你是资深测试工程师，擅长：
1. 设计全面的测试用例
2. 执行功能测试、性能测试
3. 发现和描述缺陷
4. 评估产品质量

请以测试工程师的视角评估，输出测试报告。""",
            expertise=["测试设计", "缺陷分析", "质量评估"]
        )
    ]


def create_discussion_roles() -> List[AgentRole]:
    """
    创建会议讨论团队角色

    返回:
        角色列表
    """
    return [
        AgentRole(
            name="主持人",
            description="引导讨论，确保流程",
            system_prompt="""你是专业会议主持人，擅长：
1. 引导话题，确保讨论聚焦
2. 控制时间，确保效率
3. 平衡各方意见
4. 总结讨论要点

请引导会议讨论，确保覆盖所有重要话题。""",
            expertise=["会议管理", "引导技巧", "总结归纳"]
        ),
        AgentRole(
            name="技术专家",
            description="提供技术见解",
            system_prompt="""你是技术专家，擅长：
1. 深入分析技术问题
2. 提供专业的技术建议
3. 评估技术方案的可行性
4. 解答技术疑问

请从技术角度提供专业见解。""",
            expertise=["技术分析", "方案评估", "问题解答"]
        ),
        AgentRole(
            name="业务专家",
            description="提供业务视角",
            system_prompt="""你是业务专家，擅长：
1. 从业务角度分析问题
2. 评估方案的商业价值
3. 考虑用户体验和市场需求
4. 提出改进建议

请从业务角度提供专业见解。""",
            expertise=["业务分析", "价值评估", "用户需求"]
        ),
        AgentRole(
            name="记录员",
            description="记录会议要点",
            system_prompt="""你是专业会议记录员，擅长：
1. 准确记录讨论要点
2. 整理和归纳信息
3. 生成结构化的会议记录
4. 跟踪行动项

请详细记录会议讨论内容和结论。""",
            expertise=["信息整理", "文档编写", "要点提取"]
        )
    ]


# 便捷函数：创建多智能体协调器
def create_multi_agent_coordinator(
    name: str = "多智能体协调器",
    roles: List[AgentRole] = None,
    provider: str = "mock",
    execution_mode: str = "sequential",
    **kwargs
) -> MultiAgentCoordinator:
    """
    创建多智能体协调器的便捷函数

    参数:
        name: 协调器名称
        roles: 角色列表
        provider: LLM提供商
        execution_mode: 执行模式
        **kwargs: 其他参数

    返回:
        MultiAgentCoordinator实例
    """
    llm_client = create_llm_client(provider, **kwargs)
    return MultiAgentCoordinator(
        name=name,
        roles=roles,
        llm_client=llm_client,
        execution_mode=execution_mode
    )


def create_software_dev_coordinator(
    name: str = "软件开发团队",
    provider: str = "mock",
    execution_mode: str = "sequential",
    **kwargs
) -> MultiAgentCoordinator:
    """
    创建软件开发团队协调器的便捷函数

    参数:
        name: 团队名称
        provider: LLM提供商
        execution_mode: 执行模式
        **kwargs: 其他参数

    返回:
        配置好的MultiAgentCoordinator实例
    """
    roles = create_software_dev_roles()
    coordinator = create_multi_agent_coordinator(
        name=name,
        roles=roles,
        provider=provider,
        execution_mode=execution_mode,
        **kwargs
    )
    return coordinator
