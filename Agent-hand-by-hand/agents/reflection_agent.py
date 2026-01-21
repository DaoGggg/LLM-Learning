"""
反思Agent（Reflection Agent）实现

Reflection是指Agent能够对自己的行为和决策进行推理和分析的能力。
这种能力使Agent能够更好地理解自己的行为和决策，并在未来的决策中更好地利用这些信息。

核心思路：
1. 生成初始响应
2. 对响应进行自我反思
3. 根据反思结果修正响应
4. 可迭代进行多轮反思
"""

from typing import List, Optional
from common.llm_client import LLMClientBase, Message, create_llm_client
from common.agent_base import AgentBase, AgentState


class ReflectionAgent(AgentBase):
    """
    反思Agent - 具有自我反思能力的智能代理

    反思Agent的工作流程：
    1. 接收用户输入
    2. 生成初始响应
    3. 对响应进行自我反思，识别问题和改进点
    4. 根据反思结果修正响应
    5. 可选择进行多轮反思直到满意

    使用示例:
        llm = create_llm_client("mock", responses=["初始回答", "反思后的改进回答"])
        agent = ReflectionAgent(name="反思者", llm_client=llm)
        response = agent.run("请解释什么是人工智能")
    """

    def __init__(
        self,
        name: str = "反思Agent",
        llm_client: LLMClientBase = None,
        max_reflections: int = 2,
        reflection_temperature: float = 0.8
    ):
        """
        初始化反思Agent

        参数:
            name: Agent名称
            llm_client: LLM客户端实例（可选，将使用MockLLMClient）
            max_reflections: 最大反思轮数
            reflection_temperature: 反思时的温度参数（较高的温度促进创造性思考）
        """
        if llm_client is None:
            llm_client = create_llm_client("mock")

        super().__init__(name, llm_client)

        self.max_reflections = max_reflections
        self.reflection_temperature = reflection_temperature

        # 反思历史：记录每一轮的反思过程
        self.reflection_history: List[dict] = []

        # 系统提示词
        self._setup_system_prompt()

    def _setup_system_prompt(self) -> None:
        """设置系统提示词"""
        system_prompt = """你是一个善于深度思考的智能助手。

你的工作方式：
1. 首先给出问题的初步答案
2. 然后对给出的答案进行自我反思
3. 最后根据反思改进答案

请始终：
- 提供准确、有深度的分析
- 勇于质疑自己的结论
- 追求逻辑严密和事实准确"""
        self.add_system_prompt(system_prompt)

    def _generate_initial_response(self, user_input: str) -> str:
        """
        生成初始响应

        参数:
            user_input: 用户输入

        返回:
            初始响应内容
        """
        messages = self.history + [Message(role="user", content=user_input)]
        return self.call_llm(messages, temperature=0.7)

    def _reflect(self, user_input: str, response: str) -> str:
        """
        对响应进行自我反思

        参数:
            user_input: 用户原始输入
            response: 待反思的响应

        返回:
            反思内容（包含对响应的评价和改进建议）
        """
        reflection_prompt = f"""请对以下回答进行深入反思和分析：

用户问题：{user_input}

当前回答：{response}

请从以下角度进行反思：
1. 回答是否准确？是否遗漏了重要信息？
2. 逻辑是否清晰？论证是否充分？
3. 是否有改进空间？如何改进？
4. 是否存在偏见或错误假设？

请简要但深刻地指出问题所在，并给出具体的改进建议。"""

        messages = self.history + [
            Message(role="user", content=reflection_prompt)
        ]
        return self.call_llm(messages, temperature=self.reflection_temperature)

    def _revise_response(self, user_input: str, response: str, reflection: str) -> str:
        """
        根据反思修正响应

        参数:
            user_input: 用户输入
            response: 原响应
            reflection: 反思内容

        返回:
            修正后的响应
        """
        revise_prompt = f"""基于以下反思意见，请改进你的回答：

用户问题：{user_input}

原回答：{response}

反思意见：
{reflection}

请根据反思意见，给出一个更完善、更准确的回答。"""

        messages = self.history + [
            Message(role="user", content=revise_prompt)
        ]
        return self.call_llm(messages, temperature=0.7)

    def run(self, user_input: str, max_reflections: int = None) -> dict:
        """
        执行反思Agent的核心逻辑

        参数:
            user_input: 用户输入
            max_reflections: 最大反思轮数（覆盖默认值）

        返回:
            包含以下字段的字典：
            - response: 最终响应
            - initial_response: 初始响应
            - reflections: 反思内容列表
            - num_reflections: 反思轮数
        """
        max_reflections = max_reflections or self.max_reflections

        # 重置反思历史
        self.reflection_history = []

        # 添加用户消息
        self.add_user_message(user_input)

        # Step 1: 生成初始响应
        self.set_status("thinking")
        initial_response = self._generate_initial_response(user_input)
        self.add_assistant_message(initial_response)

        # 记录初始响应
        current_response = initial_response
        reflections = []

        # Step 2-4: 反思循环
        for i in range(max_reflections):
            self.set_status(f"reflecting_{i+1}")

            # 进行反思
            reflection = self._reflect(user_input, current_response)
            reflections.append(reflection)

            # 记录反思历史
            self.reflection_history.append({
                "round": i + 1,
                "response": current_response,
                "reflection": reflection
            })

            # 判断是否需要继续反思
            should_stop = self._should_stop_reflection(reflection, i + 1)
            if should_stop:
                break

            # 修正响应
            current_response = self._revise_response(user_input, current_response, reflection)

            # 更新历史
            self.history[-1] = Message(role="assistant", content=current_response)

        self.set_status("finished")

        # 返回结果
        return {
            "response": current_response,
            "initial_response": initial_response,
            "reflections": reflections,
            "num_reflections": len(reflections),
            "reflection_history": self.reflection_history
        }

    def _should_stop_reflection(self, reflection: str, round_num: int) -> bool:
        """
        判断是否应该停止反思

        参数:
            reflection: 最新反思内容
            round_num: 当前轮数

        返回:
            是否停止
        """
        # 反思内容太短，可能已经足够好（但排除纯英文/符号的情况）
        if len(reflection.strip()) < 10:
            # 检查是否包含实质内容（中文或多个单词）
            import re
            if not re.search(r'[\u4e00-\u9fff]|\w{3,}', reflection):
                return True

        # 检查反思中是否包含"满意"、"足够好"等关键词
        positive_keywords = ["满意", "足够好", "已经很好", "无需改进", "已经很完善"]
        for keyword in positive_keywords:
            if keyword in reflection:
                return True

        return False

    def get_reflection_summary(self) -> str:
        """
        获取反思过程总结

        返回:
            总结字符串
        """
        if not self.reflection_history:
            return "尚未进行任何反思"

        summary_parts = [f"反思Agent: {self.name}"]
        summary_parts.append(f"总反思轮数: {len(self.reflection_history)}\n")

        for item in self.reflection_history:
            summary_parts.append(f"第{item['round']}轮:")
            summary_parts.append(f"  响应: {item['response'][:100]}...")
            summary_parts.append(f"  反思: {item['reflection'][:100]}...")
            summary_parts.append("")

        return "\n".join(summary_parts)


class SelfImprovingAgent(AgentBase):
    """
    自我提升Agent - 基于历史经验持续改进的Agent

    这是Reflection Agent的增强版本，会记录所有交互历史，
    并从中学习以在未来做出更好的决策。

    特点：
    1. 持久化存储交互经验
    2. 基于历史经验调整行为
    3. 能够识别模式并应用
    """

    def __init__(
        self,
        name: str = "自我提升Agent",
        llm_client: LLMClientBase = None
    ):
        if llm_client is None:
            llm_client = create_llm_client("mock")

        super().__init__(name, llm_client)

        # 经验库：存储历史交互的总结
        self.experiences: List[dict] = []

        # 改进建议库
        self.improvement_notes: List[str] = []

        self._setup_system_prompt()

    def _setup_system_prompt(self) -> None:
        """设置系统提示词"""
        system_prompt = """你是一个善于从经验中学习的智能助手。

你会：
1. 认真对待每一次交互
2. 从错误和不足中学习
3. 持续改进自己的回答质量
4. 总结规律并应用"""
        self.add_system_prompt(system_prompt)

    def run(self, user_input: str) -> dict:
        """
        执行自我提升Agent

        参数:
            user_input: 用户输入

        返回:
            执行结果字典
        """
        self.add_user_message(user_input)

        # 结合经验生成响应
        experience_context = self._get_experience_context()
        enriched_input = f"{experience_context}\n\n用户问题：{user_input}"

        # 调用LLM
        response = self.call_llm(self.history + [Message(role="user", content=enriched_input)])

        self.add_assistant_message(response)

        # 反思并更新经验
        self._reflect_and_learn(user_input, response)

        return {
            "response": response,
            "experiences_count": len(self.experiences)
        }

    def _get_experience_context(self) -> str:
        """
        获取经验上下文

        返回:
            经验上下文字符串
        """
        if not self.experiences:
            return "这是我们的第一次交流，我将尽力给出最好的回答。"

        recent_experiences = self.experiences[-3:]  # 只取最近3条
        context_parts = ["基于过往交流的经验："]

        for exp in recent_experiences:
            context_parts.append(f"- {exp['summary']}")

        return "\n".join(context_parts)

    def _reflect_and_learn(self, user_input: str, response: str) -> None:
        """
        反思并更新经验

        参数:
            user_input: 用户输入
            response: 生成的响应
        """
        reflection_prompt = f"""请简短总结这次交互的关键收获：

用户问题：{user_input}
我的回答：{response}

请用一句话总结这次学到的经验或教训。"""

        reflection = self.call_llm(
            [Message(role="user", content=reflection_prompt)],
            temperature=0.8
        )

        self.experiences.append({
            "user_input": user_input,
            "response": response,
            "reflection": reflection,
            "summary": reflection
        })

        # 保留最近50条经验
        if len(self.experiences) > 50:
            self.experiences = self.experiences[-50:]


# 便捷函数：创建Reflection Agent
def create_reflection_agent(
    name: str = "反思Agent",
    provider: str = "mock",
    **kwargs
) -> ReflectionAgent:
    """
    创建Reflection Agent的便捷函数

    参数:
        name: Agent名称
        provider: LLM提供商（'openai'/'anthropic'/'mock'）
        **kwargs: 其他参数

    返回:
        ReflectionAgent实例
    """
    llm_client = create_llm_client(provider, **kwargs)
    return ReflectionAgent(name=name, llm_client=llm_client)
