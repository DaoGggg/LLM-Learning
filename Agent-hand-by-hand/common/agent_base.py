"""
Agent基类模块 - 提供Agent的抽象基类和通用功能

包含Agent的基本结构、状态管理和对话历史功能。
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from .llm_client import LLMClientBase, ChatCompletionRequest, Message


@dataclass
class AgentState:
    """
    Agent状态类 - 跟踪Agent的当前状态

    属性:
        name: Agent名称
        status: 状态（'idle'/'thinking'/'acting'/'finished'）
        memory: 记忆/知识库
    """
    name: str = "agent"
    status: str = "idle"
    memory: Dict[str, Any] = field(default_factory=dict)


class AgentBase(ABC):
    """
    Agent基类 - 所有Agent的抽象基类

    定义了Agent的通用接口和功能，包括：
    - 对话历史管理
    - 状态跟踪
    - LLM调用封装
    """

    def __init__(self, name: str, llm_client: LLMClientBase):
        """
        初始化Agent

        参数:
            name: Agent名称
            llm_client: LLM客户端实例
        """
        self.name = name
        self.llm_client = llm_client
        self.state = AgentState(name=name)
        self.history: List[Message] = []

    def add_system_prompt(self, prompt: str) -> None:
        """
        添加系统提示词到对话历史

        参数:
            prompt: 系统提示词内容
        """
        self.history.insert(0, Message(role="system", content=prompt))

    def add_user_message(self, content: str) -> None:
        """
        添加用户消息到对话历史

        参数:
            content: 消息内容
        """
        self.history.append(Message(role="user", content=content))

    def add_assistant_message(self, content: str) -> None:
        """
        添加助手消息到对话历史

        参数:
            content: 消息内容
        """
        self.history.append(Message(role="assistant", content=content))

    def clear_history(self) -> None:
        """
        清空对话历史
        """
        self.history = []

    def call_llm(
        self,
        messages: List[Message],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None
    ) -> str:
        """
        调用LLM获取回复

        参数:
            messages: 消息列表
            temperature: 温度参数
            max_tokens: 最大token数

        返回:
            LLM生成的回复内容
        """
        request = ChatCompletionRequest(
            messages=messages,
            model=self.llm_client.get_model_name(),
            temperature=temperature,
            max_tokens=max_tokens
        )

        response = self.llm_client.chat(request)
        return response.choices[0].message.content

    @abstractmethod
    def run(self, user_input: str) -> str:
        """
        执行Agent的核心逻辑

        参数:
            user_input: 用户输入

        返回:
            Agent的响应
        """
        pass

    def set_status(self, status: str) -> None:
        """
        设置Agent状态

        参数:
            status: 新状态
        """
        self.state.status = status

    def get_history(self) -> List[Message]:
        """
        获取对话历史

        返回:
            消息历史列表
        """
        return self.history.copy()
