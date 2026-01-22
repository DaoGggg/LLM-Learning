# 从0手搓各路Agent范式的实现

理解各路Agent范式原理的基础上，从0开始构建各路Agent

API测试支持 MiniMax、OpenAI 和 Anthropic 标准协议通信的API服务

## 0.前言

Agent指的是一个能够感知其环境并根据感知到的信息做出决策以实现特定目标的系统，通过大模型的加持，Agent比以往任何时候都要更加引人注目。

**Agent的本质还是prompt engineering**

"Agent范式"是指在人工智能领域中，特别是在设计和开发智能代理时所采用的不同方法和技术。在大型语言模型（LLMs）的背景下，Agent范式通常涉及到如何利用这些模型来提升代理的规划、决策和执行能力。

---

## 1.Reflection (反思Agent)

### 1.1 什么是Reflection Agent

Reflection是指Agent能够对自己的行为和决策进行推理和分析的能力。这种能力使Agent能够更好地理解自己的行为和决策，并在未来的决策中更好地利用这些信息。

### 1.2 实现流程

```
┌─────────────────────────────────────────────────────────────────┐
│                      Reflection Agent 流程                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐ │
│   │ 用户输入  │───>│ 生成初始  │───>│ 自我反思  │───>│ 修正响应  │ │
│   │          │    │  响应     │    │          │    │          │ │
│   └──────────┘    └──────────┘    └──────────┘    └──────────┘ │
│        │                                             │         │
│        │                                             │         │
│        │              ┌──────────┐                   │         │
│        └─────────────>│ 达到最大  │<──────────────────┘         │
│                       │ 反思次数? │                           │
│                       └────┬─────┘                           │
│                            │否                                │
│                            ▼                                  │
│                       结束（返回最终响应）                       │
└─────────────────────────────────────────────────────────────────┘
```

### 1.3 核心代码结构

```python
class ReflectionAgent(AgentBase):
    """反思Agent - 具有自我反思能力的智能代理"""

    def run(self, user_input: str, max_reflections: int = None) -> dict:
        """
        核心逻辑：
        1. 生成初始响应
        2. 循环：反思 -> 判断是否停止 -> 修正响应
        """
        # Step 1: 生成初始响应
        initial_response = self._generate_initial_response(user_input)

        # Step 2-4: 反思循环
        current_response = initial_response
        for i in range(max_reflections):
            # 进行反思
            reflection = self._reflect(user_input, current_response)

            # 判断是否应该停止
            if self._should_stop_reflection(reflection, i + 1):
                break

            # 修正响应
            current_response = self._revise_response(user_input, current_response, reflection)

        return {
            "response": current_response,
            "initial_response": initial_response,
            "reflections": reflections,
            "num_reflections": len(reflections)
        }
```

### 1.4 Prompt设计

**系统提示词** - 设定Agent的反思角色：
```python
system_prompt = """你是一个善于深度思考的智能助手。

你的工作方式：
1. 首先给出问题的初步答案
2. 然后对给出的答案进行自我反思
3. 最后根据反思改进答案

请始终：
- 提供准确、有深度的分析
- 勇于质疑自己的结论
- 追求逻辑严密和事实准确"""
```

**反思提示词** - 引导Agent进行自我检查：
```python
reflection_prompt = """请对以下回答进行深入反思和分析：

用户问题：{user_input}

当前回答：{response}

请从以下角度进行反思：
1. 回答是否准确？是否遗漏了重要信息？
2. 逻辑是否清晰？论证是否充分？
3. 是否有改进空间？如何改进？
4. 是否存在偏见或错误假设？

请简要但深刻地指出问题所在，并给出具体的改进建议。"""
```

### 1.5 SelfImprovingAgent (增强版)

在 Reflection 基础上增加了经验积累能力：

```
┌────────────────────────────────────────────────────────────┐
│                  SelfImprovingAgent 流程                     │
├────────────────────────────────────────────────────────────┤
│                                                             │
│   ┌──────────┐    ┌──────────┐    ┌──────────┐             │
│   │ 用户输入  │───>│ 生成响应  │───>│ 反思并    │             │
│   │          │    │          │    │ 记录经验   │             │
│   └──────────┘    └──────────┘    └────┬─────┘             │
│                                         │                   │
│                                         ▼                   │
│                               存入经验库（最近50条）          │
│                                         │                   │
│                                         ▼                   │
│                               下次交互时参考历史经验           │
└────────────────────────────────────────────────────────────┘
```

### 1.6 相关文件

| 文件 | 说明 |
|------|------|
| `agents/reflection_agent.py` | ReflectionAgent 和 SelfImprovingAgent 实现 |
| `tests/test_reflection_agent.py` | 模拟测试（快速验证） |
| `tests/test_reflection_agent_with_minimax.py` | MiniMax API 集成测试 |

---

## 2.Tool Use (工具使用Agent)

### 2.1 什么是Tool Use Agent

就像人类使用工具来帮助完成任务一样，Agent也可以使用工具来帮助完成任务。这种Agent范式涉及到Agent如何利用外部工具和资源来提升自己的决策和执行能力。

### 2.2 实现流程

```
┌─────────────────────────────────────────────────────────────────┐
│                      Tool Use Agent 流程                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   ┌──────────┐    ┌──────────┐    ┌──────────┐                  │
│   │ 用户输入  │───>│ LLM判断  │───>│ 解析工具  │                  │
│   │          │    │ 是否需要  │    │ 调用格式  │                  │
│   └──────────┘    │   工具?   │    └────┬─────┘                  │
│                    └────┬─────┘         │                        │
│                         │              ▼                        │
│                         │        ┌──────────┐                   │
│                         │        │ 执行工具  │                   │
│                         │        │   调用   │                   │
│                         │        └────┬─────┘                   │
│                         │             │                         │
│                         │    ┌───────┴───────┐                  │
│                         │    │               │                  │
│                         ▼    ▼               ▼                  │
│                   无需工具              工具执行成功             工具执行失败
│                   直接回答              解析结果                 返回错误信息
│                                         │                       │
│                                         ▼                       │
│                                   生成最终响应                   │
└─────────────────────────────────────────────────────────────────┘
```

### 2.3 核心代码结构

```python
class ToolUseAgent(AgentBase):
    """工具使用Agent - 能够调用外部工具的智能代理"""

    def run(self, user_input: str) -> dict:
        """
        核心逻辑：
        1. LLM判断是否需要工具
        2. 解析工具调用格式
        3. 执行工具
        4. 解析结果并生成最终响应
        """
        # 初始LLM调用
        response = self.call_llm(self.history)

        tool_calls = []
        tool_results = []

        # 尝试解析和执行工具调用
        for _ in range(self.max_tool_calls):
            tool_call = self._parse_tool_call(response)

            if tool_call is None:
                # 没有工具调用，结束
                break

            tool_name, params = tool_call
            tool_calls.append({"tool": tool_name, "params": params})

            # 执行工具
            result = self._execute_tool(tool_name, params)
            tool_results.append(result)

            if result.success:
                # 工具执行成功，解析结果并继续
                response = self._parse_tool_result(response, result)
            else:
                # 工具执行失败，结束
                break

        return {
            "response": response,
            "tool_calls": tool_calls,
            "tool_results": tool_results
        }

    def _parse_tool_call(self, text: str) -> Optional[Tuple[str, Dict]]:
        """解析工具调用指令"""
        import re
        import json

        # 匹配格式: [TOOL_CALL]工具名称: calculator 参数: {"expression": "..."} [/TOOL_CALL]
        pattern = r'\[TOOL_CALL\]\s*工具名称:\s*(\w+)\s*参数:\s*(\{.*?\})\s*\[/TOOL_CALL\]'
        match = re.search(pattern, text, re.DOTALL)

        if match:
            tool_name = match.group(1)
            params_str = match.group(2)
            params = json.loads(params_str)
            return (tool_name, params)
        return None
```

### 2.4 工具定义

```python
class CalculatorTool(ToolBase):
    """计算器工具 - 执行数学表达式计算"""

    def __init__(self):
        super().__init__(
            name="calculator",
            description="计算器工具 - 执行数学表达式计算",
            parameters={
                "expression": Parameter(
                    type="string",
                    description="要计算的数学表达式",
                    required=True
                )
            }
        )

    def execute(self, expression: str) -> ToolResult:
        """执行计算"""
        try:
            # 安全计算（限制eval的使用范围）
            result = eval(expression, {"__builtins__": {}}, {})
            return ToolResult(success=True, content=str(result))
        except Exception as e:
            return ToolResult(success=False, error=str(e))
```

### 2.5 Prompt设计

**系统提示词** - 设定Agent的工具使用能力：
```python
system_prompt = """你是一个能够使用工具的智能助手。

你可以使用以下工具来帮助你完成任务：
{tool_descriptions}

使用工具的规则：
1. 只有在确实需要时才使用工具
2. 每次只调用一个工具
3. 仔细解析工具返回的结果
4. 基于工具结果给出最终回答

当你需要使用工具时，请按照以下格式回复：
[TOOL_CALL]
工具名称: <工具名称>
参数: <JSON格式的参数>
[/TOOL_CALL]

当你不需要使用工具时，直接给出回答。"""
```

### 2.6 ReAct模式 (推理-行动)

ReAct (Reasoning + Acting) 是 Tool Use 的增强模式，强调推理过程：

```
┌─────────────────────────────────────────────────────────────────┐
│                        ReAct 流程                                │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   ┌─────────────────────────────────────────────────────────┐   │
│   │                    循环 (最多max_cycles次)                │   │
│   │                                                         │   │
│   │   Thought: 用户输入，需要计算100/4                         │   │
│   │   Action: [TOOL_CALL]calculator:{"expression": "100/4"} │   │
│   │   Observation: 25.0                                      │   │
│   │   ...                                                    │   │
│   │   Thought: 得到了结果，可以回答用户了                       │   │
│   │   Action: None                                           │   │
│   │                                                          │   │
│   └─────────────────────────────────────────────────────────┘   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 2.7 相关文件

| 文件 | 说明 |
|------|------|
| `agents/tool_use_agent.py` | ToolUseAgent 和 ReActAgent 实现 |
| `common/tool.py` | 工具基类和常用工具定义 |
| `tests/test_tool_use_agent.py` | 模拟测试（快速验证） |
| `tests/test_tool_use_agent_with_minimax.py` | MiniMax API 集成测试 |

---

## 3.Planning

规划是Agent AI 的一个关键设计模式，使用大型语言模型自主决定执行哪些步骤来完成更大的任务。例如，如果我们要求Agent对给定主题进行在线研究，我们可能会使用 LLM 将目标分解为较小的子任务，例如研究特定子主题、综合研究结果和编写报告。

### 3.1 实现流程

```
┌─────────────────────────────────────────────────────────────────┐
│                      Planning Agent 流程                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   ┌──────────┐    ┌──────────┐    ┌──────────┐                  │
│   │ 用户输入  │───>│ LLM分解  │───>│ 拓扑排序  │                  │
│   │ 复杂任务  │    │ 子任务   │    │ 确定顺序  │                  │
│   └──────────┘    └──────────┘    └────┬─────┘                  │
│                                         │                        │
│                                         ▼                        │
│   ┌──────────┐    ┌──────────┐    ┌──────────┐                  │
│   │ 综合结果 <───│  │汇总整合  │<───│ 依次执行  │                  │
│   │ 最终响应  │    │          │    │ 子任务   │                  │
│   └──────────┘    └──────────┘    └──────────┘                  │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 3.2 核心代码结构

```python
class SubTask:
    """子任务类 - 表示一个分解后的子任务"""
    def __init__(self, id: str, description: str, dependent_on: List[str] = None):
        self.id = id                      # 子任务ID
        self.description = description    # 子任务描述
        self.status = "pending"           # 执行状态
        self.result = None                # 执行结果
        self.dependent_on = dependent_on  # 依赖的其他子任务ID

class PlanningAgent(AgentBase):
    """规划Agent - 能够自主规划和执行多步骤任务的智能代理"""

    def run(self, user_input: str) -> dict:
        """
        核心逻辑：
        1. 任务分解 - 使用LLM将大任务分解为子任务
        2. 确定顺序 - 拓扑排序确定执行顺序
        3. 执行子任务 - 依次执行每个子任务
        4. 综合结果 - 汇总所有子任务结果生成最终响应
        """
        # Step 1: 任务分解
        self.subtasks = []
        subtask_dicts = self._decompose_task(user_input)

        # Step 2: 确定执行顺序（拓扑排序）
        self.task_plan = self._build_execution_order()

        # Step 3: 依次执行子任务
        for task in self.task_plan:
            result = self._execute_subtask(task)
            task.result = result
            task.status = "completed"

        # Step 4: 综合结果
        final_response = self._synthesize_results(user_input)

        return {
            "response": final_response,
            "task_plan": [...],
            "subtask_results": [...],
            "num_subtasks": len(self.task_plan)
        }
```

### 3.3 任务分解Prompt

```python
decompose_prompt = f"""请将以下任务分解为多个具体的子任务：

用户任务：{user_input}

请将任务分解为3-7个子任务，并按照执行顺序编号。
对于每个子任务，说明：
1. 任务内容（做什么）
2. 预期产出（得到什么）

请用JSON数组格式返回：
[
    {{"id": "1", "description": "研究AI发展历史", "dependent_on": []}},
    {{"id": "2", "description": "分析当前技术趋势", "dependent_on": ["1"]}},
    {{"id": "3", "description": "总结未来发展方向", "dependent_on": ["1", "2"]}}
]

只返回JSON，不要有其他内容。"""
```

### 3.4 HierarchicalPlannerAgent (层级规划)

支持多层级任务分解的增强版本：

```
┌─────────────────────────────────────────────────────────────────┐
│                  HierarchicalPlannerAgent 流程                    │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐ │
│   │ 用户输入  │───>│ 层级分解  │───>│ 执行叶子  │───>│ 生成报告  │ │
│   │          │    │ (最多3层) │    │ 节点任务  │    │          │ │
│   └──────────┘    └──────────┘    └──────────┘    └──────────┘ │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 3.5 相关文件

| 文件 | 说明 |
|------|------|
| `agents/planning_agent.py` | PlanningAgent 和 HierarchicalPlannerAgent 实现 |
| `tests/test_planning_agent.py` | 模拟测试（快速验证） |
| `tests/test_planning_agent_with_minimax.py` | MiniMax API 集成测试 |

---

## 4.Multi-agent collaboration

多智能体协作是四种关键人工智能智能体设计模式中的最后一种。对于编写软件这样的复杂任务，多智能体方法会将任务分解为由不同角色（例如软件工程师、产品经理、设计师、QA（质量保证）工程师等）执行的子任务，并让不同的智能体完成不同的子任务。

### 4.1 实现流程

```
┌─────────────────────────────────────────────────────────────────┐
│                  Multi-agent Collaboration 流程                   │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   ┌──────────┐    ┌──────────┐    ┌──────────┐                  │
│   │ 用户输入  │───>│ 任务分配  │───>│ 执行角色  │                  │
│   │ 复杂任务  │    │ (LLM决策)│    │   任务   │                  │
│   └──────────┘    └──────────┘    └────┬─────┘                  │
│                                         │                        │
│                    ┌────────────────────┼────────────────────┐   │
│                    │                    │                    │   │
│                    ▼                    ▼                    ▼   │
│             顺序执行模式           并行执行模式           角色Agent │
│                    │                    │                    │   │
│                    └────────────────────┴────────────────────┘   │
│                                         │                        │
│                                         ▼                        │
│                                   ┌──────────┐                   │
│                                   │ 汇总整合  │                   │
│                                   │ 生成报告  │                   │
│                                   └──────────┘                   │
└─────────────────────────────────────────────────────────────────┘
```

### 4.2 核心代码结构

```python
@dataclass
class AgentRole:
    """Agent角色定义"""
    name: str                    # 角色名称
    description: str             # 角色描述
    system_prompt: str           # 系统提示词
    expertise: List[str]         # 专业领域

class RoleAgent:
    """角色Agent - 代表特定角色的轻量级Agent"""
    def execute(self, task: str) -> str:
        """执行角色任务"""
        user_message = f"请作为{self.role.name}执行以下任务：\n\n{task}"
        self.history.append(Message(role="user", content=user_message))
        response = self._call_llm(self.history)
        self.history.append(Message(role="assistant", content=response))
        return response

class MultiAgentCoordinator(AgentBase):
    """多智能体协调器 - 管理多个角色Agent的协调工作"""

    def run(self, user_input: str) -> dict:
        """
        核心逻辑：
        1. 任务分配 - LLM分析任务并分配给合适的角色
        2. 执行角色任务 - 顺序或并行执行
        3. 汇总整合 - 综合各角色结果生成最终响应
        """
        # Step 1: 分配任务给各角色
        task_distribution = self._distribute_tasks(user_input)

        # Step 2: 执行各角色任务
        if self.execution_mode == "parallel":
            self.execution_results = self._execute_parallel(task_distribution)
        else:
            self.execution_results = self._execute_sequential(task_distribution)

        # Step 3: 综合结果
        final_response = self._synthesize_results(user_input, task_distribution)

        return {
            "response": final_response,
            "role_results": self.execution_results,
            "task_distribution": task_distribution,
            "roles_executed": list(self.execution_results.keys())
        }
```

### 4.3 预设角色定义

```python
# 软件开发团队角色
def create_software_dev_roles() -> List[AgentRole]:
    return [
        AgentRole(
            name="产品经理",
            description="分析需求，制定产品方案",
            system_prompt="你是资深产品经理，擅长深入理解用户需求，将需求转化为具体的产品功能...",
            expertise=["需求分析", "产品规划", "用户研究"]
        ),
        AgentRole(
            name="架构师",
            description="设计系统架构和技术方案",
            system_prompt="你是资深系统架构师，擅长设计高可用、可扩展的系统架构...",
            expertise=["系统设计", "技术选型", "性能优化"]
        ),
        AgentRole(
            name="程序员",
            description="编写高质量代码",
            system_prompt="你是资深程序员，擅长编写清晰、可维护的代码...",
            expertise=["代码编写", "测试", "调试"]
        ),
        AgentRole(
            name="测试工程师",
            description="确保产品质量",
            system_prompt="你是资深测试工程师，擅长设计全面的测试用例...",
            expertise=["测试设计", "缺陷分析", "质量评估"]
        )
    ]

# 会议讨论团队角色
def create_discussion_roles() -> List[AgentRole]:
    return [
        AgentRole(name="主持人", description="引导讨论，确保流程", ...),
        AgentRole(name="技术专家", description="提供技术见解", ...),
        AgentRole(name="业务专家", description="提供业务视角", ...),
        AgentRole(name="记录员", description="记录会议要点", ...)
    ]
```

### 4.4 相关文件

| 文件 | 说明 |
|------|------|
| `agents/multi_agent.py` | MultiAgentCoordinator、RoleAgent、AgentRole 实现 |
| `tests/test_multi_agent.py` | 模拟测试（快速验证） |
| `tests/test_multi_agent_with_minimax.py` | MiniMax API 集成测试 |

---

## 5.运行测试

### 所有测试
```bash
cd Agent-hand-by-hand
python -m pytest tests/ -v
```

### 仅模拟测试（快速验证）
```bash
python -m pytest tests/test_reflection_agent.py tests/test_tool_use_agent.py tests/test_planning_agent.py tests/test_multi_agent.py -v
```

### MiniMax API 测试
```bash
# 需要设置环境变量
set MINIMAX_API_KEY=your-api-key
python -m pytest tests/test_reflection_agent_with_minimax.py tests/test_tool_use_agent_with_minimax.py tests/test_planning_agent_with_minimax.py tests/test_multi_agent_with_minimax.py -v
```

---

## 6.已实现Agent对比


| 范式 | 核心能力 | 适用场景 | 复杂度 |
|------|----------|----------|--------|
| Reflection | 自我反思与修正 | 需要高质量回答的任务 | ⭐⭐ |
| Tool Use | 外部工具调用 | 需要计算、搜索等能力的任务 | ⭐⭐ |
| ReAct | 推理+行动 | 复杂多步骤任务 | ⭐⭐⭐ |
| Planning | 任务分解与规划 | 复杂多步骤任务 | ⭐⭐⭐ |
| Multi-agent | 多角色协作 | 团队协作式复杂任务 | ⭐⭐⭐⭐ |

---

## 7.扩展新的Agent范式

每个Agent范式需要包含：

1. **代码实现** - 放入 `agents/` 目录
2. **测试用例** - 放入 `tests/` 目录（模拟 + API）
3. **README文档** - 在对应二级标题下添加实现流程说明

命名规范：
- 文件名：`{agent_type}_agent.py`
- 测试文件：`test_{agent_type}_agent.py`
- API测试：`test_{agent_type}_agent_with_minimax.py`
