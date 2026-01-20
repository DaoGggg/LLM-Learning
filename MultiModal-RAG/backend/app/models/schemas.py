"""
数据模型定义
使用 Pydantic 定义 API 请求/响应的数据结构
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


# =======================
# PDF 上传相关
# =======================

class UploadResponse(BaseModel):
    """上传 PDF 响应"""
    success: bool
    task_id: str
    file_path: str
    filename: str
    file_size: int
    pdf_info: Dict[str, Any]


# =======================
# PDF 信息相关
# =======================

class PDFInfo(BaseModel):
    """PDF 基本信息"""
    num_pages: int
    file_size: int
    metadata: Optional[Dict[str, Any]] = None


class PDFInfoResponse(BaseModel):
    """PDF 信息响应"""
    success: bool
    task_id: str
    pdf_info: PDFInfo


# =======================
# 元素解析相关
# =======================

class Coordinates(BaseModel):
    """元素坐标信息"""
    points: Optional[List[List[float]]] = None
    system: Optional[str] = None


class ElementInfo(BaseModel):
    """PDF 元素信息"""
    id: int = Field(..., description="元素序号")
    type: str = Field(..., description="元素类型: Title, NarrativeText, Table...")
    content: str = Field(..., description="元素文本内容")
    page: int = Field(..., description="所在页码")
    coordinates: Optional[Coordinates] = Field(None, description="位置坐标")
    metadata: Optional[Dict[str, Any]] = Field(None, description="其他元数据")


class PageElements(BaseModel):
    """单页元素解析结果"""
    page: int
    total_pages: int
    elements: List[ElementInfo]
    image_path: Optional[str] = Field(None, description="页面图片路径")


class ParseResult(BaseModel):
    """完整解析结果"""
    task_id: str
    total_pages: int
    pages: List[PageElements]
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ParseResponse(BaseModel):
    """解析响应"""
    success: bool
    task_id: str
    total_pages: int
    pages: List[Dict[str, Any]]


# =======================
# 进度相关
# =======================

class ProgressInfo(BaseModel):
    """进度信息"""
    task_id: str
    status: str = Field(..., description="pending / processing / completed / failed")
    current_page: int = 0
    total_pages: int = 0
    progress: float = 0.0
    message: str = ""
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


# =======================
# Markdown 相关
# =======================

class MarkdownResponse(BaseModel):
    """Markdown 响应"""
    success: bool
    task_id: str
    markdown_path: str
    preview_content: str


# =======================
# 错误响应
# =======================

class ErrorResponse(BaseModel):
    """错误响应"""
    success: bool = False
    error: str
    detail: Optional[str] = None
    code: Optional[str] = None
