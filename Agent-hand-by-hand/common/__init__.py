"""
通用模块包 - 提供Agent开发的基础组件

包含:
- llm_client: LLM客户端接口
- agent_base: Agent基类
- tool: 工具定义和工具基类
"""

from .llm_client import (
    Message,
    ChatCompletionRequest,
    ChatCompletionResponse,
    LLMClientBase,
    OpenAIClient,
    AnthropicClient,
    MockLLMClient,
    create_llm_client
)

from .agent_base import (
    AgentState,
    AgentBase
)

from .tool import (
    ToolResult,
    ToolParameter,
    ToolBase,
    CalculatorTool,
    SearchTool,
    FileReaderTool,
    FileWriterTool,
    DateTimeTool,
    WebFetchTool,
    DEFAULT_TOOLS,
    create_tool
)

__all__ = [
    # LLM客户端
    "Message",
    "ChatCompletionRequest",
    "ChatCompletionResponse",
    "LLMClientBase",
    "OpenAIClient",
    "AnthropicClient",
    "MockLLMClient",
    "create_llm_client",
    # Agent基类
    "AgentState",
    "AgentBase",
    # 工具
    "ToolResult",
    "ToolParameter",
    "ToolBase",
    "CalculatorTool",
    "SearchTool",
    "FileReaderTool",
    "FileWriterTool",
    "DateTimeTool",
    "WebFetchTool",
    "DEFAULT_TOOLS",
    "create_tool"
]
