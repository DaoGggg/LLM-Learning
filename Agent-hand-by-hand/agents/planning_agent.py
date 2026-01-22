"""
规划Agent（Planning Agent）实现

Planning是指Agent能够自主将大任务分解为子任务，并按计划执行的能力。
这种能力使Agent能够处理复杂的多步骤任务。

核心思路：
1. 接收用户输入的复杂任务
2. 将任务分解为多个子任务
3. 依次执行子任务
4. 综合所有子任务结果生成最终响应

应用场景：
- 在线研究（研究子主题 -> 综合结果 -> 编写报告）
- 项目规划（分析需求 -> 设计架构 -> 实现代码）
- 问题分析（收集信息 -> 分析原因 -> 提出方案）
"""

from typing import List, Optional, Dict, Any
from common.llm_client import LLMClientBase, Message, create_llm_client
from common.agent_base import AgentBase


class SubTask:
    """
    子任务类 - 表示一个分解后的子任务

    属性:
        id: 子任务ID
        description: 子任务描述
        status: 执行状态（pending/running/completed/failed）
        result: 执行结果
        dependent_on: 依赖的其他子任务ID列表
    """

    def __init__(
        self,
        id: str,
        description: str,
        dependent_on: List[str] = None
    ):
        self.id = id
        self.description = description
        self.status = "pending"
        self.result = None
        self.dependent_on = dependent_on or []


class PlanningAgent(AgentBase):
    """
    规划Agent - 能够自主规划和执行多步骤任务的智能代理

    工作流程：
    1. 接收复杂任务
    2. 使用LLM将任务分解为子任务
    3. 分析子任务依赖关系，确定执行顺序
    4. 依次执行子任务
    5. 综合所有结果生成最终响应

    使用示例:
        llm = create_llm_client("mock", responses=["任务分解结果", "综合结果"])
        agent = PlanningAgent(name="规划者", llm_client=llm)
        result = agent.run("请研究人工智能的发展历史和未来趋势")
    """

    def __init__(
        self,
        name: str = "规划Agent",
        llm_client: LLMClientBase = None,
        max_subtasks: int = 10
    ):
        """
        初始化规划Agent

        参数:
            name: Agent名称
            llm_client: LLM客户端实例
            max_subtasks: 最大子任务数量
        """
        if llm_client is None:
            llm_client = create_llm_client("mock")

        super().__init__(name, llm_client)

        self.max_subtasks = max_subtasks
        self.subtasks: List[SubTask] = []
        self.task_plan: List[SubTask] = []

        self._setup_system_prompt()

    def _setup_system_prompt(self) -> None:
        """设置系统提示词"""
        system_prompt = """你是一个善于规划和执行复杂任务的智能助手。

你的工作方式：
1. 首先分析用户需求的复杂度和关键点
2. 将大任务分解为可管理的小任务
3. 确定任务之间的依赖关系
4. 依次执行每个任务
5. 综合所有结果给出完整回答

请始终：
- 提供清晰、详细的计划
- 合理安排任务顺序
- 确保每个任务都可执行"""
        self.add_system_prompt(system_prompt)

    def _decompose_task(self, user_input: str) -> List[Dict[str, Any]]:
        """
        使用LLM将任务分解为子任务

        参数:
            user_input: 用户输入

        返回:
            子任务列表（字典格式）
        """
        decompose_prompt = f"""请将以下任务分解为多个具体的子任务：

用户任务：{user_input}

请将任务分解为3-7个子任务，并按照执行顺序编号。
对于每个子任务，说明：
1. 任务内容（做什么）
2. 预期产出（得到什么）

请用JSON数组格式返回，示例：
[
    {{"id": "1", "description": "研究AI发展历史", "dependent_on": []}},
    {{"id": "2", "description": "分析当前技术趋势", "dependent_on": ["1"]}},
    {{"id": "3", "description": "总结未来发展方向", "dependent_on": ["1", "2"]}}
]

注意：
- 依赖关系用被依赖任务的id表示
- 无依赖的任务dependent_on为空数组[]
- 任务id必须是从1开始的连续数字
- 只返回JSON，不要有其他内容"""

        messages = self.history + [
            Message(role="user", content=decompose_prompt)
        ]

        response = self.call_llm(messages, temperature=0.3)

        # 解析JSON响应
        import json
        import re

        # 尝试提取JSON
        json_match = re.search(r'\[.*\]', response, re.DOTALL)
        if json_match:
            try:
                subtasks = json.loads(json_match.group())
                return subtasks
            except json.JSONDecodeError:
                pass

        # 如果解析失败，返回空列表
        return []

    def _build_execution_order(self) -> List[SubTask]:
        """
        根据依赖关系确定执行顺序（拓扑排序）

        返回:
            按执行顺序排列的任务列表
        """
        if not self.subtasks:
            return []

        # 创建任务字典
        task_dict = {task.id: task for task in self.subtasks}

        # 计算每个任务的入度
        in_degree = {task.id: 0 for task in self.subtasks}
        for task in self.subtasks:
            for dep_id in task.dependent_on:
                if dep_id in in_degree:
                    in_degree[task.id] += 1

        # 拓扑排序（Kahn算法）
        from collections import deque
        queue = deque()
        for task_id, degree in in_degree.items():
            if degree == 0:
                queue.append(task_id)

        execution_order = []
        while queue:
            current_id = queue.popleft()
            execution_order.append(task_dict[current_id])

            # 更新依赖当前任务的任务
            for task in self.subtasks:
                if current_id in task.dependent_on:
                    in_degree[task.id] -= 1
                    if in_degree[task.id] == 0:
                        queue.append(task.id)

        return execution_order

    def _execute_subtask(self, task: SubTask) -> str:
        """
        执行单个子任务

        参数:
            task: 子任务

        返回:
            执行结果
        """
        task_prompt = f"""请执行以下子任务：

子任务：{task.description}

请详细完成这个任务，并给出完整的结果。

如果你需要使用工具或搜索信息，请直接给出答案。如果需要进一步分解，请说明。

子任务结果："""

        messages = self.history + [
            Message(role="user", content=task_prompt)
        ]

        result = self.call_llm(messages, temperature=0.7)
        return result

    def _synthesize_results(self, user_input: str) -> str:
        """
        综合所有子任务结果生成最终响应

        参数:
            user_input: 用户原始输入

        返回:
            综合后的最终响应
        """
        # 收集所有完成的任务结果
        results_summary = []
        for task in self.task_plan:
            if task.status == "completed":
                results_summary.append(
                    f"【任务{task.id}】{task.description}\n结果：{task.result}"
                )

        synthesize_prompt = f"""请根据以下信息，综合回答用户的原始问题。

用户原始问题：{user_input}

各子任务执行结果：
{'='*60}
{chr(10).join(results_summary)}
{'='*60}

请综合以上所有信息，给出一个完整、详细、有条理的回答。
回答应该：
1. 覆盖用户问题的各个方面
2. 结构清晰，逻辑连贯
3. 有深度分析和具体内容
4. 适当使用标题和列表提高可读性"""

        messages = self.history + [
            Message(role="user", content=synthesize_prompt)
        ]

        return self.call_llm(messages, temperature=0.7)

    def run(self, user_input: str) -> dict:
        """
        执行规划Agent的核心逻辑

        参数:
            user_input: 用户输入（通常是复杂任务）

        返回:
            包含以下字段的字典：
            - response: 最终响应
            - task_plan: 任务计划列表
            - subtask_results: 子任务结果列表
            - num_subtasks: 子任务数量
        """
        self.set_status("decomposing")
        self.add_user_message(user_input)

        # Step 1: 任务分解
        self.subtasks = []
        subtask_dicts = self._decompose_task(user_input)

        # 创建子任务对象
        for subtask_dict in subtask_dicts[:self.max_subtasks]:
            task = SubTask(
                id=str(subtask_dict.get("id", "")),
                description=subtask_dict.get("description", ""),
                dependent_on=[str(d) for d in subtask_dict.get("dependent_on", [])]
            )
            self.subtasks.append(task)

        # Step 2: 确定执行顺序
        self.task_plan = self._build_execution_order()

        self.set_status("executing")

        # Step 3: 依次执行子任务
        subtask_results = []
        for task in self.task_plan:
            task.status = "running"
            self.set_status(f"executing_{task.id}")

            # 执行任务
            result = self._execute_subtask(task)
            task.result = result
            task.status = "completed"

            subtask_results.append({
                "id": task.id,
                "description": task.description,
                "result": result,
                "status": "completed"
            })

        self.set_status("synthesizing")

        # Step 4: 综合结果
        final_response = self._synthesize_results(user_input)

        self.set_status("finished")
        self.add_assistant_message(final_response)

        return {
            "response": final_response,
            "task_plan": [
                {"id": t.id, "description": t.description, "status": t.status}
                for t in self.task_plan
            ],
            "subtask_results": subtask_results,
            "num_subtasks": len(self.task_plan)
        }

    def get_plan_summary(self) -> str:
        """
        获取任务计划摘要

        返回:
            摘要字符串
        """
        if not self.task_plan:
            return "尚未制定任务计划"

        summary_parts = [f"规划Agent: {self.name}"]
        summary_parts.append(f"总子任务数: {len(self.task_plan)}\n")

        for task in self.task_plan:
            status_icon = "✓" if task.status == "completed" else "○" if task.status == "pending" else "▶"
            summary_parts.append(f"{status_icon} [{task.id}] {task.description}")

        return "\n".join(summary_parts)


class HierarchicalPlannerAgent(AgentBase):
    """
    层级规划Agent - Planning Agent的增强版本，支持多层级任务分解

    特点：
    1. 支持将任务分解为多层级子任务
    2. 可以在执行过程中动态调整计划
    3. 支持任务的优先级设置
    4. 提供更详细的任务执行报告
    """

    def __init__(
        self,
        name: str = "层级规划Agent",
        llm_client: LLMClientBase = None,
        max_levels: int = 3,
        max_subtasks_per_level: int = 5
    ):
        """
        初始化层级规划Agent

        参数:
            name: Agent名称
            llm_client: LLM客户端实例
            max_levels: 最大分解层级
            max_subtasks_per_level: 每层最大子任务数
        """
        if llm_client is None:
            llm_client = create_llm_client("mock")

        super().__init__(name, llm_client)

        self.max_levels = max_levels
        self.max_subtasks_per_level = max_subtasks_per_level
        self.task_hierarchy: List[Dict] = []  # 任务层级结构
        self.execution_log: List[Dict] = []   # 执行日志

        self._setup_system_prompt()

    def _setup_system_prompt(self) -> None:
        """设置系统提示词"""
        system_prompt = """你是一个善于进行复杂任务规划和层级管理的智能助手。

你的工作方式：
1. 分析任务的复杂度和层级结构
2. 将任务分解为多个层级的主任务和子任务
3. 确定每个任务的优先级和依赖关系
4. 按优先级和依赖关系执行任务
5. 实时记录执行过程和结果

请始终：
- 提供清晰的任务层级结构
- 合理设置任务优先级
- 确保任务依赖关系正确
- 及时记录执行过程"""
        self.add_system_prompt(system_prompt)

    def run(self, user_input: str) -> dict:
        """
        执行层级规划Agent的核心逻辑

        参数:
            user_input: 用户输入（复杂任务）

        返回:
            包含层级任务结构和执行结果的字典
        """
        self.set_status("analyzing")
        self.add_user_message(user_input)

        # 构建层级任务结构
        self.set_status("decomposing")
        hierarchy_result = self._decompose_into_hierarchy(user_input)
        self.task_hierarchy = hierarchy_result

        # 执行所有叶子节点任务
        self.set_status("executing")
        execution_results = self._execute_hierarchy(hierarchy_result)

        # 生成最终报告
        self.set_status("synthesizing")
        final_response = self._generate_final_report(user_input, execution_results)

        self.set_status("finished")
        self.add_assistant_message(final_response)

        return {
            "response": final_response,
            "task_hierarchy": self.task_hierarchy,
            "execution_results": execution_results,
            "execution_log": self.execution_log
        }

    def _decompose_into_hierarchy(self, user_input: str) -> List[Dict]:
        """将任务分解为层级结构"""
        import json
        import re

        prompt = f"""请将以下任务分解为层级结构（最多{self.max_levels}层）：

任务：{user_input}

请用JSON数组格式返回，每层任务包含：
- level: 层级编号（1为主任务，2为子任务）
- id: 任务编号
- description: 任务描述
- priority: 优先级（1-10，10最高）
- parent_id: 父任务ID（顶层任务为null）

示例：
[
    {{"level": 1, "id": "1", "description": "主任务", "priority": 10, "parent_id": null}},
    {{"level": 2, "id": "1.1", "description": "子任务1", "priority": 8, "parent_id": "1"}},
    {{"level": 2, "id": "1.2", "description": "子任务2", "priority": 7, "parent_id": "1"}}
]

只返回JSON。"""

        messages = self.history + [Message(role="user", content=prompt)]
        response = self.call_llm(messages, temperature=0.3)

        json_match = re.search(r'\[.*\]', response, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                pass

        return []

    def _execute_hierarchy(self, hierarchy: List[Dict]) -> Dict[str, str]:
        """执行层级任务"""
        results = {}

        # 找出叶子节点任务（没有子任务的任务）
        leaf_tasks = [t for t in hierarchy if not self._has_children(t, hierarchy)]

        for task in leaf_tasks:
            self.set_status(f"executing_{task['id']}")
            self.execution_log.append({
                "task_id": task['id'],
                "description": task['description'],
                "status": "running"
            })

            result = self._execute_task(task['description'])

            results[task['id']] = result

            self.execution_log[-1]["status"] = "completed"
            self.execution_log[-1]["result"] = result

        return results

    def _has_children(self, task: Dict, hierarchy: List[Dict]) -> bool:
        """检查任务是否有子任务"""
        task_id = task['id']
        for t in hierarchy:
            if t.get('parent_id') == task_id:
                return True
        return False

    def _execute_task(self, description: str) -> str:
        """执行单个任务"""
        prompt = f"""请执行以下任务：

任务：{description}

请详细完成任务并给出结果。"""

        messages = self.history + [Message(role="user", content=prompt)]
        return self.call_llm(messages, temperature=0.7)

    def _generate_final_report(self, user_input: str, execution_results: Dict) -> str:
        """生成最终报告"""
        import json

        results_str = json.dumps(execution_results, ensure_ascii=False, indent=2)

        prompt = f"""请根据以下任务执行结果，生成一份完整的报告。

原始任务：{user_input}

执行结果：
{results_str}

请生成一份结构化的最终报告，包含：
1. 执行摘要
2. 各任务执行详情
3. 整体结论和建议"""

        messages = self.history + [Message(role="user", content=prompt)]
        return self.call_llm(messages, temperature=0.7)


# 便捷函数：创建Planning Agent
def create_planning_agent(
    name: str = "规划Agent",
    provider: str = "mock",
    **kwargs
) -> PlanningAgent:
    """
    创建Planning Agent的便捷函数

    参数:
        name: Agent名称
        provider: LLM提供商（'openai'/'anthropic'/'minimax'/'mock'）
        **kwargs: 其他参数

    返回:
        PlanningAgent实例
    """
    llm_client = create_llm_client(provider, **kwargs)
    return PlanningAgent(name=name, llm_client=llm_client)


# 便捷函数：创建HierarchicalPlanner Agent
def create_hierarchical_planner_agent(
    name: str = "层级规划Agent",
    provider: str = "mock",
    **kwargs
) -> HierarchicalPlannerAgent:
    """
    创建HierarchicalPlanner Agent的便捷函数

    参数:
        name: Agent名称
        provider: LLM提供商
        **kwargs: 其他参数

    返回:
        HierarchicalPlannerAgent实例
    """
    llm_client = create_llm_client(provider, **kwargs)
    return HierarchicalPlannerAgent(name=name, llm_client=llm_client)
