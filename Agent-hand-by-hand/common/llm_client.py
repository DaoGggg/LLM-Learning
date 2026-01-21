"""
LLM客户端模块 - 提供统一的LLM调用接口

支持多种LLM后端（OpenAI、Anthropic等），通过统一的接口调用大语言模型。
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
import os


@dataclass
class Message:
    """
    消息类 - 表示对话中的一条消息

    属性:
        role: 消息角色（'user'/'assistant'/'system'）
        content: 消息内容
    """
    role: str
    content: str


@dataclass
class ChatCompletionRequest:
    """
    聊天补全请求类

    属性:
        messages: 消息列表
        model: 模型名称
        temperature: 温度参数（控制随机性）
        max_tokens: 最大token数
        stream: 是否流式输出
    """
    messages: List[Message]
    model: str = "gpt-3.5-turbo"
    temperature: float = 0.7
    max_tokens: Optional[int] = None
    stream: bool = False


@dataclass
class ChatCompletionChoice:
    """
    聊天补全结果选项

    属性:
        message: 生成的回复消息
        finish_reason: 结束原因
    """
    message: Message
    finish_reason: str


@dataclass
class ChatCompletionResponse:
    """
    聊天补全响应类

    属性:
        id: 响应ID
        object: 对象类型
        created: 创建时间戳
        model: 使用的模型
        choices: 回复选项列表
        usage: token使用统计
    """
    id: str
    object: str
    created: int
    model: str
    choices: List[ChatCompletionChoice]
    usage: Dict[str, int]


class LLMClientBase(ABC):
    """
    LLM客户端基类 - 定义统一的接口规范

    所有LLM客户端实现都需要继承此类并实现chat方法。
    """

    @abstractmethod
    def chat(self, request: ChatCompletionRequest) -> ChatCompletionResponse:
        """
        发送聊天请求并获取回复

        参数:
            request: 聊天补全请求

        返回:
            聊天补全响应
        """
        pass

    @abstractmethod
    def get_model_name(self) -> str:
        """
        获取模型名称

        返回:
            模型名称字符串
        """
        pass


class OpenAIClient(LLMClientBase):
    """
    OpenAI客户端 - 调用OpenAI API

    参数:
        api_key: OpenAI API密钥
        base_url: API基础URL（可选）
        model: 使用的模型名称
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: str = "gpt-3.5-turbo"
    ):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.base_url = base_url or os.getenv("OPENAI_API_BASE_URL")
        self.model = model

        if not self.api_key:
            raise ValueError("请设置OPENAI_API_KEY环境变量或传入api_key参数")

    def chat(self, request: ChatCompletionRequest) -> ChatCompletionResponse:
        """
        调用OpenAI Chat Completion API
        """
        import openai

        client = openai.OpenAI(
            api_key=self.api_key,
            base_url=self.base_url
        )

        # 转换消息格式
        messages = [{"role": m.role, "content": m.content} for m in request.messages]

        # 构建API调用参数（排除None值和不必要的参数）
        api_params = {
            "model": request.model,
            "messages": messages
        }

        # 只有非None值才传递给API
        if request.temperature is not None:
            api_params["temperature"] = request.temperature
        if request.max_tokens is not None:
            api_params["max_tokens"] = request.max_tokens
        # 只有stream=True时才传递stream参数
        if request.stream:
            api_params["stream"] = True

        # 调用API
        response = client.chat.completions.create(**api_params)

        # 转换为标准响应格式
        choices = [
            ChatCompletionChoice(
                message=Message(
                    role=choice.message.role,
                    content=choice.message.content
                ),
                finish_reason=choice.finish_reason
            )
            for choice in response.choices
        ]

        return ChatCompletionResponse(
            id=response.id,
            object=response.object,
            created=response.created,
            model=response.model,
            choices=choices,
            usage={
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens
            }
        )

    def get_model_name(self) -> str:
        return self.model


class AnthropicClient(LLMClientBase):
    """
    Anthropic客户端 - 调用Anthropic Claude API

    参数:
        api_key: Anthropic API密钥
        model: 使用的模型名称
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "claude-sonnet-4-20250514"
    ):
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        self.model = model

        if not self.api_key:
            raise ValueError("请设置ANTHROPIC_API_KEY环境变量或传入api_key参数")

    def chat(self, request: ChatCompletionRequest) -> ChatCompletionResponse:
        """
        调用Anthropic Messages API
        """
        import anthropic

        client = anthropic.Anthropic(api_key=self.api_key)

        # 转换消息格式
        messages = [
            {"role": m.role if m.role != "assistant" else "assistant", "content": m.content}
            for m in request.messages
        ]

        # 调用API
        response = client.messages.create(
            model=request.model,
            messages=messages,
            temperature=request.temperature,
            max_tokens=request.max_tokens or 4096
        )

        # 转换为标准响应格式
        choices = [
            ChatCompletionChoice(
                message=Message(
                    role="assistant",
                    content=choice.text
                ),
                finish_reason=choice.stop_reason if hasattr(choice, 'stop_reason') else "stop"
            )
            for choice in response.content
        ]

        return ChatCompletionResponse(
            id=f"ant-{response.id}",
            object="chat.completion",
            created=int(response.created_at),
            model=response.model,
            choices=choices,
            usage={
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens
            }
        )

    def get_model_name(self) -> str:
        return self.model


class MockLLMClient(LLMClientBase):
    """
    模拟LLM客户端 - 用于测试，无需真实API密钥

    参数:
        responses: 预设的回复列表，按顺序返回
    """

    def __init__(self, responses: List[str] = None):
        self.responses = responses or ["这是一个模拟回复。"]
        self.call_count = 0

    def chat(self, request: ChatCompletionRequest) -> ChatCompletionResponse:
        """
        返回预设的模拟回复
        """
        import time
        import uuid

        response_text = self.responses[self.call_count % len(self.responses)]
        self.call_count += 1

        choice = ChatCompletionChoice(
            message=Message(role="assistant", content=response_text),
            finish_reason="stop"
        )

        return ChatCompletionResponse(
            id=f"mock-{uuid.uuid4().hex[:8]}",
            object="chat.completion",
            created=int(time.time()),
            model="mock-model",
            choices=[choice],
            usage={"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}
        )

    def get_model_name(self) -> str:
        return "mock-model"


class MiniMaxClient(LLMClientBase):
    """
    MiniMax客户端 - 调用 MiniMax API

    参数:
        api_key: MiniMax API密钥
        model: 使用的模型名称（默认: MiniMax-M2）
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "MiniMax-M2"
    ):
        self.api_key = api_key or os.getenv("MINIMAX_API_KEY")
        self.model = model

        if not self.api_key:
            raise ValueError("请设置MINIMAX_API_KEY环境变量或传入api_key参数")

    def chat(self, request: ChatCompletionRequest) -> ChatCompletionResponse:
        """
        调用 MiniMax Chat Completion API
        """
        import requests
        import time
        import uuid

        url = "https://api.minimax.chat/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        # 转换消息格式
        messages = [{"role": m.role, "content": m.content} for m in request.messages]

        # 构建请求数据
        data = {
            "model": self.model,
            "messages": messages
        }

        # 可选参数
        if request.temperature is not None:
            data["temperature"] = request.temperature

        try:
            response = requests.post(url, headers=headers, json=data, timeout=60)
            response.raise_for_status()
            result = response.json()

            # 解析响应
            choice = result["choices"][0]
            message = choice["message"]

            chat_choice = ChatCompletionChoice(
                message=Message(
                    role=message.get("role", "assistant"),
                    content=message.get("content", "")
                ),
                finish_reason=choice.get("finish_reason", "stop")
            )

            return ChatCompletionResponse(
                id=result.get("id", f"minimax-{uuid.uuid4().hex[:8]}"),
                object=result.get("object", "chat.completion"),
                created=result.get("created", int(time.time())),
                model=result.get("model", self.model),
                choices=[chat_choice],
                usage={
                    "prompt_tokens": result.get("usage", {}).get("prompt_tokens", 0),
                    "completion_tokens": result.get("usage", {}).get("completion_tokens", 0),
                    "total_tokens": result.get("usage", {}).get("total_tokens", 0)
                }
            )
        except requests.exceptions.RequestException as e:
            raise ValueError(f"MiniMax API请求失败: {str(e)}")

    def get_model_name(self) -> str:
        return self.model


def create_llm_client(provider: str = "openai", **kwargs) -> LLMClientBase:
    """
    工厂函数 - 创建LLM客户端实例

    参数:
        provider: 提供商名称（'openai'/'anthropic'/'minimax'/'mock'）
        **kwargs: 其他配置参数

    返回:
        LLMClientBase实例
    """
    providers = {
        "openai": OpenAIClient,
        "anthropic": AnthropicClient,
        "mock": MockLLMClient
    }

    # MiniMax 特殊处理：使用专门的 MiniMax 客户端
    if provider == "minimax":
        api_key = kwargs.pop("api_key", None) or os.environ.get("MINIMAX_API_KEY")
        model = kwargs.pop("model", "MiniMax-M2")
        return MiniMaxClient(api_key=api_key, model=model)

    if provider not in providers:
        raise ValueError(f"不支持的LLM提供商: {provider}，可选值: {list(providers.keys())}")

    return providers[provider](**kwargs)
