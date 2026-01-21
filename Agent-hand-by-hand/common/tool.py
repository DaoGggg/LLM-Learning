"""
工具模块 - 定义Agent可使用的外部工具

包含工具基类和常用工具实现。
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, Any, TypeVar, get_type_hints, Union
import json


T = TypeVar('T')


@dataclass
class ToolResult:
    """
    工具执行结果

    属性:
        success: 是否成功
        content: 结果内容
        error: 错误信息（如果失败）
    """
    success: bool
    content: Any
    error: str = None


@dataclass
class ToolParameter:
    """
    工具参数定义

    属性:
        name: 参数名称
        type: 参数类型
        description: 参数描述
        required: 是否必需
        default: 默认值
    """
    name: str
    type: type = str
    description: str = ""
    required: bool = False
    default: Any = None


class ToolBase(ABC):
    """
    工具基类 - 所有工具的抽象基类

    定义了工具的通用接口，包括：
    - 工具元信息（名称、描述、参数）
    - 工具执行方法
    """

    def __init__(self):
        self._name = self.__class__.__name__.lower().replace("tool", "")
        self._description = self._get_description()
        self._parameters = self._get_parameters()

    def _get_description(self) -> str:
        """从文档字符串获取工具描述"""
        return self.__doc__.strip() if self.__doc__ else ""

    def _get_parameters(self) -> Dict[str, ToolParameter]:
        """从类型注解获取参数定义"""
        parameters = {}

        try:
            hints = get_type_hints(self.execute)
            for param_name, param_type in hints.items():
                if param_name in ('self', 'return', 'kwargs'):
                    continue

                # 从execute方法参数获取默认值
                import inspect
                sig = inspect.signature(self.execute)
                param = sig.parameters.get(param_name)

                required = False
                default = None

                if param:
                    if param.default is inspect.Parameter.empty:
                        required = True
                    else:
                        default = param.default

                parameters[param_name] = ToolParameter(
                    name=param_name,
                    type=param_type,
                    description="",
                    required=required,
                    default=default
                )
        except Exception:
            pass

        return parameters

    @property
    def name(self) -> str:
        """获取工具名称"""
        return self._name

    @property
    def description(self) -> str:
        """获取工具描述"""
        return self._description

    @property
    def parameters(self) -> Dict[str, ToolParameter]:
        """获取参数定义"""
        return self._parameters

    @abstractmethod
    def execute(self, **kwargs) -> ToolResult:
        """
        执行工具功能

        参数:
            **kwargs: 工具参数

        返回:
            ToolResult: 执行结果
        """
        pass

    def to_schema(self) -> Dict[str, Any]:
        """
        转换为工具定义Schema（用于LLM调用）

        返回:
            工具定义字典
        """
        properties = {}
        required_params = []

        for name, param in self.parameters.items():
            type_str = param.type.__name__.lower()
            if param.type == int:
                type_str = "integer"
            elif param.type == float:
                type_str = "number"
            elif param.type == bool:
                type_str = "boolean"

            properties[name] = {
                "type": type_str,
                "description": param.description
            }

            if param.required:
                required_params.append(name)

        schema = {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required_params
                }
            }
        }

        return schema


class CalculatorTool(ToolBase):
    """
    计算器工具 - 执行数学运算

    示例:
        result = CalculatorTool().execute(expression="2 + 3")
    """

    def execute(self, expression: str) -> ToolResult:
        """
        执行数学表达式计算

        参数:
            expression: 数学表达式，如 "2 + 3 * 4"

        返回:
            计算结果
        """
        try:
            # 注意：eval存在安全风险，生产环境应使用安全的表达式解析器
            # 这里仅用于演示目的
            allowed_chars = set('0123456789+-*/.() ')
            if not all(c in allowed_chars for c in expression):
                return ToolResult(
                    success=False,
                    content=None,
                    error="表达式包含非法字符"
                )

            result = eval(expression)
            return ToolResult(success=True, content=str(result))
        except Exception as e:
            return ToolResult(success=False, content=None, error=str(e))


class SearchTool(ToolBase):
    """
    搜索工具 - 模拟网络搜索功能

    示例:
        result = SearchTool().execute(query="Python教程")
    """

    def execute(self, query: str) -> ToolResult:
        """
        执行搜索查询

        参数:
            query: 搜索关键词

        返回:
            模拟的搜索结果
        """
        # 模拟搜索结果，实际应用中可接入真实搜索引擎
        mock_results = [
            f"关于'{query}'的搜索结果1: 这是一个相关网页...",
            f"关于'{query}'的搜索结果2: 另一个相关资源...",
            f"关于'{query}'的搜索结果3: 还有更多内容..."
        ]
        return ToolResult(success=True, content=mock_results)


class FileReaderTool(ToolBase):
    """
    文件读取工具 - 读取文本文件内容

    示例:
        result = FileReaderTool().execute(filepath="test.txt")
    """

    def execute(self, filepath: str) -> ToolResult:
        """
        读取文件内容

        参数:
            filepath: 文件路径

        返回:
            文件内容
        """
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
            return ToolResult(success=True, content=content)
        except FileNotFoundError:
            return ToolResult(success=False, content=None, error=f"文件不存在: {filepath}")
        except Exception as e:
            return ToolResult(success=False, content=None, error=str(e))


class FileWriterTool(ToolBase):
    """
    文件写入工具 - 创建或覆盖文本文件

    示例:
        result = FileWriterTool().execute(filepath="test.txt", content="Hello")
    """

    def execute(self, filepath: str, content: str) -> ToolResult:
        """
        写入文件内容

        参数:
            filepath: 文件路径
            content: 要写入的内容

        返回:
            操作结果
        """
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            return ToolResult(success=True, content=f"文件已写入: {filepath}")
        except Exception as e:
            return ToolResult(success=False, content=None, error=str(e))


class DateTimeTool(ToolBase):
    """
    日期时间工具 - 获取当前日期和时间

    示例:
        result = DateTimeTool().execute()
    """

    def execute(self) -> ToolResult:
        """
        获取当前日期时间

        返回:
            当前日期时间字符串
        """
        from datetime import datetime
        now = datetime.now()
        return ToolResult(
            success=True,
            content=now.strftime("%Y-%m-%d %H:%M:%S")
        )


class WebFetchTool(ToolBase):
    """
    网页抓取工具 - 获取网页内容

    示例:
        result = WebFetchTool().execute(url="https://example.com")
    """

    def execute(self, url: str) -> ToolResult:
        """
        获取网页内容

        参数:
            url: 网页URL

        返回:
            网页内容摘要
        """
        try:
            import urllib.request
            import urllib.parse

            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }

            request = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(request, timeout=10) as response:
                content = response.read().decode('utf-8')

            # 返回摘要（避免内容过长）
            summary = content[:500] + "..." if len(content) > 500 else content
            return ToolResult(success=True, content=summary)
        except Exception as e:
            return ToolResult(success=False, content=None, error=str(e))


# 工具注册表 - 方便统一管理
DEFAULT_TOOLS = {
    "calculator": CalculatorTool,
    "search": SearchTool,
    "file_reader": FileReaderTool,
    "file_writer": FileWriterTool,
    "datetime": DateTimeTool,
    "web_fetch": WebFetchTool,
}


def create_tool(tool_name: str, **kwargs) -> ToolBase:
    """
    工厂函数 - 创建工具实例

    参数:
        tool_name: 工具名称
        **kwargs: 工具初始化参数

    返回:
        ToolBase实例
    """
    if tool_name not in DEFAULT_TOOLS:
        raise ValueError(f"未知工具: {tool_name}，可选工具: {list(DEFAULT_TOOLS.keys())}")

    return DEFAULT_TOOLS[tool_name](**kwargs)
